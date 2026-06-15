# PMSM_NFLUX 参数地图

本文档记录 `PMSM_NFLUX_v1_1` 当前数据字典 `PMSM_NFLUX.sldd` 的参数边界、代码生成存储类和上板标定含义。当前字典已按参考 `BLDC_SMO` 工程的思路精简：模型需要的标定量保留为 `Simulink.Parameter`，通过 Custom Storage Class `Struct` 打包生成 C 结构体；不需要导出给 MCU 的推导量、旧启动阈值和重复信号对象已移出数据字典。

## 代码生成原则

字典里的参数分三类：

| 类别 | 字典形式 | 代码生成策略 |
|---|---|---|
| 上板标定参数 | `Simulink.Parameter` | `StorageClass = Custom`，`CustomStorageClass = Struct` |
| 固定设计/仿真参数 | 普通数值或 `Simulink.Parameter` | `Auto` 或内联常量 |
| 调试信号对象 | `Simulink.Signal` | 需要导出的信号使用 `ExportedGlobal` |

当前不再把所有可见参数都设成 `ExportedGlobal`。这样生成代码不会散落大量 `extern real32_T xxx`，而是接近参考工程：

```c
extern curr_kpki_type curr_kpki;
extern handover_cfg_type handover_cfg;
extern motor_type motor;
extern nflux_obs_type nflux_obs;
extern spd_kpki_type spd_kpki;
```

`PLL_OmegaLimit` 保持 `Auto`。它在 PID 块里被用作 `-PLL_OmegaLimit` 表达式，若强行放入结构体可调参数，子系统代码生成会报错。当前处理方式是接受其作为保护限幅常量内联。

## 结构体参数

### `motor`

| 字段 | 单位 | 是否标定 | 含义 |
|---|---:|---|---|
| `Rs` | ohm | 是 | 定子相电阻 |
| `L` | H | 是 | 表贴 PMSM 当前使用的公共相电感 |
| `Pn` | pole pairs | 视情况 | 电机极对数 |
| `flux` | Wb | 是 | 永磁体磁链 |

说明：当前模型只保留 `L`，不再在数据字典中保留未被模型引用的 `Ld/Lq`。如果后续切换到凸极 PMSM 或需要独立 d/q 轴参数，再重新引入 `Ld/Lq`。

### `curr_kpki`

| 字段 | 单位 | 是否标定 | 含义 |
|---|---:|---|---|
| `curr_d_kp` | V/A | 是 | d 轴电流环比例增益 |
| `curr_d_ki` | V/(A*s) | 是 | d 轴电流环积分增益 |
| `curr_q_kp` | V/A | 是 | q 轴电流环比例增益 |
| `curr_q_ki` | V/(A*s) | 是 | q 轴电流环积分增益 |

### `spd_kpki`

| 字段 | 单位 | 是否标定 | 含义 |
|---|---:|---|---|
| `spd_kp` | A/rpm | 是 | 速度环比例增益，当前速度误差按 rpm 理解 |
| `spd_ki` | A/(rpm*s) | 是 | 速度环积分增益，当前速度误差按 rpm 理解 |

### `nflux_obs`

| 字段 | 单位 | 是否标定 | 含义 |
|---|---:|---|---|
| `Gamma` | 依观测器公式 | 是 | 非线性磁链观测器校正增益 |
| `PLL_Kp` | rad/s per rad | 是 | PLL 比例增益 |
| `PLL_Ki` | rad/s^2 per rad | 是 | PLL 积分增益 |
| `LPF_K` | ratio | 是 | 观测速度一阶低通滤波系数 |

### `handover_cfg`

| 字段 | 单位 | 是否标定 | 含义 |
|---|---:|---|---|
| `iq_handover` | A | 是 | 角度接管阶段保持的 q 轴电流 |
| `iq_ref_slew_up` | A/s | 是 | q 轴电流给定上升斜率限制 |
| `iq_ref_slew_down` | A/s | 是 | q 轴电流给定下降斜率限制 |
| `theta_handover_slew_limit` | electrical rad/s | 是 | case4 角度补偿最大变化率 |

## 固定设计和仿真参数

| 参数名 | 单位 | 代码生成策略 | 含义 |
|---|---:|---|---|
| `Ts` | s | `Auto` | FOC 主控制周期 |
| `Udc` | V | `Auto` | 仿真默认直流母线电压；上板时应优先使用 FOC 输入端口实时母线电压 |
| `PLL_OmegaLimit` | electrical rad/s | `Auto` | PLL 输出电角速度保护限幅，当前内联 |
| `PWM_HalfPeriod` | count | 普通数值 | PWM 半周期计数 |
| `Tpwm` | count | 普通数值 | SVPWM 使用的 PWM 计数基准 |
| `J` | kg*m^2 | 普通数值 | 仿真 plant 转动惯量 |
| `B` | N*m*s/rad | 普通数值 | 仿真 plant 粘性摩擦系数 |
| `load_torque` | N*m | 普通数值 | 仿真 plant 外部负载转矩 |

## 信号对象

| 名称 | 类型 | 存储类 | 含义 |
|---|---|---|---|
| `i_alpha` | `Simulink.Signal` | `Auto` | alpha 轴电流内部信号对象 |
| `i_beta` | `Simulink.Signal` | `Auto` | beta 轴电流内部信号对象 |
| `u_alpha` | `Simulink.Signal` | `Auto` | alpha 轴电压内部信号对象 |
| `u_beta` | `Simulink.Signal` | `Auto` | beta 轴电压内部信号对象 |
| `FluxWm` | `Simulink.Signal` | `ExportedGlobal` | 导出的观测机械速度调试量 |
| `FluxTheta` | `Simulink.Signal` | `ExportedGlobal` | 导出的观测电角度调试量 |

`FluxWm` 和 `FluxTheta` 不作为 FOC 普通输出口导出，而是作为全局调试信号导出，风格上对应参考工程的 `SMOWm` 和 `SMOTheta`。

## 已移出的旧条目

以下条目已从 `PMSM_NFLUX.sldd` 移出，因为当前模型没有直接引用，或更适合留在设计计算脚本/文档中，而不是进入最终 MCU 参数接口：

```text
Kt
Ld
Lq
MotorOnOff_init
OpenLoopHold_init
PLL_BW
PLL_Zeta
Speed_ref_init
Ts_speed
VdqLimit
VoltageMargin
current_bw
handover_stable_ticks
iq_handover_slew
iq_open_loop
iq_ref_limit
iq_ref_max_handover
iq_ref_min_handover
iq_run_default
omega_handover_min
phase_err_limit
rpm_to_radps
sim_stop_time
speed_bw
speed_loop_delay_ticks
ialpha
ibeta
ualpha
ubeta
```

后续如果确实需要重新标定其中某个量，应先确认模型中有实际引用，再决定是作为结构体可调参数、`Auto` 内联参数，还是只保留在设计计算脚本中。

## 当前验证状态

2026-06-13 已完成以下检查：

1. `PMSM_NFLUX.sldd` 从 61 个条目精简为 32 个条目。
2. `PMSM_NFLUX_v1_1` 模型 update 通过。
3. FOC 子系统代码生成通过。
4. 生成头文件中参数已按 `curr_kpki`、`spd_kpki`、`motor`、`nflux_obs`、`handover_cfg` 组织。
5. 使用 ARM GCC 对生成的 C 文件做语法检查通过。
