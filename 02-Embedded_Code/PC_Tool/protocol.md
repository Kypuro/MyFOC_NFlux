# MyFOC_NFlux 上位机协议

## 串口参数

- USART：USART3，CH340 Type-C 转 USB
- 波特率：`2000000`
- 数据位：8
- 校验：None
- 停止位：1

## STM32 -> PC 遥测

STM32 保持 VOFA JustFloat 兼容格式：

```text
float[8] + 00 00 80 7F
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
| 7 | `vbus_raw` |

上位机仍兼容旧版 `float[6]` 帧，但旧版固件没有 `ib/ic`，三相电流窗口只能显示 `ia`。

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

速度给定会在 STM32 端限制到 `0..1200`。
