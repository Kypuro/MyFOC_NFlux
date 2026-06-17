# PMSM Parameter Identification Strategy

This note records the parameter-identification approach intended for the PC host
tool and firmware integration. The main target is accurate PMSM stator resistance
identification first, because Rs affects low-speed sensorless observers and current
controller tuning.

## Current Conclusion

Do not use normal closed-loop running data directly for Rs identification.
The present Simulink diagnostic estimator is useful to show why the operating
point matters, but it is not accurate enough as the final PC-host algorithm.

The recommended production workflow is a self-commissioning test sequence:

1. Firmware enters a dedicated identification mode.
2. Motor is kept stopped or locked.
3. Firmware injects controlled voltage or current levels.
4. Firmware streams measured current, bus voltage, PWM duty, and test state.
5. The PC host computes the parameter offline from captured samples.
6. The result is validated before writing it back to the project settings.

## Research Notes

MathWorks Motor Control Blockset uses a parameter estimation workflow that
estimates Rs, Ld, Lq, Ke, J, and B, and it runs tests in a prescribed order of
Rs -> Ld -> Lq -> mechanical parameters. Its Rs estimator injects two voltages
for each phase, measures the corresponding current responses, estimates each
phase resistance, and averages the three phase results.

Sources:

- MathWorks PMSM parameter estimation example:
  https://www.mathworks.com/help/mcb/gs/pmsm-parameter-estimation-using-recommended-hardware.html
- MathWorks PMSM Rs Estimator block:
  https://www.mathworks.com/help/mcb/ref/pmsmrsestimator.html
- MathWorks custom-hardware parameter estimation workflow:
  https://www.mathworks.com/help/mcb/gs/estimate-pmsm-parameters-using-custom-hardware.html

The academic literature points to the same practical constraints:

- Standstill or locked-rotor tests eliminate rotor-flux/back-EMF influence for
  electrical parameter estimation.
- Simultaneous online estimation of Rs, inductance, and flux linkage can become
  rank deficient unless one or more parameters are fixed, additional states are
  used, or an injection signal is added.
- Inverter nonlinearity, especially dead time and voltage distortion, is a major
  source of resistance-estimation error when commanded voltage is used instead
  of measured terminal voltage.
- Winding resistance must be interpreted at a known temperature. Near room
  temperature, copper is commonly corrected with a coefficient around
  `0.00393 / degC`; a 25 degC rise changes Rs by almost 10 percent.

Sources:

- Zhu et al., "Online parameter estimation for permanent magnet synchronous
  machines: an overview", IEEE Access, 2021:
  https://eprints.whiterose.ac.uk/id/eprint/173931/1/09402773.pdf
- Erixon and Lind-Anderton, "Parameter estimation using a self-commissioning
  sequence for internal permanent magnet synchronous motors", Chalmers, 2022:
  https://odr.chalmers.se/bitstreams/4c629765-08f4-4ca9-97fa-9abeac325003/download
- Lee et al., "Electrical Parameter Estimation Method for Surface-Mounted
  Permanent Magnet Synchronous Motors Considering Voltage Source Inverter
  Nonlinearity", IEEE Access, 2023:
  https://www.researchgate.net/publication/368516257_Electrical_Parameter_Estimation_Method_for_Surface-Mounted_Permanent_Magnet_Synchronous_Motors_Considering_Voltage_Source_Inverter_Nonlinearity
- NIST, "The temperature coefficient of resistance of copper":
  https://nvlpubs.nist.gov/nistpubs/bulletin/07/nbsbulletinv7n1p71_A2b.pdf

## Why The Existing Running Estimator Is Not Accurate Enough

The voltage equation in alpha-beta form is:

```text
u = Rs * i + L * di/dt + e
```

The current Simulink diagnostic estimator assumes low-speed or standstill:

```text
e ~= 0
Rs ~= (u dot i - L * i dot di/dt) / (i dot i)
```

This breaks during normal startup or running because back-EMF is no longer
negligible. The estimator then folds back-EMF and inverter voltage errors into
Rs, which is why `Rs_inst` can hit the clamp while `Rs_valid` remains false.

For the PC-host implementation, the better target is not an instantaneous
sample-by-sample estimator. It should be a short controlled test and a batch
fit over many samples.

## Recommended Rs Algorithm

Use differential multi-level least squares at standstill.

For each test level, after the current has settled:

```text
V_eff = Rs * I + V_offset
```

Collect multiple positive and negative current points:

```text
(I_1, V_1), (I_2, V_2), ..., (I_N, V_N)
```

Fit:

```text
V = Rs * I + b0 + bsign * sign(I)
```

The slope is Rs. The constant intercept `b0` absorbs residual voltage offset.
The `bsign` term absorbs current-direction-dependent voltage error such as
dead time and MOSFET/body-diode drop. This matters because a pure
`V = Rs * I + b` fit can fold sign-dependent inverter error into the Rs slope.
The sign term becomes smaller when the firmware provides a better effective or
measured terminal voltage.

Use both polarities:

```text
I = [-I3, -I2, -I1, I1, I2, I3]
```

Avoid points too close to zero current because ADC offset and dead-time dominate
there. Avoid too-large current because winding heating changes Rs during the
test.

For this motor's current parameters:

```text
Rs ~= 6.97 ohm
L  ~= 5.35 mH
tau = L / Rs ~= 0.77 ms
```

The electrical transient settles quickly, but the firmware should still discard
the first 20 ms to 50 ms of each step to cover current-loop, PWM, filter, and
serial timing effects.

## Test Sequence

### Stage 0: Calibration

Before estimating motor parameters:

- Calibrate current-sensor offset with PWM disabled.
- Verify current sign, phase order, and Clarke/Park sign.
- Verify Vbus scaling.
- Record board temperature or motor temperature if available.
- Ensure motor is unloaded and mechanically safe.

### Stage 1: Rs Standstill Test

Preferred firmware behavior:

1. Disable speed loop and normal sensorless startup state machine.
2. Enter `ID_RS` mode.
3. Apply a fixed electrical vector or per-phase injection level.
4. Wait for settling.
5. Stream samples tagged with the current test level.
6. Repeat for positive and negative levels.
7. Return PWM to safe state.

Recommended levels for first implementation:

```text
I_levels = [-0.6, -0.4, -0.25, 0.25, 0.4, 0.6] A
settle_time = 50 ms
capture_time = 50 ms
```

These values should be treated as tunable. If the motor heats quickly, reduce
current or shorten the test. If the fit is noisy, increase capture time.

### Stage 2: PC Host Batch Fit

The host-side implementation is:

```text
02-Embedded_Code/PC_Tool/parameter_identification.py
```

The PC GUI now exposes a conservative first integration point: the `Rs` button
loads an identification CSV and runs the host-side estimator. It does not yet
send automatic identification commands or write the result back to firmware.

The MATLAB-side implementation is:

```text
01-Simulink/ParameterIdentification/estimatePmsmRs.m
```

The Simulink streaming implementation is in the 1-1 model:

```text
PMSM_NFLUX_v1_1/FOC/current_loop/Rs_Standstill_ID
```

This block calls:

```text
01-Simulink/ParameterIdentification/rsStandstillIdStep.m
```

It is separate from the older `Rs_Identification` diagnostic block. The older
block estimates an instantaneous running value from alpha-beta voltage/current.
`Rs_Standstill_ID` is the production-oriented standstill identifier: it receives
tagged samples, discards settling samples, groups by level, fits
`V = Rs * I + b0 + bsign * sign(I)`, and checks holdout validation residuals.

Use the MATLAB implementation first while the PC host workflow is still under
development:

```matlab
addpath("01-Simulink/ParameterIdentification")
result = estimatePmsmRs("capture_rs.csv");
disp(result.RsAtReferenceOhm)
```

It accepts either a table or a CSV path and returns the same quality metrics as
the PC implementation: Rs, Rs normalized to the reference temperature, offset,
sign-dependent voltage term, fit residuals, holdout validation residual, and
rejection counts by reason.

Public entry points:

```text
estimate_rs(records, config=None)
estimate_rs_from_csv(csv_path, config=None)
```

For each level:

1. Drop settling samples using `time_s` and `level_settle_time_s`.
2. Compute the median or trimmed mean of current and effective voltage.
3. Reject invalid samples:
   - non-finite values
   - `id_valid = 0`
   - current below threshold
   - speed not near zero
   - PWM saturation or duty near the rail
   - Vbus outside valid range
4. Fit `V = Rs * I + b0 + bsign * sign(I)`.
5. Report:
   - `Rs`
   - intercept `b0`
   - sign-dependent voltage term `bsign`
   - temperature-corrected `Rs` at the reference temperature
   - sample count
   - rejected sample count by reason
   - R-squared or normalized residual
   - positive/negative asymmetry
   - holdout validation RMSE if validation levels are present

The module reads voltage fields in this priority order:

```text
id_voltage_eff
id_voltage_meas
terminal_voltage
id_voltage_cmd
Ud / ud
```

`id_voltage_eff` should be the firmware's best estimate of the voltage that
actually reached the motor after bus-voltage scaling, duty limiting, and known
inverter compensation. `id_voltage_cmd` is accepted as a fallback but is less
accurate.

The preferred field names are:

```text
id_level
id_current_meas
id_voltage_eff
speed
time_s
id_valid
temperature_c
```

For the Simulink `Rs_Standstill_ID` subsystem, the input ports are:

```text
enable
reset
finish
sample_valid
id_level
id_current
id_voltage
speed
temperature_c
pwm_saturated
id_role
```

The output ports are:

```text
Rs_hat
Rs_20C
offset_v
sign_v
valid
status
fit_rmse
val_rmse
level_count
sample_count
reject_count
```

Status codes:

```text
 1 = valid estimate
 0 = idle / collecting
-1 = not enough valid fit levels
-2 = singular fit
-3 = Rs outside configured range
-4 = fit residual too high
-5 = validation residual too high
```

If `id_level` is not present, the estimator groups samples by current-reference
fields:

```text
id_current_ref
Id_ref
id_ref
current_ref
```

This lets a CSV exported from the existing diagnostic host format work as long
as the firmware holds `Id_ref` constant for each Rs test level.

It also accepts existing diagnostic names where useful:

```text
Id / id
Ud / ud
FluxWm
```

Accept the result only when:

```text
valid_points >= 4
samples_per_level >= 3
abs(speed_rpm) < small_threshold
0.1 ohm < Rs < 50 ohm
R_squared >= 0.995
fit_residual is below threshold
positive_negative_asymmetry is below threshold
holdout_validation_residual is below threshold when validation data exist
```

### Stage 3: Validation

After estimating Rs:

1. Re-run one held-out injection level that was not used in the fit, or tag one
   level as `id_role = validation`.
2. Predict current or voltage from the fitted Rs.
3. Compare prediction error.
4. Only allow saving to configuration if validation passes.

## Required Firmware/Telemetry Additions

The current host protocol only has:

```text
RUN=1
RUN=0
SPD=...
```

Add identification commands:

```text
ID=STOP
ID=RS_START
ID=RS_LEVEL,<index>
ID=RS_ABORT
```

Or, better, let firmware run the entire sequence:

```text
ID=RS_AUTO
```

Add telemetry fields for the identification mode:

```text
id_mode
id_state
id_level
id_valid
id_role
id_voltage_eff
id_voltage_cmd
id_current_meas
temperature_c
pwm_saturated
rs_hat_firmware_optional
```

For host-side Rs computation, the minimum useful data are:

```text
time_s
ia, ib, ic
vbus
Tcmp1, Tcmp2, Tcmp3
Id, Iq
Ud, Uq
temperature_c
FOC_state
id_state
id_level
id_role
id_valid
pwm_saturated
```

The PC host does not need 10 kHz streaming for steady-state Rs. It does need
unambiguous test-state tags and enough samples after settling.

## Voltage Handling

The biggest accuracy risk is using commanded voltage as if it were actual motor
terminal voltage.

The first implementation can use:

```text
V_cmd ~= duty * Vbus
```

but the PC host should prefer a firmware-provided `id_voltage_eff` and fit both
an offset term and a `sign(I)` term. The reported `sign_voltage_v` is not a
motor parameter; it is a warning about inverter voltage distortion in the test
data. Later, improve with:

- dead-time voltage compensation,
- measured phase voltage if hardware is added,
- board resistance subtraction,
- MOSFET voltage drop model,
- using differential two-level voltage/current slopes rather than a single point.

## Temperature Handling

Copper resistance changes approximately linearly with winding temperature:

```text
R(T) = R(T0) * (1 + alpha * (T - T0))
alpha_copper ~= 0.00393 / degC
```

So a 25 degC temperature rise changes Rs by about 9.8 percent. Accurate Rs
identification must record temperature or at least record the test time and avoid
long heating tests. The current host module reports both the measured-test
temperature result and `rs_at_reference_ohm` normalized to 20 degC by default.

## What To Do Next

1. Keep the current Simulink `Rs_Identification` subsystem as a diagnostic only.
2. Add a dedicated `ID_RS` firmware state rather than using normal FOC running.
3. Extend the serial protocol with identification state and level fields.
4. Use saved CSV data to tune the host fit thresholds against real captures.
5. Only after the CSV workflow is reliable, add a GUI button for automatic Rs
   identification and parameter saving.
