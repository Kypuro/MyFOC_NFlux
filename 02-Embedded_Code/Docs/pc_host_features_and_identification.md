# PC host features and parameter identification notes

## Current PC host scope

The PC host is a PySide6 + pyqtgraph serial monitor and control tool for the
MyFOC_NFlux firmware. It keeps the firmware protocol simple and compatible with
VOFA JustFloat telemetry.

## Serial connection

- Uses USART3 through the CH340 USB serial adapter.
- Default baud rate is `2000000`.
- Supports manual port refresh and automatic port list refresh every 1 second.
- Connect and disconnect are handled from the left sidebar.
- Serial read runs in a worker thread and decoded frames are passed to the UI by
  a queue, so UI drawing does not block the serial read loop.

## Telemetry protocol

STM32 sends little-endian single precision floats followed by the VOFA frame
tail. New firmware sends the 17-float diagnostic frame:

```text
float[17] + 00 00 80 7F
```

The current channels are:

| Index | Signal | Unit / meaning |
| --- | --- | --- |
| 0 | `ia` | A phase current, A |
| 1 | `ib` | B phase current, A |
| 2 | `ic` | C phase current, A |
| 3 | `FluxTheta` | flux angle, rad, wrapped to `0..2*pi` in cards |
| 4 | `FluxWm` | observed mechanical speed, rpm |
| 5 | `RefSpeed` | speed command, rpm |
| 6 | `v_bus` | DC bus voltage, V |
| 7 | `Id` | d-axis current, A |
| 8 | `Iq` | q-axis current, A |
| 9 | `Id_ref` | d-axis current reference, A |
| 10 | `Iq_ref` | q-axis current reference, A |
| 11 | `Ud` | d-axis voltage command, V |
| 12 | `Uq` | q-axis voltage command, V |
| 13 | `Tcmp1` | TIM1 compare value for phase A |
| 14 | `Tcmp2` | TIM1 compare value for phase B |
| 15 | `Tcmp3` | TIM1 compare value for phase C |
| 16 | `FOC_state` | generated model startup/run state |

The parser still accepts older `float[7]`, `float[6]`, and transitional
`float[8]` frame formats for compatibility.
Frames are rejected when values are not finite or outside the basic plausibility
range.

## Real-time display

- Top cards show the latest value of each telemetry channel.
- The plot area is a 2x2 layout:
  - three phase currents,
  - flux angle,
  - speed,
  - DC bus voltage.
- The current plot shows `ia`, `ib`, and `ic` together.
- The speed plot shows observed speed and reference speed together.
- The flux angle plot displays the wrapped `0..2*pi` sawtooth waveform.
- Each plot has its own X time window setting, so current, angle, speed, and
  voltage can use different viewing ranges.
- Mouse wheel zoom and drag pan operate per plot.
- Manual zoom disables follow-latest for that plot only; other plots continue
  to update normally.
- Y auto-scale is per plot and leaves padding around the visible data.
- Grid, pause drawing, reset view, clear data, and channel visibility are
  available from the sidebar.
- Channel visibility can also be toggled from the legend.
- Light and dark themes are supported.

## Control commands

PC sends ASCII line commands ending with `\n`:

```text
RUN=1
RUN=0
SPD=600
```

Implemented controls:

- `RUN=1`: request motor start.
- `RUN=0`: request motor stop.
- `SPD=x`: set target speed.
- Custom command entry for manual protocol testing.

The speed command is clamped in both the host and the firmware. The current
software command range is:

```text
120..1800 rpm
```

The host repeats `RUN` and `SPD` commands briefly after a button click to reduce
the effect of serial receive timing and make button actions more reliable.

## Data logging and demo mode

- CSV logging writes files under `02-Embedded_Code/PC_Tool/data`.
- CSV columns are:

```text
time_s, ia, ib, ic, FluxTheta, FluxWm, RefSpeed, vbus,
Id, Iq, Id_ref, Iq_ref, Ud, Uq, Tcmp1, Tcmp2, Tcmp3, FOC_state
```

- Demo mode generates local simulated frames so the UI and plotting behavior can
  be tested without a board.

## Reserved but not active

The UI contains disabled controls for future work:

- position mode,
- trajectory profile settings,
- `Rs` identification,
- `Ld/Lq` identification,
- flux linkage identification.

These controls are placeholders only. The firmware protocol does not yet
implement the required identification commands or diagnostic telemetry.

## Current known limitations

- The firmware currently reports only 7 telemetry floats. This is enough for
  basic observation but not enough to diagnose high-speed voltage saturation
  directly.
- The FOC model limits speed-loop output to `Iq_ref = +/-3 A`.
- The generated FOC model limits each d/q voltage command to about `+/-12.47 V`.
- The current model does not implement field weakening. With the present motor
  parameters and 24 V bus, speeds near 2000 rpm are unlikely under load unless
  voltage utilization, motor parameters, or field weakening are improved.
- `FluxWm` is treated by the host as mechanical rpm. Some firmware comments may
  still describe it as electrical rad/s and should be corrected when the
  telemetry format is next changed.

## Can parameter identification start now?

Yes, but it should start with controlled offline tests, not with the current
closed-loop speed run.

Before automated identification is added to the host, first add firmware support
for a small identification mode and extra telemetry. The minimum useful
diagnostic set is:

```text
ia, ib, ic,
FluxTheta, FluxWm, RefSpeed, v_bus,
Id, Iq, Id_ref, Iq_ref,
Ud, Uq,
Tcmp1, Tcmp2, Tcmp3,
FOC_state
```

Recommended identification order:

1. Current and voltage scaling

   Verify `CURRENT_ADC_TO_AMP`, current offset, current sign, phase order, and
   `VBUS_ADC_SCALE`. Bad scaling makes every later identified parameter wrong.

2. Stator resistance `Rs`

   Lock the rotor or keep it stationary, inject a small DC current/vector, wait
   for current to settle, then estimate:

   ```text
   Rs = U / I
   ```

   Use several current levels and average the linear region. Stop if current or
   temperature rises too much.

3. Phase inductance `L`, or `Ld/Lq`

   With the rotor locked, apply a small voltage step or current step and fit the
   current transient:

   ```text
   i(t) = I_final * (1 - exp(-t * Rs / L))
   L = tau * Rs
   ```

   For `Ld/Lq`, repeat with the injected vector aligned to d and q axes.

4. Flux linkage `flux`

   Best measured by back-EMF with the motor spun externally, or estimated from a
   stable no-load run after `Rs` and `L` are known:

   ```text
   flux ~= (Uq - Rs * Iq - omega_e * Ld * Id) / omega_e
   omega_e = mechanical_rad_per_sec * pole_pairs
   ```

5. Optional mechanical parameters

   Inertia and friction can be estimated later from speed step responses. They
   are not required before fixing the electrical model and observer parameters.

## Next implementation step

The next useful software change is to extend the telemetry frame and host plots
with `Id/Iq`, `Iq_ref`, `Ud/Uq`, and PWM compare values. This will show whether
the 1220 rpm ceiling is caused by speed-loop current saturation, voltage
saturation, bus voltage sag, observer loss, or PWM clipping.
