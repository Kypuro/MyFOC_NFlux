# MyFOC_NFlux 上位机协议

## 串口参数

- USART：USART3，CH340 Type-C 转 USB
- 波特率：`2000000`
- 数据位：8
- 校验：None
- 停止位：1

## STM32 -> PC 遥测

STM32 保持 VOFA JustFloat 兼容格式。当前新固件发送 17 路诊断帧：

```text
float[17] + 00 00 80 7F
```

每个 `float` 为 little-endian IEEE754 单精度。

| 序号 | 信号 |
| --- | --- |
| 0 | `ia` |
| 1 | `ib` |
| 2 | `ic` |
| 3 | `FluxTheta` |
| 4 | `FluxWm` |
| 5 | `RefSpeed` |
| 6 | `rtU.v_bus` |
| 7 | `Id` |
| 8 | `Iq` |
| 9 | `Id_ref` |
| 10 | `Iq_ref` |
| 11 | `Ud` |
| 12 | `Uq` |
| 13 | `Tcmp1` |
| 14 | `Tcmp2` |
| 15 | `Tcmp3` |
| 16 | `FOC_state` |

上位机仍兼容旧版 `float[7]`、`float[6]` 和过渡期 `float[8]` 帧；旧版固件没有诊断量时，对应通道会显示为空值。

## PC -> STM32 控制

PC 下发 ASCII 行命令，命令以 `\n` 或 `\r\n` 结束。

```text
RUN=1
RUN=0
SPD=600
```

命令含义：

- `RUN=1`：允许电机运行。offset 已完成且 PWM 未启动时，主循环会启动三相 PWM。
- `RUN=0`：停止电机，关闭三相 PWM 输出。
- `SPD=600`：设置速度给定，单位沿用模型中的速度单位，当前按 rpm 使用。

速度给定会在 STM32 端限制到 `120..1800`。当前无感启动/闭环切换策略在低速区仍可能失锁，低速调试需逐步降低速度并观察电流和磁链角。
