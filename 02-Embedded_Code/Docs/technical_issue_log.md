# MyFOC_NFlux technical issue log

This file records firmware, protocol, control, and measurement issues found
during bring-up. Visual polish and layout-only notes are intentionally excluded.

## 串口命令偶发无响应

- Symptom: `RUN=1`, `RUN=0`, or `SPD=x` sometimes required several button
  clicks before the firmware reacted.
- Root cause found: single-byte UART interrupt receive was vulnerable to loss
  under 2 Mbps telemetry traffic and 10 kHz FOC interrupt load.
- Fix applied: USART3 RX was changed to DMA circular receive. The main loop now
  polls the DMA write pointer and parses complete ASCII command lines.
- Host-side mitigation: RUN/STOP/SPD commands are sent several times with a
  short interval after a button click.
- Verification: unit tests check that the firmware starts `HAL_UART_Receive_DMA`
  and uses `DMA_CIRCULAR`.

## 低速给定反转和抖动

- Symptom: commanding low speed such as 100 rpm could make the motor reverse,
  accelerate unexpectedly, and shake.
- Root cause found: the generated sensorless startup process transitions from
  an open-loop startup region around 600 rpm into closed loop. A much lower
  closed-loop target can create a large speed error at handover and destabilize
  the observer/control loop.
- Fix applied: software speed command range was clamped to `120..1800 rpm`.
- Remaining risk: the current sensorless startup strategy is still not designed
  for very low speed operation. Lower speeds should be tested gradually.

## 高速约 1220 rpm 上不去

- Symptom: after raising the software speed limit, the observed speed stayed
  near 1220 rpm instead of reaching the command.
- Evidence from code: speed command path is clamped at 1800 rpm, but the FOC
  model limits speed-loop `Iq_ref` to `+/-3 A` and d/q voltage commands to about
  `+/-12.47 V`.
- Analysis: with the current model parameters (`Rs=6.97 ohm`,
  `L=5.35 mH`, `flux=0.016884 Wb`, `Pn=4`), a loaded high-speed point can hit
  the voltage equation before the requested speed is reached.
- Next diagnostic action: add telemetry for `Id/Iq`, `Id_ref/Iq_ref`, `Ud/Uq`,
  PWM compare values, and FOC state. This has now been added to the protocol so
  the actual saturation source can be checked from captured data.

## Telemetry frame bandwidth

- Symptom risk: increasing telemetry from 7 floats to 17 floats increases each
  JustFloat frame from 32 bytes to 72 bytes.
- Design decision: keep the existing best-effort TX DMA policy. If USART3 is
  busy, the firmware skips the current telemetry frame instead of blocking the
  10 kHz ADC/FOC interrupt.
- Consequence: frame rate will drop compared with 7-float telemetry, but control
  timing is protected.
