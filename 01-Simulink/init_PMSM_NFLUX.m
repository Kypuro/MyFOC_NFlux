% PMSM_NFLUX.slx 的初始化参数脚本
% 每次更新模型、仿真模型、生成代码之前，先运行这个脚本。

%% 模型名称和仿真时间
model_name = 'PMSM_NFLUX';
this_script_dir = fileparts(mfilename('fullpath'));
if ~isempty(this_script_dir)
    addpath(fullfile(this_script_dir, 'ParameterIdentification'));
end

Ts = 1.0e-4;                      % FOC 电流环/主控制周期，单位 s，也就是 10 kHz
Ts_speed = 1.0e-3;                % 速度环周期，单位 s，也就是 1 kHz
sim_stop_time = 10.0;             % 默认仿真停止时间，单位 s

%% 直流母线和 PWM 参数
Udc = single(24.0);               % 直流母线电压，单位 V
PWM_HalfPeriod = single(8000);    % PWM 半周期计数值，对应定时器 ARR 或半周期计数
Tpwm = 2 * PWM_HalfPeriod;            % SVPWM 计算中使用的 PWM 周期归一化计数
VoltageMargin = single(0.90);     % 电压利用安全裕量，避免调制进入过饱和
VdqLimit = Udc * VoltageMargin / single(sqrt(3)); % dq 轴电压限幅，线性 SVPWM 近似上限

%% PMSM 电机参数
Pn = single(4);                   % 电机极对数
Rs = single(6.97);                 % 定子相电阻，单位 ohm
L = single(0.00535);             % 表贴式 PMSM 相电感，单位 H
Ld = L;                           % d 轴电感，表贴电机通常近似 Ld = Lq
Lq = L;                           % q 轴电感
flux = single(0.016884);            % 永磁体磁链，单位 Wb
J = single(75e-6);               % 转动惯量，单位 kg*m^2
B = single(8e-5);             % 粘性摩擦系数，单位 N*m*s/rad
load_torque = single(0.0);        % 外部负载转矩，单位 N*m
Kt = single(1.5) * Pn * flux;     % 转矩常数，单位 N*m/A，公式 Kt = 1.5 * Pn * flux

%% Rs identification parameters
RsId_Init = Rs;                   % Initial estimated stator resistance, ohm
RsId_L = L;                       % Inductance used to compensate L * di/dt, H
RsId_MinCurrent = single(0.05);   % Minimum alpha-beta current magnitude, A
RsId_MaxOmega = single(5.0);      % Maximum electrical speed for Rs ID, rad/s
RsId_LpfGain = single(0.02);      % First-order update gain for Rs_hat
RsId_Min = single(0.1);           % Lower clamp for instantaneous Rs, ohm
RsId_Max = single(50.0);          % Upper clamp for instantaneous Rs, ohm

%% Standstill Rs identification parameters
RsIdBatch_Init = Rs;                  % Initial/held Rs estimate for standstill ID, ohm
RsIdBatch_MinCurrent = single(0.05);  % Minimum d-axis/test current magnitude, A
RsIdBatch_MaxSpeed = single(5.0);     % Maximum speed accepted as standstill, rpm-equivalent input
RsIdBatch_MinSamples = int32(3);      % Minimum settled samples per current level
RsIdBatch_MinLevels = int32(4);       % Minimum fit levels required before accepting Rs
RsIdBatch_SettleTicks = int32(200);   % Samples to discard after each level transition
RsIdBatch_Min = single(0.1);          % Lower valid Rs limit, ohm
RsIdBatch_Max = single(50.0);         % Upper valid Rs limit, ohm
RsIdBatch_MaxRmse = single(0.1);      % Maximum fit voltage RMSE, V
RsIdBatch_MaxValRmse = single(0.1);   % Maximum holdout validation RMSE, V
RsIdBatch_RefTemp = single(20.0);     % Reference winding temperature, degC
RsIdBatch_CuAlpha = single(0.00393);  % Copper resistance temperature coefficient, 1/degC

%% 电流环 PI 参数
current_bw = single(1000.0);      % 电流环目标带宽，单位 rad/s
curr_d_kp = 0.017; %Ld * current_bw;      % d 轴电流环比例增益，近似 Kp = Ld * 带宽
curr_d_ki = 35; %Rs * current_bw;      % d 轴电流环积分增益，近似 Ki = Rs * 带宽
curr_q_kp = 0.017; %Lq * current_bw;      % q 轴电流环比例增益
curr_q_ki = 35; %Rs * current_bw;      % q 轴电流环积分增益

%% 速度环 PI 参数
speed_bw = single(20.0);          % 速度环目标带宽，单位 rad/s，要明显低于电流环
rpm_to_radps = single(pi / 30.0); % rpm 到 rad/s 的换算系数
spd_kp = (J * speed_bw / Kt) * rpm_to_radps;
%spd_kp = 0.003389;%(J * speed_bw / Kt) * rpm_to_radps; % 速度环比例增益，输入是 rpm 误差
spd_ki = 0.000144; %(B * speed_bw / Kt) * rpm_to_radps; % 速度环积分增益，输入是 rpm 误差
spd_ki = (B * speed_bw / Kt) * rpm_to_radps;
iq_ref_limit = single(3.0);       % 速度环输出的 q 轴电流限幅，单位 A

iq_handover = single(0.4);          % 角度接管时保持的 q 轴电流
iq_ref_slew_up = single(5.0);       % iq_ref 上升斜率 A/s
iq_ref_slew_down = single(2.0);     % iq_ref 下降斜率 A/s
iq_ref_min_handover = single(-0.2); % 接管阶段先限制负电流，避免猛刹车
iq_ref_max_handover = single(1.2);
speed_loop_delay_ticks = single(5000); % case5 进入后延时 0.5s 再开速度环
reverse_cross_ticks = uint16(6000);    % 运行中正反转时开环跨越低速不可观区的采样点数
reverse_align_ticks = uint16(5000);    % 正反转开环跨越后的角度重接管采样点数
reverse_open_iq_ref = single(1.0);     % 正反转开环跨越期间 q 轴电流给定，单位 A
reverse_open_speed_rpm = single(600.0);% 正反转开环跨越目标机械转速，单位 rpm

%% 非线性磁链观测器参数
Gamma = single(100000.0);         % 非线性磁链观测器校正增益

%% PLL 和速度滤波参数
PLL_BW = single(150.0);           % PLL 带宽调节量，单位 rad/s
PLL_Zeta = single(0.707);         % PLL 阻尼系数，0.707 接近二阶系统常用阻尼
PLL_Kp = single(212.1); %single(2.0) * PLL_Zeta * PLL_BW; % PLL 比例增益
PLL_Ki = single(2500); %single(50.0 * 50.0);     % PLL 积分增益，当前先用经验初值
PLL_OmegaLimit = single(2.0 * pi * 1000.0); % PLL 输出电角速度限幅，单位 rad/s
LPF_K = single(0.003);            % 机械速度一阶低通滤波系数

%% 启动流程和命令默认值
MotorOnOff_init = uint8(0);       % 电机启动开关默认值，0 表示关闭
OpenLoopHold_init = uint8(0);     % 是否保持开环，0 表示允许进入后续闭环切换
Speed_ref_init = single(600.0);   % 默认机械目标转速，单位 rpm
iq_open_loop = single(1.0);       % 开环启动阶段给定的 q 轴电流，单位 A
iq_run_default = single(0.3);     % 闭环运行初始 q 轴电流，单位 A
phase_err_limit = single(0.67);    % 允许观测器接管的电角度误差阈值，单位 rad
omega_handover_min = single(20.0); % 允许接管的最小观测器速度，单位必须与 NfluxWm 保持一致
handover_stable_ticks = single(1000); % 误差连续满足阈值的采样点数，1000 点对应 0.1 s
iq_handover_slew = single(1.0);    % case5 中 iq_ref 从开环电流过渡到速度环输出的最大变化率，单位 A/s
theta_handover_slew_limit = single(5.0); % case4 角度补偿最大变化率，单位 electrical rad/s

%% 必须解析为 Simulink.Signal 的信号对象
i_alpha = Simulink.Signal;         % alpha 轴电流信号对象
i_alpha.DataType = 'single';       % 信号数据类型为 single
i_alpha.Dimensions = 1;            % 信号维度为标量
i_alpha.Complexity = 'real';       % 信号为实数
i_alpha.CoderInfo.StorageClass = 'Auto'; % 代码生成存储类型自动决定

i_beta = Simulink.Signal;          % beta 轴电流信号对象
i_beta.DataType = 'single';
i_beta.Dimensions = 1;
i_beta.Complexity = 'real';
i_beta.CoderInfo.StorageClass = 'Auto';

u_alpha = Simulink.Signal;         % alpha 轴电压信号对象
u_alpha.DataType = 'single';
u_alpha.Dimensions = 1;
u_alpha.Complexity = 'real';
u_alpha.CoderInfo.StorageClass = 'Auto';

u_beta = Simulink.Signal;          % beta 轴电压信号对象
u_beta.DataType = 'single';
u_beta.Dimensions = 1;
u_beta.Complexity = 'real';
u_beta.CoderInfo.StorageClass = 'Auto';

ialpha = i_alpha;                 % 兼容模型中无下划线的 alpha 电流信号名
ibeta = i_beta;                   % 兼容模型中无下划线的 beta 电流信号名
ualpha = u_alpha;                 % 兼容模型中无下划线的 alpha 电压信号名
ubeta = u_beta;                   % 兼容模型中无下划线的 beta 电压信号名

%% 基本参数合法性检查
assert(Rs > 0, 'Rs must be positive.');       % 电阻必须大于 0
assert(L > 0, 'L must be positive.');         % 电感必须大于 0
assert(flux > 0, 'flux must be positive.');   % 磁链必须大于 0
assert(Pn > 0, 'Pn must be positive.');       % 极对数必须大于 0
assert(Udc > 0, 'Udc must be positive.');     % 母线电压必须大于 0
assert(Ts > 0, 'Ts must be positive.');       % 采样周期必须大于 0
