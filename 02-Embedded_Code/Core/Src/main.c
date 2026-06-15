/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "adc.h"
#include "dma.h"
#include "opamp.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "FOC.h"
#include <stdlib.h>
#include <string.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */

/*==============================================================================
 * 电流采样与标定相关宏定义
 *============================================================================*/

/**
 * @brief 电流 offset 标定的 ADC 样本数量
 * @note  值越大 offset 越准确，但上电等待时间越长。
 *        1024 样本在 10kHz 注入采样率下约耗时 102.4ms。
 *        计算方式：1024 / 10000Hz = 0.1024s
 */
#define CURRENT_ADC_SAMPLE_COUNT 1024U

/**
 * @brief ADC count 到实际电流 (A) 的转换系数
 * @note  推导公式：gain = (Vref / 4096) / (Gain_opamp * Rshunt)
 *        本例：3.3V / 4096 / (10 * 0.1Ω) ≈ 0.0219726 A/count
 *        需根据实际运放增益、分流电阻值和 ADC 参考电压重新计算。
 */
#define CURRENT_ADC_TO_AMP 0.0219726f

/*==============================================================================
 * PWM 与母线电压相关宏定义
 *============================================================================*/

/**
 * @brief PWM 中点比较值（50% 占空比）
 * @note  TIM1 ARR = 8000-1，中心对齐模式，10kHz PWM 频率。
 *        f_PWM = TIM1CK / (2 * (ARR+1)) = 160MHz / 16000 = 10kHz。
 *        FOC 算法输出的 Tcmp1/2/3 范围为 0..8000，
 *        中值 4000 对应三相输出各 50% 占空比，即电机端电压为零。
 *        上电初始化及停机时均将 PWM 设为中值，确保不会意外驱动电机。
 */
#define PWM_MID_COUNTS 4000U

/**
 * @brief 母线电压固定初值 (V)
 * @note  在 ADC 尚未完成首次母线电压采样前，作为 FOC 模型的临时输入。
 *        主循环开始后会通过 ADC2 regular 通道实时更新，替换此初值。
 *        根据实际供电电压调整（如使用 12V 电源则改为 12.0f）。
 */
#define VBUS_FIXED_VALUE 24.0f

/**
 * @brief 母线电压 ADC 分压比换算系数 (V/count)
 * @note  推导：VBUS_ADC_SCALE = (Rtop + Rbottom) / Rbottom * (Vref / 4096)
 *        本例：(100k + 10k) / 10k * (3.3 / 4096) ≈ 11.0
 *        即 ADC 每读到一个 count，对应实际母线电压约 11.0 / 4096 ≈ 0.0027V。
 *        更换分压电阻后必须重新计算此值。
 */
#define VBUS_ADC_SCALE 11.0f

/*==============================================================================
 * 转速范围宏定义
 *============================================================================*/

/** @brief 默认目标转速 (RPM)，上电及未收到上位机速度指令时使用 */
#define SPEED_DEFAULT_RPM 600.0f

/** @brief 当前无感启动/闭环切换策略允许的最低稳定转速 (RPM) */
#define SPEED_SENSORLESS_MIN_RPM 120.0f

/** @brief 允许的最低目标转速 (RPM) */
#define SPEED_MIN_RPM SPEED_SENSORLESS_MIN_RPM

/** @brief 允许的最高目标转速 (RPM)，防止超速损坏电机或驱动器 */
#define SPEED_MAX_RPM 1800.0f

/** @brief 上位机 ASCII 命令缓冲区大小（含结尾 '\0'） */
#define HOST_CMD_BUFFER_SIZE 32U

/** @brief USART3 RX DMA 环形缓冲区大小，用于可靠接收上位机命令 */
#define HOST_RX_DMA_BUFFER_SIZE 128U

/*==============================================================================
 * 三相电流 ADC 原始值（中断与主循环共享，需 volatile）
 *============================================================================*/

/** @brief A 相电流 ADC 原始值（12-bit，0..4095），由 ADC1 injected rank1 采样 */
volatile uint16_t ia_adc = 0;

/** @brief B 相电流 ADC 原始值（12-bit，0..4095），由 ADC2 injected rank1 采样 */
volatile uint16_t ib_adc = 0;

/** @brief C 相电流 ADC 原始值（12-bit，0..4095），由 ADC1 injected rank2 采样 */
volatile uint16_t ic_adc = 0;

/**
 * @brief ADC 注入组转换完成计数
 * @note  每完成一轮三相电流采样自增 1，用于在调试器中确认 10kHz 采样是否持续运行。
 *        正常运行时该值应持续增长；若停止增长则说明注入组触发或中断响应异常。
 */
volatile uint32_t adc_inj_count = 0;

/*==============================================================================
 * 去零偏后的三相电流（有符号值）
 *============================================================================*/

/**
 * @brief 三相电流去除零偏后的 ADC count 值
 * @note  允许为负数（当实际电流为负半周时）。
 *        计算公式：raw = adc - offset
 *        后续乘以 CURRENT_ADC_TO_AMP 即为实际安培值。
 */
volatile int16_t ia_raw = 0;
volatile int16_t ib_raw = 0;
volatile int16_t ic_raw = 0;

/*==============================================================================
 * 零电流偏置（offset）相关变量
 *============================================================================*/

/**
 * @brief 三相电流的零偏 ADC 值
 * @note  上电后在 PWM 未输出功率的状态下采样若干次取平均得到。
 *        该值包含了 OPAMP 偏置电压、ADC 零点误差等静态分量，
 *        FOC 运行时用 ia_adc - ia_offset 消除这些静态误差。
 */
volatile uint16_t ia_offset = 0;
volatile uint16_t ib_offset = 0;
volatile uint16_t ic_offset = 0;

/**
 * @brief offset 标定阶段的累加和
 * @note  每进入一次 ADC 注入回调累加一次三相 ADC 值，
 *        累计 CURRENT_ADC_SAMPLE_COUNT 次后除以总数即为 offset 平均值。
 *        使用 uint32_t 防止 1024 次累加溢出（1024 * 4095 ≈ 4.2M < 2^32）。
 */
volatile uint32_t ia_offset_sum = 0;
volatile uint32_t ib_offset_sum = 0;
volatile uint32_t ic_offset_sum = 0;

/*==============================================================================
 * FOC 运行状态变量
 *============================================================================*/

/**
 * @brief 三相电流瞬时和 (A)
 * @note  根据基尔霍夫电流定律，三相星形连接时 ia+ib+ic 应始终为 0。
 *        若该值偏离 0 较大（如 >0.5A），应优先排查：
 *        1. 电流 offset 标定是否正确
 *        2. 三相电流采样相序是否与 FOC 模型一致
 *        3. 电流传感器/运放方向是否反向
 */
volatile float i_sum = 0.0f;

/** @brief 已累计的 offset 样本数，达到 CURRENT_ADC_SAMPLE_COUNT 后停止计数 */
volatile uint16_t current_offset_count = 0;

/**
 * @brief offset 标定完成标志
 * @note  0 = 标定进行中，不可启动功率 PWM；
 *        1 = 标定完成，offset 可用于电流采样修正，允许启动功率 PWM。
 */
volatile uint8_t current_offset_ready = 0;

/**
 * @brief 电机功率级状态
 * @note  0 = 三相功率 PWM (CH1/CH2/CH3) 未启动；
 *        1 = offset 完成且收到上位机 RUN=1 后已自动启动三相 PWM。
 *        该变量用于区分"仅 CH4 触发采样"和"三相全功率输出"两种状态。
 */
volatile uint8_t Motor_state = 0;

/*==============================================================================
 * ADC 常规通道采样变量（主循环低频读取）
 *============================================================================*/

/** @brief ADC2 regular 采得的母线电压原始值 (12-bit)，对应 PA0 / ADC2_IN1 */
uint16_t adc_vbus = 0;

/**
 * @brief ADC1_IN11 速度电位器原始值
 * @note  当前使用上位机固定 RefSpeed，此变量暂未使用，预留用于后续电位器调速功能。
 */
uint16_t adc1_in11 = 0;

/**
 * @brief 电位器换算后的目标转速 (RPM)
 * @note  当前使用上位机固定 RefSpeed，此变量暂未使用。
 */
uint16_t finalspeed = 0;

/*==============================================================================
 * VOFA JustFloat 调试数据帧缓冲区
 *============================================================================*/

/**
 * @brief VOFA JustFloat 数据区
 * @note  17 个 float = 68 字节，依次为基础遥测和 FOC 诊断量。
 *        VOFA+ 上位机选择 JustFloat 协议即可实时查看这些波形。
 */
float load_data[17];

/**
 * @brief VOFA JustFloat 完整帧缓冲区 (72 字节)
 * @note  布局：[68 字节 float 数据] + [0x00, 0x00, 0x80, 0x7F]
 *        末尾 4 字节是 JustFloat 协议的固定帧尾，VOFA+ 靠它识别帧边界。
 *        使用 DMA 发送以避免阻塞 ADC 中断服务例程。
 */
uint8_t tempData[72];

/*==============================================================================
 * USART3 上位机 ASCII 命令接收缓冲区
 *============================================================================*/

/** @brief USART3 RX DMA 环形缓冲区，避免 2Mbps 单字节中断接收丢命令 */
uint8_t host_rx_dma_buffer[HOST_RX_DMA_BUFFER_SIZE];

/** @brief 正在接收中的命令行缓冲区（未遇到换行符前持续填充） */
char host_rx_buffer[HOST_CMD_BUFFER_SIZE];

/** @brief 兼容旧接收路径的完整命令行，正常 DMA 路径不会写入 */
char host_cmd_line[HOST_CMD_BUFFER_SIZE];

/** @brief host_rx_buffer 的当前写入位置（即已接收字符数） */
uint8_t host_rx_index = 0U;

/** @brief 主循环上次已处理到的 RX DMA 环形缓冲位置 */
volatile uint16_t host_rx_dma_last_pos = 0U;

/**
 * @brief 命令就绪标志
 * @note  兼容旧 UART RX 中断路径。当前 DMA 环形接收路径在主循环中直接解析，
 *        正常不会使用该标志。
 */
volatile uint8_t host_cmd_ready = 0U;

/**
 * @brief 上位机运行使能标志
 * @note  上位机发送 RUN=1 后置 1，主循环检测到此标志且 offset 完成后启动电机。
 *        RUN=0 时置 0，同时发出停机请求。
 *        上电默认为 0（安全：未收到运行命令前绝不启动电机）。
 */
volatile uint8_t host_run_enable = 0U;

/**
 * @brief 上位机停机请求标志
 * @note  收到 RUN=0 或 STOP 命令后置 1，主循环检测后执行停机操作并清零。
 */
volatile uint8_t host_stop_request = 0U;

/**
 * @brief 上位机给定的目标转速 (RPM)
 * @note  通过 SPD=xxx 或 REF=xxx 命令设置，默认值 SPEED_DEFAULT_RPM (600)。
 *        该值被限制在 [SPEED_MIN_RPM, SPEED_MAX_RPM] 范围内。
 */
volatile float host_ref_speed = SPEED_DEFAULT_RPM;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */

/**
 * @brief  将浮点值限制在 [lower, upper] 闭区间内
 * @param  value 输入值
 * @param  lower 下限
 * @param  upper 上限
 * @retval 钳位后的值（lower <= 返回值 <= upper）
 * @note   用于限制上位机下发的转速指令，防止超范围运行。
 */
static float ClampFloat(float value, float lower, float upper);

/**
 * @brief  启动 USART3 RX DMA 环形接收
 * @note   DMA 负责收字节，主循环通过 HostCommand_PollDmaRx() 解析。
 */
static void HostCommand_RestartDmaRx(void);

/**
 * @brief  轮询 USART3 RX DMA 新收到的字节
 * @note   在主循环中调用，避免高频 FOC 中断抢占导致命令字节丢失。
 */
static void HostCommand_PollDmaRx(void);

/**
 * @brief  处理一个上位机命令字节
 * @param  rx_byte USART3 RX DMA 收到的单字节数据
 */
static void HostCommand_ProcessRxByte(uint8_t rx_byte);

/**
 * @brief  处理上位机命令（主循环调用）
 * @note   检查 host_cmd_ready 标志，若为 1 则将命令行拷贝出来、
 *         清标志、再调用 HostCommand_Parse() 解析。
 *         拷贝前关全局中断是为了防止拷贝过程中 UART 中断
 *         又收到新数据修改 host_cmd_line。
 */
static void HostCommand_ProcessPending(void);

/**
 * @brief  解析上位机 ASCII 命令
 * @param  cmd 以 '\0' 结尾的命令字符串（已在调用前做了备份）
 * @note   支持的命令格式：
 *         - RUN=1 或 START  → 使能电机运行
 *         - RUN=0 或 STOP   → 禁止运行并停机
 *         - SPD=xxx 或 REF=xxx → 设置目标转速（自动钳位）
 *         解析前会先将小写字母转为大写，实现大小写不敏感匹配。
 */
static void HostCommand_Parse(char *cmd);

/**
 * @brief  停止电机运行
 * @note   将 MotorOnOff 清零通知 FOC 模型，停止三相功率 PWM 及互补输出，
 *         并将 PWM 比较值恢复为中值（50% 占空比），确保电机端电压为零。
 */
static void HostCommand_StopMotor(void);

/**
 * @brief  判断字符串 text 是否以 prefix 开头
 * @param  text   待检查的字符串
 * @param  prefix 前缀字符串
 * @retval 1 表示 text 以 prefix 开头；0 表示不是
 * @note   用于解析 SPD=xxx / REF=xxx 这类"关键字=数值"格式的命令。
 */
static uint8_t HostCommand_StartsWith(const char *text, const char *prefix);

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/**
 * @brief  FOC 系统启动流程说明
 * @note
 * 本系统采用分阶段启动策略，确保电流采样零偏标定完成后才输出功率，
 * 避免因 offset 未标定导致 FOC 控制发散损坏硬件。
 *
 * 阶段 1 — 仅采样、无功率输出（上电自动开始）：
 *   - HAL_Init / SystemClock_Config / 各外设初始化完成后，
 *     只启动 TIM1_CH4，其作用是在每个 PWM 周期内产生 ADC injected 触发信号，
 *     但 CH4 不连接功率 MOS，因此电机端电压为零。
 *   - ADC1/ADC2 注入组开始以 10kHz 采样三相电流。
 *
 * 阶段 2 — 零电流 offset 标定（在 ADC injected 中断回调中进行）：
 *   - 每次 ADC 注入组转换完成，累加 ia/ib/ic 的 ADC 原始值。
 *   - 累计 CURRENT_ADC_SAMPLE_COUNT (1024) 次后取平均，得到三相的零电流偏置。
 *   - 置 current_offset_ready = 1，通知主循环 offset 已就绪。
 *
 * 阶段 3 — 启动功率输出（主循环检测条件满足后执行）：
 *   - 条件：current_offset_ready == 1 && Motor_state == 0 && host_run_enable == 1
 *   - 置 MotorOnOff = 1，通知 FOC 模型进入启动状态机。
 *   - 启动 TIM1 CH1/CH2/CH3 及互补输出通道，电机开始受控运行。
 *
 * 阶段 4 — 正常运行循环（每次 ADC injected 中断中执行）：
 *   - 用 offset 修正电流值 → 转换为安培 → 写入 FOC 模型输入。
 *   - 调用 FOC_step() 执行一次 FOC 运算。
 *   - 将 FOC 输出的 Tcmp1/2/3 写入 TIM1 CCR 寄存器更新 PWM。
 *   - 通过 USART3 DMA 发送一帧 VOFA JustFloat 调试数据。
 *
 * 阶段 5 — 上位机命令处理（USART3 RX DMA 环形缓冲 + 主循环解析）：
 *   - DMA 持续接收 PC 发来的 ASCII 命令字节。
 *   - 主循环轮询 DMA 写入位置，遇换行符后直接解析完整命令。
 *   - 支持 RUN=1/START（启动）、RUN=0/STOP（停机）、SPD=xxx/REF=xxx（调速）。
 */

/* USER CODE END 0 */

/**
  * @brief  应用程序入口
  * @note   执行顺序：
  *         1. HAL 库初始化
  *         2. 系统时钟配置 (HSE 24MHz → PLL → 160MHz SYSCLK)
  *         3. FOC 模型输入赋初值
  *         4. 各外设初始化 (GPIO/DMA/ADC/OPAMP/TIM/USART)
  *         5. FOC 模型初始化
  *         6. 启动电流采样 (TIM1_CH4 + ADC injected)
  *         7. 进入主循环，等待 offset 标定和上位机命令
  * @retval int  本函数永不返回（无限循环）
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /*
   * FOC 模型 (Simulink 生成代码) 输入初始化：
   * - v_bus: 先填充固定初值，防止模型在母线电压为 0 时出现除零或异常。
   *          主循环中每 10ms 通过 ADC2 regular 通道更新一次。
   * - RefSpeed: 默认 600 RPM，后续可由上位机 SPD=xxx 命令修改。
   */
  rtU.v_bus = VBUS_FIXED_VALUE;
  rtU.RefSpeed = SPEED_DEFAULT_RPM;

  /*
   * 安全策略：上电默认不启动。
   * - MotorOnOff = 0: FOC 模型内部状态机保持 IDLE，不输出 PWM。
   * - 只有同时满足 (offset_ready && Motor_state==0 && host_run_enable==1)
   *   三个条件后，主循环才会将 MotorOnOff 置 1 并启动功率 PWM。
   */
  rtU.MotorOnOff = 0U;

  /*
   * OpenLoopHold: 开环锁定时间 (秒)，由 Simulink 模型定义。
   * 设为 0 表示不使用开环拖动的延时保持功能，直接进入启动流程。
   */
  rtU.OpenLoopHold = 0.0f;
  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_ADC1_Init();
  MX_ADC2_Init();
  MX_OPAMP1_Init();
  MX_OPAMP2_Init();
  MX_OPAMP3_Init();
  MX_TIM1_Init();
  MX_TIM2_Init();
  MX_TIM4_Init();
  MX_USART3_UART_Init();
  /* USER CODE BEGIN 2 */

  /*
   * FOC 模型初始化：调用 Simulink 自动生成的 FOC_initialize()，
   * 初始化模型内部的所有状态变量、积分器、延迟单元等。
   * 必须在 TIM/ADC 等外设启动之前调用。
   */
  FOC_initialize();

  /*
   * 启动三个 OPAMP (运放)：
   * OPAMP1→A 相电流放大、OPAMP2→B 相电流放大、OPAMP3→C 相电流放大。
   * 运放配置为 PGA 模式，增益由 STM32CubeMX 在 OPAMP 初始化中配置。
   */
  HAL_OPAMP_Start(&hopamp1);
  HAL_OPAMP_Start(&hopamp2);
  HAL_OPAMP_Start(&hopamp3);

  /*
   * ADC 自校准：补偿 ADC 内部电容阵列的制造偏差。
   * 必须在 ADC 开始转换之前执行，校准期间 ADC 不能进行任何转换。
   */
  HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
  HAL_ADCEx_Calibration_Start(&hadc2, ADC_SINGLE_ENDED);

  /*
   * 初始化 TIM1 三相比较值为中点 (50% 占空比)。
   * 此时 CH1/2/3 尚未启动 PWM 输出，这里只是预填比较寄存器，
   * 确保后续启动 CH1/2/3 时不会瞬间输出一个不确定的占空比。
   */
  TIM1->CCR1 = PWM_MID_COUNTS;
  TIM1->CCR2 = PWM_MID_COUNTS;
  TIM1->CCR3 = PWM_MID_COUNTS;

  /*
   * 启动 TIM1_CH4 PWM 输出（仅 CH4，不启动 CH1/2/3）：
   * CH4 配置为 PWM2 模式，在每个 PWM 周期的特定时刻产生
   * ADC injected 触发脉冲，驱动三相电流同步采样。
   * CH4 不连接功率 MOS 管，因此不会在电机绕组上产生电压。
   */
  HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_4);
  Motor_state = 0U;  /* 标记当前仅采样、无功率输出状态 */

  /*
   * 清除 ADC JEOC (注入组转换完成) 和 EOC (常规组转换完成) 标志，
   * 防止残留标志位在上电瞬间触发意外的中断或干扰第一次采样的判断。
   * 然后启动 ADC1 注入组中断采样 (ADC2 注入组仅启动、不使用单独中断)。
   * 注意：ADC1 和 ADC2 注入组由 TIM1_CH4 的同一个触发信号同步启动，
   * 但只使能 ADC1 的注入中断——在 ADC1 的回调里统一读取两个 ADC 的数据。
   */
  __HAL_ADC_CLEAR_FLAG(&hadc1, ADC_FLAG_JEOC | ADC_FLAG_EOC);
  __HAL_ADC_CLEAR_FLAG(&hadc2, ADC_FLAG_JEOC | ADC_FLAG_EOC);
  HAL_ADCEx_InjectedStart_IT(&hadc1);
  HAL_ADCEx_InjectedStart(&hadc2);

  /*
   * 启动 USART3 RX DMA 环形接收：
   * 上位机命令很短，但 2Mbps 下单字节仅约 5us。FOC ADC 中断和 TX DMA
   * 会抢占 USART 中断，单字节 IT 接收容易 ORE/漏字节；DMA 环形缓冲先
   * 硬件收下字节，主循环再解析，可以根治“命令有时没反应”。
   */
  HostCommand_RestartDmaRx();
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */

    /*
     * 第 1 步：处理上位机命令
     * 先轮询 RX DMA 环形缓冲中的新字节并直接解析完整命令行。
     * 兼容保留 HostCommand_ProcessPending()，用于处理旧中断路径留下的
     * host_cmd_ready 命令；正常情况下 DMA 路径不会使用该标志。
     */
    HostCommand_PollDmaRx();
    HostCommand_ProcessPending();

    /*
     * 第 2 步：将上位机速度给定同步到 FOC 模型输入
     * host_ref_speed 可能被 HostCommand_Parse() 修改，每次循环都刷新。
     */
    rtU.RefSpeed = host_ref_speed;

    /*
     * 第 3 步：低频读取母线电压（ADC2 regular 通道）
     * 每 10ms 主循环执行一次，通过 ADC2 regular 转换 PA0 上的分压值。
     * 换算公式：Vbus = adc_count * (3.3V / 4096) * VBUS_ADC_SCALE
     *          = adc_count * 0.00080566 * 11.0
     * 其中 VBUS_ADC_SCALE = (100k + 10k) / 10k = 11.0（电阻分压比）。
     * PollForConversion 超时 10ms，若超时则使用旧值继续运行。
     */
    HAL_ADC_Start(&hadc2);
    HAL_ADC_PollForConversion(&hadc2, 10);
    adc_vbus = HAL_ADC_GetValue(&hadc2);
    rtU.v_bus = (float)adc_vbus * 3.3f / 4096.0f * VBUS_ADC_SCALE;

    /*
     * 第 4 步：处理上位机停机请求
     * host_stop_request 由 HostCommand_Parse() 在收到 RUN=0/STOP 时置 1。
     * 停机操作包括：MotorOnOff 清零、三相 PWM 停止、比较值回中点。
     */
    if (host_stop_request != 0U)
    {
      HostCommand_StopMotor();
      host_stop_request = 0U;
    }

    /*
     * 第 5 步：条件满足时自动启动功率 PWM
     * 三个条件缺一不可：
     *   current_offset_ready == 1  → 电流零偏已标定完成
     *   Motor_state == 0           → 尚未启动（防止重复启动）
     *   host_run_enable == 1       → 上位机已发 RUN=1
     *
     * 启动顺序：
     *   1. 先置 MotorOnOff = 1，通知 FOC 模型进入启动状态机
     *   2. 再启动 CH1/CH2/CH3 的 PWM 输出和互补输出
     *
     * 注意：CH4 在上电初始化时已经启动，此处不需要额外操作。
     */
    if ((current_offset_ready == 1U) && (Motor_state == 0U) && (host_run_enable == 1U))
    {
      rtU.MotorOnOff = 1U;   /* FOC 模型内部状态机开始走启动流程 */
      Motor_state = 1U;      /* 标记已启动，避免重复执行本段代码 */

      /* 启动三相高端 PWM 输出 (CH1/CH2/CH3) */
      HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
      HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_2);
      HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_3);

      /* 启动三相低端互补 PWM 输出 (CH1N/CH2N/CH3N) */
      HAL_TIMEx_PWMN_Start(&htim1, TIM_CHANNEL_1);
      HAL_TIMEx_PWMN_Start(&htim1, TIM_CHANNEL_2);
      HAL_TIMEx_PWMN_Start(&htim1, TIM_CHANNEL_3);
    }

    /*
     * 第 6 步：主循环延时 10ms
     * 主循环主要负责低频任务（母线电压读取、命令处理），高频 FOC 控制在
     * ADC 注入中断回调中以 10kHz 实时执行，不依赖主循环节拍。
     */
    HAL_Delay(10);
  }
  /* USER CODE END 3 */
}

/**
  * @brief  系统时钟配置
  * @note
  * 时钟树 (STM32G4xx, HSE = 24MHz 外部晶振):
  *   HSE (24MHz) → PLLM (/3) → PLL VCO 输入 = 8MHz
  *                → PLLN (×40) → VCO = 320MHz (处于 96~344MHz 合法范围)
  *                → PLLR (/2) → PLLRCLK = 160MHz (作为 SYSCLK)
  *
  * 总线时钟分配:
  *   SYSCLK = PLLRCLK = 160 MHz
  *   HCLK   = SYSCLK / 1 = 160 MHz (AHB 总线)
  *   PCLK1  = HCLK / 1   = 160 MHz (APB1, TIM2/TIM4 等)
  *   PCLK2  = HCLK / 1   = 160 MHz (APB2, TIM1/USART3/ADC 等)
  *   TIM1 定时器时钟 = PCLK2 = 160 MHz
  *     (APB2 预分频 = 1 时，定时器时钟等于 PCLK2)
  *
  * PWM 频率: f_PWM = 160MHz / (2 * 8000) = 10 kHz (周期 100 µs)
  *
  * 电压调节器: SCALE1_BOOST (最高性能，满足 160MHz 运行)
  * Flash 延迟: 4 等待周期 (匹配 160MHz HCLK)
  *
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /*
   * 配置内核电压调节器为 BOOST 模式（最高性能档）。
   * 电机 FOC 需要高计算性能，选择此档以获得最高 CPU 频率。
   */
  HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1_BOOST);

  /*
   * 配置 HSE 及 PLL:
   * - 使能外部 24MHz 晶振 (HSE_VALUE = 24000000)
   * - PLL 源 = HSE, PLLM = /3, PLLN = ×40, PLLR = /2
   * - PLL "R" 输出 = 24MHz / 3 × 40 / 2 = 160 MHz → 作为 SYSCLK
   */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = RCC_PLLM_DIV3;
  RCC_OscInitStruct.PLL.PLLN = 40;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV2;
  RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /*
   * 配置系统时钟源及总线预分频:
   * - SYSCLK = PLLCLK (PLL "R" 输出)
   * - AHB/APB1/APB2 均不分频 (÷1)，所有总线与 SYSCLK 同频
   */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */

/**
 * @brief  将浮点值钳位在 [lower, upper] 区间内
 * @param  value 输入值
 * @param  lower 下限
 * @param  upper 上限
 * @retval 钳位后的值
 * @note   纯函数，无副作用，用于限制上位机转速指令在安全范围内。
 */
static float ClampFloat(float value, float lower, float upper)
{
  if (value < lower)
  {
    return lower;
  }
  if (value > upper)
  {
    return upper;
  }
  return value;
}

/**
 * @brief  判断字符串 text 是否以 prefix 开头
 * @param  text   待检查的字符串（以 '\0' 结尾）
 * @param  prefix 前缀字符串（以 '\0' 结尾）
 * @retval 1 表示 text 以 prefix 开头；0 表示不是
 * @note   逐字符比较，直到 prefix 的 '\0' 为止。
 *         若 text 比 prefix 短，会在访问 text 字符时读到 '\0' ≠ prefix 字符，正确返回 0。
 */
static uint8_t HostCommand_StartsWith(const char *text, const char *prefix)
{
  while (*prefix != '\0')
  {
    if (*text != *prefix)
    {
      return 0U;
    }
    text++;
    prefix++;
  }
  return 1U;
}

/**
 * @brief  启动 USART3 RX DMA 环形接收
 * @note   禁用 RX DMA 半传输/传输完成中断，只在主循环轮询 DMA 写入位置。
 */
static void HostCommand_RestartDmaRx(void)
{
  host_rx_dma_last_pos = 0U;
  host_rx_index = 0U;

  if (HAL_UART_Receive_DMA(&huart3, host_rx_dma_buffer, HOST_RX_DMA_BUFFER_SIZE) != HAL_OK)
  {
    Error_Handler();
  }

  if (huart3.hdmarx != NULL)
  {
    __HAL_DMA_DISABLE_IT(huart3.hdmarx, DMA_IT_HT | DMA_IT_TC);
  }
}

/**
 * @brief  轮询 USART3 RX DMA 环形缓冲中的新增字节
 */
static void HostCommand_PollDmaRx(void)
{
  uint16_t dma_pos;

  if (huart3.hdmarx == NULL)
  {
    return;
  }

  dma_pos = (uint16_t)(HOST_RX_DMA_BUFFER_SIZE - __HAL_DMA_GET_COUNTER(huart3.hdmarx));
  if (dma_pos >= HOST_RX_DMA_BUFFER_SIZE)
  {
    dma_pos = 0U;
  }

  while (host_rx_dma_last_pos != dma_pos)
  {
    HostCommand_ProcessRxByte(host_rx_dma_buffer[host_rx_dma_last_pos]);
    host_rx_dma_last_pos++;
    if (host_rx_dma_last_pos >= HOST_RX_DMA_BUFFER_SIZE)
    {
      host_rx_dma_last_pos = 0U;
    }
  }
}

/**
 * @brief  处理 USART3 RX DMA 收到的单字节命令数据
 */
static void HostCommand_ProcessRxByte(uint8_t rx_byte)
{
  if ((rx_byte == '\n') || (rx_byte == '\r'))
  {
    if (host_rx_index > 0U)
    {
      host_rx_buffer[host_rx_index] = '\0';
      HostCommand_Parse(host_rx_buffer);
    }
    host_rx_index = 0U;
  }
  else if ((rx_byte >= 32U) && (rx_byte <= 126U))
  {
    if (host_rx_index < (HOST_CMD_BUFFER_SIZE - 1U))
    {
      host_rx_buffer[host_rx_index] = (char)rx_byte;
      host_rx_index++;
    }
    else
    {
      host_rx_index = 0U;
    }
  }
}

/**
 * @brief  处理上位机命令（主循环每 10ms 调用一次）
 * @note
 * 执行流程：
 * 1. 检查 host_cmd_ready 标志，若为 0 则直接返回（无命令待处理）。
 * 2. 若为 1，先关全局中断，将 host_cmd_line 拷贝到栈上的局部缓冲区 cmd。
 *    ——关中断是为了防止 UART 中断在拷贝期间同时写入 host_cmd_line，
 *      造成数据竞争（data race）。拷贝量仅 32 字节，中断关闭时间极短。
 * 3. 清 host_cmd_ready 标志，开中断。
 * 4. 调用 HostCommand_Parse() 解析 cmd 内容。
 *
 * 为什么需要拷贝一份？因为 HostCommand_Parse() 会原地修改字符串
 * （小写转大写），而 host_cmd_line 可能被下一帧命令覆盖。
 */
static void HostCommand_ProcessPending(void)
{
  char cmd[HOST_CMD_BUFFER_SIZE];

  if (host_cmd_ready == 0U)
  {
    return;  /* 无待处理命令，快速返回 */
  }

  /*
   * 临界区：关中断 → 拷贝 → 清标志 → 开中断。
   * 不直接操作 host_cmd_line 而是拷贝到栈上，
   * 这样 Parse 函数可以随意修改 cmd 而不影响接收缓冲。
   */
  __disable_irq();
  memcpy(cmd, host_cmd_line, HOST_CMD_BUFFER_SIZE);
  host_cmd_ready = 0U;
  __enable_irq();

  HostCommand_Parse(cmd);
}

/**
 * @brief  解析上位机 ASCII 命令
 * @param  cmd 以 '\0' 结尾的命令字符串（已在调用前从 host_cmd_line 拷贝出来）
 * @note
 * 支持的命令（大小写不敏感，解析前统一转大写）：
 *   RUN=1 或 START   → 使能电机运行 (host_run_enable = 1)
 *   RUN=0 或 STOP    → 禁止运行并请求停机
 *   SPD=xxx 或 REF=xxx → 设置目标转速，自动钳位到 [SPEED_MIN, SPEED_MAX]
 *
 * 大小写转换方式：小写字母 a-z (ASCII 97-122) 减去 32 得到大写 (65-90)。
 * 'a' - 'A' = 32，因此 cmd[i] -= 32 即可完成单个字符转换。
 *
 * 数值解析：使用标准库 strtof()，若 end_text != value_text 说明成功解析
 * 了至少一个数字；若相等则说明字符串不是有效数字，忽略本次命令。
 */
static void HostCommand_Parse(char *cmd)
{
  char *value_text;  /* 指向 "SPD=600" 中 '6' 的位置 */
  char *end_text;    /* strtof 解析结束后指向第一个非数字字符 */
  float speed;

  /*
   * 将命令字符串中的所有小写字母转为大写，实现大小写不敏感匹配。
   * 例如用户输入 "run=1" → 转为 "RUN=1"，后续 strcmp 直接比较即可。
   */
  for (uint8_t i = 0U; cmd[i] != '\0'; i++)
  {
    if ((cmd[i] >= 'a') && (cmd[i] <= 'z'))
    {
      cmd[i] = (char)(cmd[i] - ('a' - 'A'));  /* 小写 ASCII - 32 = 大写 ASCII */
    }
  }

  /* 匹配 "RUN=1" 或 "START" → 使能电机运行 */
  if ((strcmp(cmd, "RUN=1") == 0) || (strcmp(cmd, "START") == 0))
  {
    host_run_enable = 1U;
    return;
  }

  /* 匹配 "RUN=0" 或 "STOP" → 禁止运行 + 请求停机 */
  if ((strcmp(cmd, "RUN=0") == 0) || (strcmp(cmd, "STOP") == 0))
  {
    host_run_enable = 0U;
    host_stop_request = 1U;  /* 主循环检测到此标志后执行 HostCommand_StopMotor() */
    return;
  }

  /*
   * 匹配速度设置命令：SPD=xxx 或 REF=xxx
   * HostCommand_StartsWith 检查字符串前缀，&cmd[4] 跳过 "SPD=" 四个字符，
   * 指向数值部分的第一个字符。
   */
  if (HostCommand_StartsWith(cmd, "SPD=") != 0U)
  {
    value_text = &cmd[4];
  }
  else if (HostCommand_StartsWith(cmd, "REF=") != 0U)
  {
    value_text = &cmd[4];
  }
  else
  {
    return;  /* 无法识别的命令，静默忽略 */
  }

  /*
   * strtof 解析浮点数字符串：
   * - 若 value_text 以有效数字开头，end_text 将指向第一个非数字字符
   * - 若 end_text == value_text，说明一个数字都没解析到（如 "SPD=abc"），忽略
   * - 解析成功则用 ClampFloat 将值限制在安全范围内
   */
  speed = strtof(value_text, &end_text);
  if (end_text != value_text)
  {
    host_ref_speed = ClampFloat(speed, SPEED_MIN_RPM, SPEED_MAX_RPM);
  }
}

/**
 * @brief  停止电机运行
 * @note
 * 执行以下操作（顺序重要）：
 * 1. 将 MotorOnOff 清零 → 通知 FOC 模型停止输出，进入 IDLE 状态。
 * 2. 将 Motor_state 清零 → 允许后续再次自动启动。
 * 3. 将三相比较值恢复为中点 (50% 占空比) → 确保即使在 PWM 停止前
 *    仍有输出时，电机端电压也为零。
 * 4. 依次停止三相 PWM 和互补 PWM 输出 → 功率 MOS 全部关断。
 *
 * 注意：CH4 不会被停止，因为它是 ADC 触发源，需持续运行以维持电流采样。
 */
static void HostCommand_StopMotor(void)
{
  rtU.MotorOnOff = 0U;   /* FOC 模型收到 0 后进入 IDLE/停机流程 */
  Motor_state = 0U;      /* 清除启动标记，允许再次启动 */

  /*
   * 先将三相比较值设为中点 (50%)，确保在 PWM 停止前的最后一个周期
   * 也不会输出非零电压。这是防御性编程：即使后续 Stop 调用失败，
   * 比较值也已经安全。
   */
  TIM1->CCR1 = PWM_MID_COUNTS;
  TIM1->CCR2 = PWM_MID_COUNTS;
  TIM1->CCR3 = PWM_MID_COUNTS;

  /* 停止三相高端 PWM 输出 */
  HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_1);
  HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_2);
  HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_3);

  /* 停止三相低端互补 PWM 输出 */
  HAL_TIMEx_PWMN_Stop(&htim1, TIM_CHANNEL_1);
  HAL_TIMEx_PWMN_Stop(&htim1, TIM_CHANNEL_2);
  HAL_TIMEx_PWMN_Stop(&htim1, TIM_CHANNEL_3);
}

/**
 * @brief  ADC 注入组转换完成中断回调
 * @param  hadc 触发回调的 ADC 句柄
 * @note
 * 本函数是 FOC 系统的核心实时处理函数，以 10kHz 频率被调用：
 *
 * 工作流程分为两个阶段：
 *
 * 【阶段 1 — Offset 标定阶段】(current_offset_ready == 0)
 *   - 功率 PWM 尚未启动时，累加三相 ADC 原始值
 *   - 累计 N = CURRENT_ADC_SAMPLE_COUNT 次后取平均，得到零电流偏置
 *   - 置 current_offset_ready = 1，通知主循环 offset 已可用
 *
 * 【阶段 2 — FOC 运行阶段】(current_offset_ready == 1)
 *   每次进入执行以下步骤：
 *   a) 用 offset 修正电流 → 得到有符号 ADC count
 *   b) 乘以 CURRENT_ADC_TO_AMP → 转换为安培
 *   c) 计算三相电流和 (i_sum)，用于异常检测
 *   d) 调用 FOC_step() 执行一次 FOC 算法迭代
 *   e) 将 FOC 输出的比较值写入 TIM1 CCR1/2/3
 *   f) 通过 USART3 DMA 发送 VOFA JustFloat 调试帧
 *
 * 为什么只处理 ADC1 的回调？
 *   ADC1 和 ADC2 注入组由同一触发信号同步启动，转换几乎同时完成。
 *   但只有 ADC1 使能了注入中断。在 ADC1 的回调中统一读取两个 ADC
 *   的数据，避免每个 ADC 各进一次回调造成的重复计算和时序问题。
 */
void HAL_ADCEx_InjectedConvCpltCallback(ADC_HandleTypeDef* hadc)
{
  if(hadc->Instance == ADC1){
    /*
     * 读取三相电流 ADC 值：
     * ADC1 injected rank1 → A 相 (ia)
     * ADC1 injected rank2 → C 相 (ic)
     * ADC2 injected rank1 → B 相 (ib)
     *
     * 注意 ib 从 hadc2 读取，因为 B 相电流经过 OPAMP2 → ADC2 通道。
     * 三个通道在硬件上分属两个 ADC 但由同一个触发信号同步采样，
     * 因此读到的值属于同一时刻。
     */
    ia_adc = HAL_ADCEx_InjectedGetValue(&hadc1, ADC_INJECTED_RANK_1);
    ic_adc = HAL_ADCEx_InjectedGetValue(&hadc1, ADC_INJECTED_RANK_2);
    ib_adc = HAL_ADCEx_InjectedGetValue(&hadc2, ADC_INJECTED_RANK_1);

    /* 采样计数自增，调试时在观察窗口中确认该值持续增长 */
    adc_inj_count++;

    if(current_offset_ready == 0U){
      /*
       * ——— Offset 标定阶段 ———
       * 此时 TIM1 CH1/2/3 未启动，电机绕组无电流，
       * ADC 读到的值 = 零电流时的 OPAMP 偏置 + ADC 零点误差。
       * 累加后取平均即为 offset。
       */
      ia_offset_sum += ia_adc;
      ib_offset_sum += ib_adc;
      ic_offset_sum += ic_adc;

      current_offset_count++;

      if(current_offset_count >= CURRENT_ADC_SAMPLE_COUNT){
        /* 达到样本数：取平均得到三相各自的零电流偏置值 */
        ia_offset = (uint16_t)(ia_offset_sum / CURRENT_ADC_SAMPLE_COUNT);
        ib_offset = (uint16_t)(ib_offset_sum / CURRENT_ADC_SAMPLE_COUNT);
        ic_offset = (uint16_t)(ic_offset_sum / CURRENT_ADC_SAMPLE_COUNT);

        current_offset_ready = 1U;  /* 标定完成，主循环可启动功率 PWM */
      }
    }
    else{
      /*
       * ——— FOC 正常运行阶段 ———
       * 用 offset 修正电流原始值：
       * ia_raw = ia_adc - ia_offset，结果可能为负（电流负半周）。
       * 使用 int32_t 中间变量防止 uint16_t 减法溢出。
       */
      ia_raw = (int16_t)((int32_t)ia_adc - (int32_t)ia_offset);
      ib_raw = (int16_t)((int32_t)ib_adc - (int32_t)ib_offset);
      ic_raw = (int16_t)((int32_t)ic_adc - (int32_t)ic_offset);

      /* ADC count → 安培转换，填入 FOC 模型输入 */
      rtU.ia = (float)ia_raw * CURRENT_ADC_TO_AMP;
      rtU.ib = (float)ib_raw * CURRENT_ADC_TO_AMP;
      rtU.ic = (float)ic_raw * CURRENT_ADC_TO_AMP;

      /*
       * 三相电流和：根据基尔霍夫电流定律 (KCL)，
       * 星形连接的三相对称绕组中 ia + ib + ic ≡ 0。
       * 若 i_sum 持续偏离 0，可能存在：
       * - offset 标定不准确
       * - ADC 采样通道相序错误
       * - 运放或分流器硬件故障
       */
      i_sum = rtU.ia + rtU.ib + rtU.ic;

      /* 执行一次 FOC 算法迭代：包含 Clarke/Park 变换、PI 调节、SVPWM 等 */
      FOC_step();

      /*
       * 更新 PWM 比较值：
       * 若电机已启动 (Motor_state == 1)，用 FOC 输出值；
       * 否则保持中点值，确保无功率输出。
       *
       * rtY.Tcmp1/2/3 范围 0..8000，直接写入 TIM1 CCR 寄存器。
       * 这些寄存器有预装载功能 (TIM_CCR 带影子寄存器)，
       * 写入后在下个 PWM 周期开始时生效，避免 PWM 毛刺。
       */
      if (Motor_state == 1U)
      {
        TIM1->CCR1 = (uint32_t)rtY.Tcmp1;
        TIM1->CCR2 = (uint32_t)rtY.Tcmp2;
        TIM1->CCR3 = (uint32_t)rtY.Tcmp3;
      }
      else
      {
        TIM1->CCR1 = PWM_MID_COUNTS;
        TIM1->CCR2 = PWM_MID_COUNTS;
        TIM1->CCR3 = PWM_MID_COUNTS;
      }

      /*
       * VOFA JustFloat 调试数据发送：
       * 仅在 USART3 空闲时发送，若上一帧 DMA 未完成则跳过本帧。
       * 这是一种"尽力发送"策略：DMA 来不及发就丢弃当前帧，
       * 保证不阻塞 ADC 中断服务例程。
       *
       * JustFloat 帧格式 (72 字节):
       *   [0..67]: 17 个 float (小端序)
       *   [68..71]: 帧尾 0x00 0x00 0x80 0x7F
       * VOFA+ 上位机通过帧尾定位每帧边界。
       */
      if (huart3.gState == HAL_UART_STATE_READY)
      {
        load_data[0] = rtU.ia;
        load_data[1] = rtU.ib;
        load_data[2] = rtU.ic;
        load_data[3] = FluxTheta;   /* FOC 模型输出的磁链角度 (rad) */
        load_data[4] = FluxWm;      /* FOC 模型输出的机械速度 (rpm) */
        load_data[5] = rtU.RefSpeed;/* 目标转速 (RPM) */
        load_data[6] = rtU.v_bus;   /* 母线电压 (V) */
        load_data[7] = FocDiagId;
        load_data[8] = FocDiagIq;
        load_data[9] = FocDiagIdRef;
        load_data[10] = FocDiagIqRef;
        load_data[11] = FocDiagUd;
        load_data[12] = FocDiagUq;
        load_data[13] = FocDiagTcmp1;
        load_data[14] = FocDiagTcmp2;
        load_data[15] = FocDiagTcmp3;
        load_data[16] = FocDiagState;

        memcpy(tempData, (uint8_t *)load_data, sizeof(load_data));
        tempData[68] = 0x00;
        tempData[69] = 0x00;
        tempData[70] = 0x80;
        tempData[71] = 0x7F;
        HAL_UART_Transmit_DMA(&huart3, (uint8_t *)tempData, sizeof(tempData));
      }
    }
  }

}

/**
 * @brief  UART 接收完成中断回调
 * @param  huart 触发回调的 UART 句柄
 * @note
 * 当前命令接收使用 USART3 RX DMA 环形缓冲，并由主循环轮询解析。
 * 这里保留空回调，避免未来误启用 HAL 接收完成中断时重新进入旧路径。
 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
  (void)huart;
}

/**
 * @brief  UART 错误回调
 * @param  huart 触发错误的 UART 句柄
 * @note
 * UART 通信中可能发生帧错误、噪声错误、溢出错误等。
 * 错误发生后 HAL 可能停止当前接收，本回调重新启动 RX DMA 环形接收，
 * 确保通信链路在短暂干扰后能自动恢复。
 *
 * 对于这种简单的 ASCII 命令协议，出错时丢弃当前字节/命令即可，
 * 上位机可重发命令（人工操作场景，容忍偶尔丢包）。
 */
void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance == USART3)
  {
    /* 错误后重新启动 DMA 接收，丢弃可能损坏的半行命令 */
    HostCommand_RestartDmaRx();
  }
}
/* USER CODE END 4 */

/**
  * @brief  系统错误处理函数
  * @note
  * 当 HAL 库检测到无法恢复的错误时（时钟配置失败、外设初始化失败等）
  * 会调用此函数。当前实现：
  *   1. 关闭全局中断，阻止任何中断服务例程继续执行
  *   2. 进入无限循环，等待看门狗复位或用户手动复位
  *
  * 实际调试时可在 while(1) 中加入 LED 闪烁或错误代码输出，
  * 帮助定位故障原因。工程化产品中建议记录错误状态后再死循环。
  * @retval None（永不返回）
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /*
   * 关全局中断：确保外设中断不会在异常状态下继续触发，
   * 避免错误的 DMA/中断访问已损坏的数据结构。
   */
  __disable_irq();
  while (1)
  {
    /*
     * 死循环等待复位。
     * 实际产品可在此处：
     * - 翻转 LED 指示错误状态
     * - 将错误信息写入备份寄存器供下次启动读取
     * - 触发软件复位 (NVIC_SystemReset)
     */
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
