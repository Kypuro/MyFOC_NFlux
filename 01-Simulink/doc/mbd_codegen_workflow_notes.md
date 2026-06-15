
# PMSM_NFLUX MBD 与代码生成流程记录

本文档记录 `PMSM_NFLUX_v0` 当前从 Simulink 仿真模型走向 STM32 代码生成的工作流程、已经完成的内容、遇到的问题、处理原则和后续步骤。用于换电脑或继续开发时快速恢复上下文。

## 1. 当前目标

当前项目目标是基于 `PMSM_NFLUX_v0.slx` 建立一套可用于 STM32 的无感 FOC 控制算法模型。

代码生成边界暂定为：

```text
PMSM_NFLUX_v0/FOC
```

只生成 FOC 控制器代码，不生成顶层仿真 plant。

FOC 子系统输入：

| 信号 | 含义 |
|---|---|
| `VDC` | 母线电压 |
| `Speed_ref` | 速度指令 |
| `MotorOnOff` | 电机使能开关 |
| `OpenLoopHold` | 开环保持开关 |
| `ia` | A 相电流 |
| `ib` | B 相电流 |
| `ic` | C 相电流 |

FOC 子系统输出：

| 信号 | 含义 |
|---|---|
| `Tcmp1` | A 相 PWM 输出/比较值 |
| `Tcmp2` | B 相 PWM 输出/比较值 |
| `Tcmp3` | C 相 PWM 输出/比较值 |
| `FluxTheta` | 观测器角度 |
| `FluxWm` | 观测速度 |

注意：`Tcmp1/2/3` 需要继续确认最终单位是 PWM compare count 还是 0~1 占空比。

## 2. 当前建议路线

整体顺序建议为：

```text
1. Simulink 仿真中跑稳无感启动和接管
2. 建立数据字典
3. 整理参数地图和可标定参数
4. 确定 FOC 子系统代码生成边界
5. 子系统代码生成
6. 查看生成 C 接口
7. 再考虑低速运转功能和参数辨识功能
8. 最后接 STM32 工程和上板调试
```

不建议在算法还未整理清楚时直接烧录 STM32。原因是上板后调试手段有限，很多问题在 Simulink 里更容易定位。

## 3. 已完成内容

### 3.1 数据字典建立

已建立：

```text
PMSM_NFLUX.sldd
```

并将 `init_PMSM_NFLUX.m` 中的主要参数同步进数据字典。

已验证：

```text
clear workspace 后，模型仍能 update diagram 和仿真
```

说明模型已经不再强依赖 base workspace。

### 3.2 参数地图

建议建立中文参数说明文档：

```text
doc/parameter.md
```

当前数据字典已经按代码生成接口整理，不再采用“所有参数都平铺在 `Design Data` 并全部导出”的早期策略。分类仍在 `doc/parameter.md` 中维护，代码生成可调参数则通过 Custom Storage Class `Struct` 归组。

建议分类如下：

```text
1. 固定设计参数
2. 电机参数
3. 电源和限制参数
4. 电流环和速度环控制参数
5. 观测器和 PLL 参数
6. 启动和接管参数
7. 信号对象
```

### 3.3 可调参数 Simulink.Parameter 化和结构体归组

为了代码生成和后续上板标定，当前可调参数使用：

```matlab
Simulink.Parameter
```

并设置为结构体存储类：

```text
StorageClass = Custom
CustomStorageClass = Struct
StructName = curr_kpki / spd_kpki / motor / nflux_obs / handover_cfg
```

不是所有参数都需要导出为全局变量。判断原则：

```text
需要上板调试的参数 -> Custom / Struct
不需要上板调试的固定参数 -> Auto / 内联常量
仿真 plant 参数 -> 普通数值或 Auto
调试观测信号 -> Simulink.Signal / ExportedGlobal
```

当前结构体参数包括：

```text
motor: Rs, L, Pn, flux
curr_kpki: curr_d_kp, curr_d_ki, curr_q_kp, curr_q_ki
spd_kpki: spd_kp, spd_ki
nflux_obs: Gamma, PLL_Kp, PLL_Ki, LPF_K
handover_cfg: iq_handover, iq_ref_slew_up, iq_ref_slew_down, theta_handover_slew_limit
```

当前保持 Auto 或普通数值的参数包括：

```text
Ts
Udc
PWM_HalfPeriod
Tpwm
PLL_OmegaLimit
J
B
load_torque
```

## 4. case4 角度接管问题与修正

### 4.1 原问题

之前发现：

```text
case4 使用逐渐切换到观测器角度时，速度波动很大；
但 case4 直接使用开环角，然后 case5 直接切到观测器角，速度波动反而小。
```

仿真对比结果：

```text
旧错误渐变 case4：速度波动约 909 rpm
纯开环 case4：速度波动约 248 rpm
修正后 case4：速度波动约 239.5 rpm
```

### 4.2 根因

旧渐变逻辑使用正向 `0 ~ 2π` 差值去插值两个角度。角度是周期变量，不能直接按普通数值插值。

典型问题：

```text
theta_open = 0.10 rad
theta_hat  = 6.20 rad
```

普通相减：

```text
theta_hat - theta_open = 6.10 rad
```

但真实最短角度差应该是：

```text
6.10 - 2π = -0.183 rad
```

旧逻辑会把很小的跨零误差误认为接近一整圈的正向误差，从而在 case4 中持续注入很大的等效角速度扰动。

### 4.3 修正逻辑

新增 case4 子系统：

```text
ThetaShortestBlend
```

逻辑为：

```text
delta_short = wrapToPi(theta_hat - theta_open)
correction_raw = alpha * delta_short
correction_limited = rateLimit(correction_raw, theta_handover_slew_limit)
theta_fd = wrapTo2Pi(theta_open + correction_limited)
```

等价 Simulink 计算：

```text
delta_short = mod(theta_hat - theta_open + pi, 2*pi) - pi
theta_fd = mod(theta_open + correction_limited, 2*pi)
```

当前参数：

```matlab
theta_handover_slew_limit = single(5.0);
```

含义：

```text
case4 角度补偿最大变化率，单位 electrical rad/s
```

根据扫描结果：

```text
0 rad/s   -> case4 实际转速峰峰值约 248.1 rpm
5 rad/s   -> case4 实际转速峰峰值约 239.5 rpm
10/20/50  -> 波动变大
```

因此当前采用 `5 rad/s`。



## 5. 数据字典和代码生成参数问题

### 5.1 代码生成警告示例

生成 FOC 子系统代码时遇到警告：

```text
The generated code will inline the numeric value of the expression '-PLL_OmegaLimit'
because block ... only supports double-precision tunable parameter expressions.
The code for this block will not use the tunable variables PLL_OmegaLimit.
```

### 5.2 含义

模型某个 block 参数写成了：

```matlab
-PLL_OmegaLimit
```

这不是独立参数，而是参数表达式。

代码生成器提醒：

```text
这个表达式不会作为可调参数保留，
而是直接计算成数值写死进 C 代码。
```

如果 `PLL_OmegaLimit` 需要上板可调，这就是问题。

如果 `PLL_OmegaLimit` 不需要上板可调，这个警告可以接受。

### 5.3 处理原则

判断方式：

```text
这个参数是否需要上板调试？
```

如果需要上板调试：

```text
不要在 block 参数里写表达式。
把表达式拆成独立数据字典参数。
```

例如：

```matlab
PLL_OmegaLimit_Neg = -PLL_OmegaLimit;
```

然后 block 中写：

```text
LowerSaturationLimit = PLL_OmegaLimit_Neg
```

如果不需要上板调试：

```text
接受内联，或将参数 StorageClass 改为 Auto。
```

对当前项目，`PLL_OmegaLimit` 更像保护限幅，不一定需要上板频繁调，因此可接受内联。

## 6. FOC 子系统代码生成流程

推荐使用图形界面，不优先用脚本。

### 6.1 确认代码生成边界

边界：

```text
PMSM_NFLUX_v0/FOC
```

只生成该子系统，不生成顶层模型。

不进入代码生成的内容：

```text
Surface Mount PMSM
逆变器平均值模型
Signal Builder
Scope
仿真负载
顶层 plant
```

### 6.2 设置 FOC 子系统

在 Simulink 中：

```text
右键 FOC 子系统
Block Parameters (Subsystem)
勾选 Treat as atomic unit
```

如界面中有代码生成相关设置，可设置：

```text
Function packaging: Nonreusable function
Function name: PMSM_NFLUX_FOC_step
File name: PMSM_NFLUX_FOC
```

### 6.3 模型配置

打开：

```text
Model Settings
```

建议检查：

```text
Solver:
  Type: Fixed-step
  Solver: discrete / no continuous states
  Fixed-step size: Ts 或 1e-4

Code Generation:
  System target file: ert.tlc
  Language: C
```

### 6.4 生成子系统代码

使用图形界面：

```text
右键 FOC 子系统
C/C++ Code
Build This Subsystem
```

如果提示创建 harness，可以允许。

生成后重点检查：

```text
1. 是否只生成 FOC 控制器代码
2. 是否没有 plant / Scope / Signal Builder
3. 生成的 .h 文件中函数接口是否符合预期
4. 参数是否按期望变成全局变量或常量
```

## 7. 后续要做的事

### 7.1 短期下一步

1. 确认 FOC 子系统根输入端口命名是否统一为 `VDC`、`Speed_ref`、`MotorOnOff`、`OpenLoopHold`、`ia`、`ib`、`ic`。
2. 检查 `.h` 文件中的函数声明、输入输出结构体和参数结构体是否符合 STM32 集成预期。
3. 将生成代码接入 STM32 工程时，只编译控制器源文件和运行时辅助文件，不编译 `ert_main.c`。
4. 参考标准工程的 ADC injected callback，把电流采样、母线电压、`FOC_step()` 和 `TIM1->CCR1/2/3` 更新串起来。

### 7.2 中期工作

1. 整理 FOC 子系统接口数据类型
2. 确认 `Tcmp1/2/3` 是 PWM compare count 还是归一化占空比
3. 确认 `FluxWm` 的单位，并在 STM32 调试输出中标注清楚
4. 建立低速运行策略
5. 建立参数辨识流程：
   - 先 `Rs`
   - 再 `L`
   - 最后 `flux`

### 7.3 上板前检查项

上板前至少确认：

```text
1. 模型清空 workspace 后可 update 和仿真
2. FOC 子系统可单独生成代码
3. 生成代码中无 plant
4. 输入输出接口明确
5. 可调参数列表明确
6. 固定参数不会被误当成可调参数
7. 电流、电压、速度、角度单位明确
8. case4/case5 接管逻辑已通过仿真验证
```

## 8. 当前已知风险

1. `idq_Controller/PID Controller1/Integrator/Discrete/Integrator` 仍有 wrap overflow warning，需要后续检查电流环积分器限幅和抗饱和。
2. `FluxWm` 单位需要在 STM32 调试输出中明确标注。
3. `Tcmp1/2/3` 输出单位仍需确认。
4. 低速无感运行尚未系统设计。
5. 参数辨识功能尚未开始。

## 9. 2026-06-13 数据字典精简和结构体参数组织

本次对 `PMSM_NFLUX.sldd` 做了代码生成接口对齐，目标是让本工程的参数组织方式接近参考 `BLDC_SMO` FOC 工程，同时避免生成代码中出现大量散落的 `extern real32_T xxx`。

### 9.1 当前原则

不再把所有参数都设为 `ExportedGlobal`。参数按用途分为：

```text
需要上板调试的标定参数 -> Simulink.Parameter + Custom / Struct
固定设计参数或保护限幅 -> Auto / 内联常量
仿真 plant 参数 -> 普通数值或 Auto，不进入 MCU 参数接口
调试观测信号 -> Simulink.Signal + ExportedGlobal
```

### 9.2 当前结构体参数

当前生成代码中的全局结构体参数为：

```c
extern curr_kpki_type curr_kpki;
extern handover_cfg_type handover_cfg;
extern motor_type motor;
extern nflux_obs_type nflux_obs;
extern spd_kpki_type spd_kpki;
```

字段分组如下：

```text
curr_kpki:
  curr_d_kp
  curr_d_ki
  curr_q_kp
  curr_q_ki

spd_kpki:
  spd_kp
  spd_ki

motor:
  Rs
  L
  Pn
  flux

nflux_obs:
  Gamma
  PLL_Kp
  PLL_Ki
  LPF_K

handover_cfg:
  iq_handover
  iq_ref_slew_up
  iq_ref_slew_down
  theta_handover_slew_limit
```

对应的 Simulink 数据字典设置不是创建 Bus 结构体，而是参考工程使用的 Custom Storage Class 方式：

```text
StorageClass = Custom
CustomStorageClass = Struct
StructName = curr_kpki / spd_kpki / motor / nflux_obs / handover_cfg
```

这种方式可以保留模型里原来的散参数名，例如 `curr_d_kp`、`curr_q_ki`，同时在 C 代码中生成结构体。

### 9.3 保持 Auto 的参数

`PLL_OmegaLimit` 保持 `Auto`。原因是 PID 块里使用了 `-PLL_OmegaLimit` 这种参数表达式；该块只支持特定形式的可调参数表达式。如果把 `PLL_OmegaLimit` 放进结构体可调参数，子系统代码生成会报错。当前把它作为保护限幅常量内联，符合参考工程中固定限幅常量不一定导出的原则。

`Ts`、`Udc` 也保持 `Auto`。其中 `Udc` 是仿真默认值，上板代码应优先通过 FOC 输入端口读取实时母线电压。

### 9.4 调试信号

`FluxTheta` 和 `FluxWm` 作为 `Simulink.Signal` 保留并设置为 `ExportedGlobal`，用于上板或串口调试时观测角度和速度。它们不再作为 FOC 普通输出口导出，风格上对应参考工程的 `SMOTheta` 和 `SMOWm`。

### 9.5 已验证

本次整理后已验证：

```text
PMSM_NFLUX.sldd: 61 -> 32 entries
PMSM_NFLUX_v1_1: update diagram passed
FOC subsystem: code generation passed
Generated C: ARM GCC syntax check passed
```

生成代码检查重点：

```text
不应再出现一串 curr_d_kp/curr_q_ki/Gamma/PLL_Kp 等散 extern 参数；
应看到 curr_kpki、spd_kpki、motor、nflux_obs、handover_cfg 五个结构体参数。
```
