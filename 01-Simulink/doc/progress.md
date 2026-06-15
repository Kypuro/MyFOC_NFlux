# My_NFLUX 进度记录

## 2026-06-10 21:32:45 +08:00

### 当前阶段

已对 `PMSM_NFLUX.slx` 做静态结构检查。模型目前已经搭出无感 FOC 的主体链路：

- 根模型包含 `Speed_loop` 和主控制 `Subsystem`。
- 主控制内部包含 `Clark`、`Park`、`In_park`、`idq_Controller`、`SVPWM`、`Nonlinear Flux Observer`。
- 状态机 `Subsystem/Chart` 已搭建，包含 `IDLE`、`AlignStage`、`OpenStage`、`ThetaAlign`、`RunStage`。
- 非线性磁链观测器链路为 `i_alpha/u_alpha/i_beta/u_beta -> flux observer -> PLL -> theta/we`。
- `case [3]` 已实现开环速度斜坡到角度的生成。
- `case [4]` 已实现开环角与观测器角的融合过渡，并输出融合后的 `Theta_fd`。
- 顶层已有速度环，速度环采样由 `Function-Call Generator` 触发，周期为 `1e-3`。

### 发现的问题

1. 项目文件夹目前只有 `PMSM_NFLUX.slx`，没有 `.sldd` 数据字典或初始化 `.m` 文件。
2. 模型引用了 `Gamma`、`L`、`Rs`、`Ts`、`flux`、`Pn`、`LPF_K`、`curr_d_kp`、`curr_d_ki`、`Tpwm` 等变量，当前项目内没有可见定义来源。
3. 模型配置仍是普通仿真目标：`SystemTargetFile=grt.tlc`，`FixedStep=auto`，`HardwareBoard=None`，还不是嵌入式代码生成配置。
4. 状态机 `OpenStage` 内存在明显拼写错误风险：
   - 使用了 `ZRest = 1`，但外部信号名是 `ZReset`。
   - 使用了 `Motor_stage = 3`，但外部状态输出名是 `Motor_state`。
5. 状态机部分停机跳转写成了 `[[Motor_OnOff == 0]]`，建议统一为 `[Motor_OnOff == 0]`。
6. `OpenLoopHold` 当前是外部输入，用于控制 `OpenStage -> ThetaAlign` 是否允许切换，不是状态机内部自动生成。

### 下一步建议

1. 先修正状态机拼写问题：`ZRest -> ZReset`，`Motor_stage -> Motor_state`。
2. 建立数据字典或初始化脚本，集中定义电机参数、控制周期、PI 参数、观测器参数和 PWM 参数。
3. 固定仿真步长，确认 `Ts`、电流环采样周期和速度环 `1e-3` 的关系。
4. 给 `theta_fd`、`iq_ref`、`Motor_state`、`NfluxTheta`、`NfluxWm` 加日志或 Scope，跑启动流程仿真。
5. 等仿真流程稳定后，再改嵌入式代码生成配置。

### 参数辨识边界

已知电阻 `Rs` 可直接测量，极对数 `Pn` 已知。在这个前提下，电感和磁链可以做辨识，但不是完全无前提的盲辨识：

- 电感 `L` / `Ld` / `Lq`：适合通过静止注入或锁轴注入辨识，需要电流采样、电压输出和相序正确。
- 磁链 `flux`：通常需要电机旋转后利用电压方程或反电动势估算，低速和静止时可靠性差。
- 对未知电机的辨识顺序应为：电流/电压采样标定 -> `Rs` -> `L` 或 `Ld/Lq` -> 开环/闭环旋转 -> `flux` -> 观测器和 PLL 参数整定。

### 简历项目进度判断

当前项目作为简历项目已经具备主体框架，但还未达到“完整可答辩”的程度。已完成内容偏模型结构搭建，后续重点应放在参数来源、仿真验证、代码生成和上板实验闭环。

### 与参考 FOC 模型的差异

当前 `BLDC_NFLO` 更偏向算法验证模型，采用 `Average-Value Inverter + Surface Mount PMSM`，适合观测器和状态机调试；参考 `foc.slx` 更偏向硬件验证模型，采用 `Universal Bridge + Permanent Magnet Synchronous Machine`，并带 Hall 反馈，更接近实际开关波形和板级调试环境。

## 2026-06-11 关键结论：控制器与 plant 边界

后续硬件代码生成只应导出 FOC 控制算法子系统，电机和逆变器属于仿真 plant，不进入 MCU 代码。电机和逆变器不是“无所谓”，它们不会影响最终导出的控制器结构，但会影响仿真结果是否可信、参数整定是否能迁移到实物、以及观测器/PLL 在仿真中是否表现正常。

当前建议：算法开发阶段优先保持 `BLDC_NFLO` / `My_NFLUX` 的控制器接口清晰；plant 可先用平均值逆变器快速验证 FOC、状态机、观测器逻辑。等控制逻辑稳定后，再用 `foc.slx` 的开关级逆变器和 PMSM plant 做更接近硬件的验证。

## 2026-06-11 PMSM_NFLUX 参数初始化与编译检查

新增 `init_PMSM_NFLUX.m`，集中定义模型当前引用到的控制参数、电机参数、observer 参数、PLL 参数、速度环参数和必需的 `Simulink.Signal` 对象。电机参数按当前 `Surface Mount PMSM` plant 保持一致：`Pn=4`、`Rs=0.2`、`L=3.752e-4`、`flux=0.1194`。

发现并修复模型编译问题：

- Stateflow Chart 内部把 `MotorOnOff` 写成了 `Motor_OnOff`，导致未解析符号。
- Chart 内部使用了 `cnt`，但没有声明局部数据。
- `[[MotorOnOff == 0]]` 这类双中括号转移条件已统一为单中括号。
- Chart 的采样时间明确为 `1e-4`。
- `Speed_ref` 从仿真激励进入控制器前增加 single 类型转换。
- `Surface Mount PMSM` 切换为离散仿真，并将 `P/Rs/L/flux/mechanical` 等参数改为脚本变量。
- 逆变器输出到 PMSM 前增加 single 类型转换。

验证结果：

- `init_PMSM_NFLUX.m` 可通过 `matlab -batch` 单独执行。
- `PMSM_NFLUX` 执行 Update Diagram 通过。
- `PMSM_NFLUX` 运行 `StopTime=0.02` 的短仿真通过。

剩余注意事项：

- 仿真时仍有 single 参数量化警告，多数来自 `pi`、`sqrt(3)`、`Ts`、Clarke/Park 系数和电压限幅，属于 single 精度下的正常提示。后续可统一改成 `single(...)` 参数表达式或降低 precision-loss 诊断等级。
- `idq_Controller` 中 q 轴 PID 的外部参数端口目前仍接到了 `curr_d_kp/curr_d_ki` 常量；如果后续 d/q 轴需要独立整定，应把 q 轴外接常量改为 `curr_q_kp/curr_q_ki`。

## 2026-06-11 state4 接管门控与相位误差检测

当前已经在 `PMSM_NFLUX` 中加入 `Handover_Gate` 子系统，并将 `ThetaAlign -> RunStage` 迁移条件改为：

```text
[after(5000,tick) && HandoverReady == 1]
```

`Handover_Gate` 的作用是：

- 计算 `phase_err = wrapToPi(theta_fd - NfluxTheta)`。
- 对 `abs(phase_err)` 做阈值判断。
- 只有当误差连续小于 `phase_err_limit = 0.3 rad` 达到 `handover_stable_ticks = 1000` 个采样点后，`HandoverReady` 才置位。
- `HandoverReady` 到 Chart 前增加了一拍 `Unit Delay`，避免 action subsystem 的输入依赖环。

验证结果：

- `set_param(model,'SimulationCommand','update')` 通过。
- 5 s 仿真通过。
- `HandoverGate_out1` 在 3.5 s 后由 0 变为 1。
- `HandoverGate_out2`（相位误差）在接管区间约为 `-0.05 rad` 量级，说明误差门控能正常收敛。

已同步修正初始化脚本中的兼容信号别名，避免旧模型/新模型信号名不一致：

- `ialpha = i_alpha`
- `ibeta = i_beta`
- `ualpha = u_alpha`
- `ubeta = u_beta`

剩余建议：

- 继续用 `state4` 保持积分角，不要立刻切 `theta_hat`。
- 先观察 `phase_err` 能否稳定小于 0.3 rad，再考虑更平滑的观测器角接管。
- 如果后面还要做更严格的接管，可以把 `phase_err_limit` 和 `handover_stable_ticks` 单独暴露成可调参数。
 
## 2026-06-11 19:59:25 +08:00 HandoverJudge 纯模块化

当前模型按 `PMSM_NFLUX_v0.slx` 处理，不再修改无后缀模型。

本次将 `FOC/current_loop/Subsystem` 中原来的 `MATLAB Function` 接管判断块替换为普通 Simulink 子系统 `HandoverJudge`。子系统内部使用 `Sum`、`Abs`、`Relational Operator`、`Logical Operator`、`Unit Delay`、`MinMax`、`Product`、`Data Type Conversion` 等基础模块实现：

- `phase_err = theta_fd - theta_hat`
- `err_ok = abs(phase_err) < phase_err_limit`
- `speed_ok = abs(omega_hat) > omega_handover_min`
- `state_ok = Motor_state == 4`
- `stable_ok = err_ok && speed_ok && state_ok`
- `stable_cnt = stable_ok ? min(stable_cnt + 1, handover_stable_ticks) : 0`
- `HandoverReady = stable_cnt >= handover_stable_ticks`

建模注意点：不能直接从 If Action Subsystem4 的输出分支给 `HandoverJudge`，因为该信号同时进入 `Merge`，Simulink 会报“分支信号无法馈入 Merge 模块”。当前改为从 `theta_fd` 的 `Merge` 输出取角度信号，再由 `Motor_state == 4` 限定只在 `ThetaAlign` 阶段判断，因此逻辑等价且满足 Merge 建模规则。

新增参数：

- `omega_handover_min = single(20.0)`

验证结果：

- 已备份原模型为 `PMSM_NFLUX_v0_before_handover_module_20260611.slx`
- 已执行 `build_handover_judge_module_v0.m`
- `set_param(model,'SimulationCommand','update')` 通过
- 静态检查确认 `HandoverJudge` 内部不再包含 `S-Function`，已经是普通 Simulink 模块
## 2026-06-11 20:20:00 +08:00 Handover 判定未通过现象

当前用户反馈：按建议修改后，仿真中速度显示仍为 600，`stable_cnt_dbg` 类信号只出现周期性尖峰，未持续累加到 `handover_stable_ticks = 1000`。

初步判断：
- 如果显示的 600 来自 `OP_Spd` / `Speed_ref`，它只是开环给定转速，不代表观测器估算速度已经接管。
- 从 scope 现象看，接管判定没有稳定通过，状态仍停留在开环/对齐阶段，因此输出角度仍主要按给定转速积分。
- 保存后的 `PMSM_NFLUX_v0.slx` 中 `HandoverJudge` 仍是 `theta_fd_for_check - theta_hat` 直接相减，未看到 `mod`/wrap 结构；若用户已在界面修改，需确认修改的是 `PMSM_NFLUX_v0.slx` 且已经保存。
- 即便加入 wrap，如果 `phase_err` 长期约为 1 rad 量级，也说明观测器角度与开环角度存在固定相位偏差，需要先做角度基准/符号/相位补偿，而不是直接放宽门槛。

下一步建议：
1. 先确认 `HandoverJudge` 内部实际为 `phase_err = mod(theta_fd - theta_hat + pi, 2*pi) - pi`。
2. 同时观察 `Motor_state`、`HandoverReady`、`stable_cnt_dbg`、`phase_err`、`omega_hat`、`theta_fd`、`theta_hat`。
3. 如果 `stable_cnt_dbg` 达不到 1000，说明没有满足连续稳定条件；优先校正 `theta_hat` 的相位基准，而不是强行切到 RunStage。

## 2026-06-11 20:35:00 +08:00 HandoverJudge wrap 结构确认

用户保存 `PMSM_NFLUX_v0.slx` 后重新检查，`HandoverJudge` 内部已经包含 wrap 误差链路：

```text
delta = theta_fd_for_check - theta_hat
phase_err = mod(delta + pi, 2*pi) - pi
```

静态检查可见新增块：
- `Sum_phase_err`
- `Add`，用于 `delta + pi`
- `Mod`，参数为 `mod`
- `Multiply`，用于生成 `2*pi`
- `Add1`，用于 `mod(...) - pi`

因此当前问题不再是角度未包角，而是 `phase_err` 包角后仍长期约在 `-1.0 ~ -1.4 rad`，只在局部瞬间接近 0，导致 `stable_cnt_dbg` 只能出现尖峰，无法连续累加到 `handover_stable_ticks = 1000`。后续应优先处理 `theta_hat` 与 `theta_fd` 的相位基准/偏置对齐，而不是继续放宽 `phase_err_limit`。

## 2026-06-11 20:55:00 +08:00 自动角度偏置与 RunStage 接线修正

用户手动加入 `theta_bias = -1.2 rad` 后，接管判定明显改善，但反馈“速度后面变成 0”。检查 `PMSM_NFLUX_v0.slx` 后发现：

- 手动偏置链路只接到了 `HandoverJudge` 的 `theta_hat` 输入。
- `RunStage(case 5)` 的 `theta_Close` 来自 `Unit Delay1`。
- 保存后的模型中 `Unit Delay1` 输入未接线，因此进入 `case 5` 后 `theta_fd` 会变成 0 或旧值，电机速度掉 0 是合理现象。

本次新增 `ThetaBiasAlign` 子系统：

```text
raw_phase_err = wrapToPi(theta_fd - theta_hat_raw)
theta_bias(k+1) = theta_bias(k) + theta_bias_lpf_k * wrapToPi(raw_phase_err - theta_bias(k))
theta_hat_align = wrapTo2Pi(theta_hat_raw + theta_bias)
```

更新规则：
- 只在 `Motor_state == 4` 的 ThetaAlign 阶段更新 `theta_bias`。
- 进入 RunStage 后保持最后一次偏置。
- `theta_hat_align` 同时接入 `HandoverJudge` 和 `Unit Delay1 -> RunStage theta_Close`，保证“判定用角度”和“接管用角度”一致。

新增参数：
- `theta_bias_lpf_k = single(0.002)`
- `theta_bias_initial = single(0.0)`

新增脚本：
- `add_theta_bias_align_v0.m`

验证结果：
- 已备份模型为 `PMSM_NFLUX_v0_before_theta_bias_align_20260611.slx`
- `set_param(model,'SimulationCommand','update')` 通过
- `sim('PMSM_NFLUX_v0','StopTime','5')` 通过

注意事项：
- 仿真仍存在 single 参数精度量化警告，属于当前 single 建模下的常见提示。
- 出现过 `idq_Controller/PID Controller1/Integrator/Discrete/Integrator` wrap overflow 警告，后续需要检查电流环积分限幅/抗饱和配置。
## 2026-06-11 22:10:00 +08:00 简化接管链路，回到参考式开环+原始观测器角

当前已经把自动偏置链路收回，只保留最小必要路径：

- `ThetaBiasAlign` 已从 `PMSM_NFLUX_v0.slx` 中移除。
- `NfluxTheta` 仍然直接接到 `Unit Delay1`，保证 `RunStage(case 5)` 的 `theta_Close` 不是 0。
- 如果未来重新加入 `HandoverJudge`，脚本 `simplify_handover_ref_logic_v0.m` 也能兼容；但当前模型不强依赖它。
- 新脚本已保存为 `simplify_handover_ref_logic_v0.m`，自动偏置脚本 `add_theta_bias_align_v0.m` 已删除。

验证结果：

- `simplify_handover_ref_logic_v0.m` 运行成功。
- `sim('PMSM_NFLUX_v0','StopTime','5')` 通过。

当前结论：

- 这版先不靠自动偏置掩盖观测器误差。
- 后续如果还要做接管判定，再单独补一个更干净的 `HandoverReady`，不要和角度补偿混在一起。

## 2026-06-11 22:40:00 +08:00 接管判定恢复为递减计数，并加入延时门控

本次按你的要求把接管逻辑收回到参考项目式结构：

- 新增 `HandoverJudge`，只负责判断能不能切，不再做角度偏置。
- `stable_cnt` 由“失败清零”改成“失败递减”。
- `phase_err_limit = single(0.67)`、`omega_handover_min = single(20.0)`、`handover_stable_ticks = single(1000)` 保持不变。
- `Chart` 中 `ThetaAlign -> RunStage` 的转移条件改为 `after(5000,tick) && HandoverReady == 1`。
- `HandoverReady` 先经过 `Unit Delay` 再进 Chart，避免当前步状态动作和转移条件互相依赖。
- `RunStage/case5` 的 `iq_ref` 不再直接从 1.0A 跳到 0.3A，而是通过 `Rate Limiter` 从 `iq_open_loop` 斜坡过渡到 `iq_CloseRef`。

验证结果：

- `add_handover_ready_logic_v0.m` 运行成功。
- `sim('PMSM_NFLUX_v0','StopTime','5')` 通过。

当前结论：

- 这版更接近你想要的最简洁参考逻辑。
- 后面再看的是 `phase_err`、`HandoverReady`、`stable_cnt` 是否稳定连续，而不是再去加偏置。

## 2026-06-12 09:20:00 +08:00 HandoverReady 验证与未接管原因

新增 `verify_handover_v0.m` 用于记录并打印接管关键信号：

- `Motor_state`
- `HandoverReady_d`
- `stable_cnt`
- `phase_err`
- `omega_hat`
- `state_ok`
- `err_ok`
- `speed_ok`
- `stable_ok`
- `nflux_wm_raw`
- `iq_ref_final`
- `theta_fd`
- `theta_hat`

验证发现：

- 之前 `omega_hat` 进 `HandoverJudge` 为 0，是因为在嵌套状态机子系统里用 `From_NfluxWm` 取父层局部 Goto 信号不可靠。
- 已改为显式输入口：`Nonlinear Flux Observer` 的速度输出直接接入状态机子系统 `NfluxWm` 输入，再送入 `HandoverJudge`。
- 修改后 `omega_hat` 与 `nflux_wm_raw` 一致，速度判定 `speed_ok` 可以成立。
- 20 s 验证中仍未进入 `RunStage`：`stable_cnt` 最高约 413，未达到 `handover_stable_ticks = 1000`。
- 当前阻塞接管的是 `phase_err`，后期会重新回到约 `-1.3 rad`，超过 `phase_err_limit = 0.67 rad`。

当前结论：

- `HandoverReady` 结构和速度接线已修正。
- 当前不应继续放宽门槛或加自动偏置；下一步应检查观测器角 `theta_hat` 与控制角 `theta_fd` 的角度基准/符号/90 度补偿关系。

## 2026-06-12 case5 iq_ref 切换整理
- 在 PMSM_NFLUX_v0 的 RunStage/case5 内加入延时切换：先输出 iq_handover，计数达到 speed_loop_delay_ticks 后再接 iq_CloseRef。
- 在状态机父级 Merge1 后加入统一 iq_ref_Saturation 和 iq_ref_RateLimiter_Final，所有状态的 iq_ref 统一经过限幅和斜率限制。
- 备份模型：PMSM_NFLUX_v0_before_case5_iq_ref_slew_20260612.slx。
- 目的：避免从开环/接管阶段直接切入速度环时 iq_ref 出现大幅负向制动尖峰。
- 补充：RunStage/case5 的 Action Port InitializeStates 改为 reset，保证延时计数器每次进入 case5 重新计数。

## 2026-06-12 HandoverReady 接线修正
- 发现 HandoverJudge 四个输入悬空，Chart 没有 HandoverReady 输入，实际仍是 after(5000,tick) 定时硬切。
- 新增/恢复 Chart 输入 HandoverReady，并把 ThetaAlign->RunStage 条件改为 after(5000,tick) && HandoverReady == 1。
- 将 Motor_state、theta_fd、NfluxWm、NfluxTheta 接入 HandoverJudge，并用 HandoverReadyDelay 延后一拍进入 Chart。
- 给状态机子系统增加 NfluxWm 输入，来源为 Nonlinear Flux Observer 的 we 输出。
- 备份模型：PMSM_NFLUX_v0_before_wire_handover_ready_20260612.slx。

## 2026-06-12 切闭环后速度异常诊断
- 重新仿真发现，当前模型中 HandoverReady 修正后会在约 3.3304 s 变为 1，状态机仍在 3.6002 s 从 case4 进入 case5，因为 case4 至少等待 5000 tick。
- 当前保存模型在本机仿真中未复现“速度大幅超调”，而是表现为 7 s 后目标 1200 rpm 时实际速度约 730 rpm，观测速度约 548 rpm。
- 速度环输出 iq_CloseRef 最高约 2.94 A，但 uq_ref 长期顶到 12.47 V，说明电压已经饱和，电流环无法继续提升有效 q 轴电流。
- 当前初始化参数为 Udc=24 V、VdqLimit=12.47 V、Pn=4、flux=0.016884 Wb。按反电势估算：680 rpm 需要约 7.65 V，1020 rpm 需要约 11.48 V，1200 rpm 需要约 13.51 V。1200 rpm 已超过当前 VdqLimit，1020 rpm 也几乎没有电压余量。
- 初步结论：后续应先降低速度指令或提高母线电压/放宽电压限制，再评价速度环和观测器切换效果；否则速度环会持续饱和，调 PI 或 handover 逻辑意义有限。

## 2026-06-12 case4 最短相位差渐变修正

本次针对“case4 逐渐切换到观测器角度时速度波动明显大于 case5 直接切换”的问题做了仿真对比和模型修正。

### 现象确认

- 当前保存的 `PMSM_NFLUX_v0.slx` 原本 case4 的 `Theta_fd` 实际接在 `If Action Subsystem4/Mod`，即开环积分角；case5 通过 `Unit Delay1` 直接使用 `NfluxTheta`。
- 临时把 case4 输出改回旧的渐变角 `Mod1` 后仿真，case4 期间实际机械转速约 `565 ~ 1475 rpm`，峰峰值约 `909 rpm`。
- 当前开环 case4 对照组约 `464 ~ 712 rpm`，峰峰值约 `248 rpm`。
- 根因判断：旧渐变链路使用正向 `0..2*pi` 差值插值，遇到角度包络边界时会把很小的跨零误差变成接近 `2*pi` 的大补偿，相当于持续注入非物理角速度。

### 修改内容

- 备份模型和初始化脚本：
  - `PMSM_NFLUX_v0_before_case4_shortest_blend_20260612_124923.slx`
  - `init_PMSM_NFLUX_before_case4_shortest_blend_20260612_124923.m`
  - 建模脚本执行过程中还生成了 `PMSM_NFLUX_v0_before_case4_shortest_blend_20260612_125108.slx` 和 `PMSM_NFLUX_v0_before_case4_shortest_blend_20260612_125123.slx`
- 在 `PMSM_NFLUX_v0.slx` 的 case4 action subsystem 内新增 `ThetaShortestBlend` 子系统。
- case4 的 `Theta_fd` 现在接到 `ThetaShortestBlend` 输出。
- 新逻辑为：

```text
delta_short = wrapToPi(theta_hat - theta_open)
correction = rateLimit(alpha * delta_short, theta_handover_slew_limit)
theta_fd = wrapTo2Pi(theta_open + correction)
```

- 在 `init_PMSM_NFLUX.m` 中新增参数：

```matlab
theta_handover_slew_limit = single(5.0);
```

### 新增脚本

- `apply_case4_shortest_blend_v0.m`：可重复重建 `ThetaShortestBlend` 并接入 case4。
- `verify_case4_shortest_blend_v0.m`：记录并打印当前模型 case4 修正后的关键仿真指标。
- `sweep_theta_handover_slew_v0.m`：扫描 `theta_handover_slew_limit`，用于比较不同补偿限速下的 case4 速度波动。
- `analyze_handover_v0.m`：保留为对比旧开环/旧渐变链路的分析脚本，并已修正为运行后恢复原始 case4 输出接线。

### 参数扫描与最终验证

`sweep_theta_handover_slew_v0.m` 扫描结果显示：

- `0 rad/s`：case4 实际转速峰峰值约 `248.1 rpm`，等价于不做角度补偿。
- `5 rad/s`：case4 实际转速峰峰值约 `239.5 rpm`，是当前扫描中最稳的一档。
- `10/20/50 rad/s`：补偿过快，case4 速度波动开始明显增大；`50 rad/s` 时 case4 实际转速峰峰值约 `806.5 rpm`。

最终默认采用：

```matlab
theta_handover_slew_limit = single(5.0);
```

`verify_case4_shortest_blend_v0.m` 最终验证结果：

- `State4 first = 3.100200 s`
- `State5 first = 3.600200 s`
- case4 `Theta_fd` 来源确认为 `If Action Subsystem4/ThetaShortestBlend`
- case4 实际机械转速约 `472.9 ~ 712.4 rpm`，峰峰值约 `239.5 rpm`
- case5 后 `0.8 s` 实际机械转速约 `578.1 ~ 1104 rpm`
- 模型最后清理为 `Dirty=off`

### 注意事项

- 仿真仍会出现 `idq_Controller/PID Controller1/Integrator/Discrete/Integrator` 的 wrap overflow warning，这是电流环积分器/抗饱和问题，和本次 case4 角度渐变修正不是同一个问题。
- 当前修正的核心目标是避免旧渐变算法跨 `0/2*pi` 时产生大角度跳变；不是解决高转速电压饱和或速度环参数整定问题。

## 2026-06-13 数据字典精简与代码生成参数结构体化

本次目标是让 `PMSM_NFLUX_v1_1` 的数据字典和生成代码参数接口对齐参考 `BLDC_SMO` FOC 工程，减少散落的全局参数。

### 修改内容

- `PMSM_NFLUX.sldd` 从 61 个条目精简为 32 个条目。
- 删除未被当前模型直接引用或不适合进入 MCU 参数接口的旧条目，例如 `Ld/Lq`、`current_bw`、`speed_bw`、`iq_open_loop`、`phase_err_limit`、`omega_handover_min`、重复的 `ialpha/ibeta/ualpha/ubeta` 等。
- 保留 `FluxTheta` 和 `FluxWm` 为 `ExportedGlobal` 调试信号，对齐参考工程中 `SMOTheta`、`SMOWm` 的使用方式。
- 将需要上板标定的参数从散 `ExportedGlobal` 改为 Custom Storage Class `Struct`，生成以下结构体参数：

```c
extern curr_kpki_type curr_kpki;
extern handover_cfg_type handover_cfg;
extern motor_type motor;
extern nflux_obs_type nflux_obs;
extern spd_kpki_type spd_kpki;
```

### 参数分组

```text
curr_kpki:
  curr_d_kp, curr_d_ki, curr_q_kp, curr_q_ki

spd_kpki:
  spd_kp, spd_ki

motor:
  Rs, L, Pn, flux

nflux_obs:
  Gamma, PLL_Kp, PLL_Ki, LPF_K

handover_cfg:
  iq_handover, iq_ref_slew_up, iq_ref_slew_down, theta_handover_slew_limit
```

`PLL_OmegaLimit` 已退回 `Auto`，因为它在 PID 块中以 `-PLL_OmegaLimit` 表达式形式使用，放入结构体可调参数会导致子系统代码生成失败。当前将其作为固定保护限幅内联。

### 验证结果

- `PMSM_NFLUX_v1_1` 模型 update 通过。
- FOC 子系统代码生成通过。
- 生成头文件中不再导出一串散 `curr_*`、`spd_*`、`Gamma`、`PLL_Kp` 等全局参数，而是导出结构体参数。
- 使用 ARM GCC 对生成的 4 个 C 文件做语法检查通过。
