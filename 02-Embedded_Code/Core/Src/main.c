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
#define CURRENT_ADC_SAMPLE_COUNT 1024U
#define CURRENT_ADC_TO_AMP 0.0219726f

#define PWM_MID_COUNTS 4000U
#define VBUS_FIXED_VALUE 24.0f
#define VBUS_ADC_SCALE 11.0f
#define VBUS_LPF_ALPHA 0.3f
#define SPEED_DEFAULT_RPM 600.0f
#define SPEED_MIN_RPM 0.0f
#define SPEED_MAX_RPM 1200.0f
#define HOST_CMD_BUFFER_SIZE 32U

volatile uint16_t ia_adc = 0;
volatile uint16_t ib_adc = 0;
volatile uint16_t ic_adc = 0;

volatile uint32_t adc_inj_count = 0; /* ADC 注入转换回调计数，用来确认 10kHz 电流采样是否持续运行。 */

/* 三相电流去零偏后的原始 ADC count，允许为负数。 */
volatile int16_t ia_raw = 0; 
volatile int16_t ib_raw = 0;
volatile int16_t ic_raw = 0;

/* 上电后先在无驱动状态下统计零电流偏置，用于抵消 OPAMP/ADC 的静态误差。 */
volatile uint16_t ia_offset = 0;
volatile uint16_t ib_offset = 0;
volatile uint16_t ic_offset = 0;

/* offset 标定阶段的累加值，累计 CURRENT_ADC_SAMPLE_COUNT 次后求平均。 */
volatile uint32_t ia_offset_sum = 0;
volatile uint32_t ib_offset_sum = 0;
volatile uint32_t ic_offset_sum = 0;

volatile float i_sum = 0.0f; /* 三相电流和，正常应接近 0；偏大时优先查 offset、采样相序或电流方向。 */

volatile uint16_t current_offset_count = 0;
volatile uint8_t current_offset_ready = 0; /* 0: offset 标定中；1: offset 可用，可以启动功率 PWM。 */

volatile uint8_t Motor_state = 0; /* 0: 三相 PWM 未启动；1: offset 完成后已自动启动。 */

uint16_t adc_vbus = 0;       /* ADC2 regular 采到的母线电压原始值，对应 PA0 / ADC2_IN1。 */
float vbus_raw = 24.0f;      /* 按 100k/10k 分压换算出的母线电压，只用于 VOFA 观察。 */
float vbus_lpf = 24.0f;      /* 母线电压滤波值，当前作为 FOC/SVPWM 的母线电压输入。 */
uint16_t adc1_in11 = 0;      /* ADC1_IN11 速度电位器原始值，当前固定 RefSpeed 时暂不使用。 */
uint16_t finalspeed = 0;     /* 电位器换算后的目标转速，当前固定 RefSpeed 时暂不使用。 */

float load_data[8];          /* VOFA JustFloat 数据区，8 个 float 共 32 字节。 */
uint8_t tempData[36];        /* 32 字节 float 数据 + 4 字节 JustFloat 帧尾。 */

uint8_t uart_rx_byte = 0U;                         /* USART3 每次中断接收 1 个字节。 */
char host_rx_buffer[HOST_CMD_BUFFER_SIZE];         /* 正在接收的一行 ASCII 命令。 */
char host_cmd_line[HOST_CMD_BUFFER_SIZE];          /* 接收完成、等待主循环解析的命令。 */
uint8_t host_rx_index = 0U;
volatile uint8_t host_cmd_ready = 0U;
volatile uint8_t host_run_enable = 0U;             /* 上位机发 RUN=1 后才允许运行，便于安全调试。 */
volatile uint8_t host_stop_request = 0U;
volatile float host_ref_speed = SPEED_DEFAULT_RPM; /* 上位机速度给定；未连接上位机时默认 600rpm。 */
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
static float ClampFloat(float value, float lower, float upper);
static void HostCommand_ProcessPending(void);
static void HostCommand_Parse(char *cmd);
static void HostCommand_StopMotor(void);
static uint8_t HostCommand_StartsWith(const char *text, const char *prefix);

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
/*
 * FOC 启动流程：
 * 1. 上电后先只启动 TIM1_CH4，用它在 PWM 周期内触发 ADC injected 电流采样。
 * 2. ADC injected 回调先累计 1024 次三相电流原始值，计算零电流 offset。
 * 3. current_offset_ready 变成 1 后，等待上位机 RUN=1，再启动 TIM1 CH1/2/3 及互补输出，
 *    并把 MotorOnOff 置 1，让 Simulink 生成的 FOC 状态机开始启动。
 * 4. 后续每次 ADC injected 回调都会更新 ia/ib/ic，执行 FOC_step()，刷新 PWM，
 *    并通过 USART3 DMA 发送一帧 VOFA JustFloat 调试数据。
 * 5. USART3 RX 同时接收上位机 ASCII 命令：RUN=1、RUN=0、SPD=600。
 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
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
  /* 先给模型一个 24V 初值；主循环开始采样后会更新为 ADC 滤波母线电压。 */
  rtU.v_bus = VBUS_FIXED_VALUE;
  rtU.RefSpeed = SPEED_DEFAULT_RPM;

  /* 上电先不让模型进入运行状态，等待电流 offset 标定完成且上位机发 RUN=1 后再置 1。 */
  rtU.MotorOnOff = 0U;
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
  FOC_initialize();

  HAL_OPAMP_Start(&hopamp1);
  HAL_OPAMP_Start(&hopamp2);
  HAL_OPAMP_Start(&hopamp3);

  HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
  HAL_ADCEx_Calibration_Start(&hadc2, ADC_SINGLE_ENDED);

  TIM1->CCR1 = PWM_MID_COUNTS;
  TIM1->CCR2 = PWM_MID_COUNTS;
  TIM1->CCR3 = PWM_MID_COUNTS;

  /* 只先启动 TIM1_CH4：它没有功率输出，只负责在 PWM 周期内触发 ADC injected 采样。 */
  HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_4);
  Motor_state = 0U;

  /* 清掉 ADC 旧标志位，再启动注入组采样；ADC1 中断回调里统一读取三相电流。 */
  __HAL_ADC_CLEAR_FLAG(&hadc1, ADC_FLAG_JEOC | ADC_FLAG_EOC);
  __HAL_ADC_CLEAR_FLAG(&hadc2, ADC_FLAG_JEOC | ADC_FLAG_EOC);
  HAL_ADCEx_InjectedStart_IT(&hadc1);
  HAL_ADCEx_InjectedStart(&hadc2);

  /* 开启 USART3 单字节中断接收。上位机命令很短，用 ASCII 行协议更方便串口助手调试。 */
  HAL_UART_Receive_IT(&huart3, &uart_rx_byte, 1U);
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    HostCommand_ProcessPending();
    rtU.RefSpeed = host_ref_speed;

    /* 低频读取 ADC2 regular 母线电压；滤波后的 vbus_lpf 作为当前控制输入，vbus_raw 只用于观察。 */
    HAL_ADC_Start(&hadc2);
    HAL_ADC_PollForConversion(&hadc2, 10);
    adc_vbus = HAL_ADC_GetValue(&hadc2);
    vbus_raw = (float)adc_vbus * 3.3f / 4096.0f * VBUS_ADC_SCALE;
    vbus_lpf += VBUS_LPF_ALPHA * (vbus_raw - vbus_lpf);
    rtU.v_bus = vbus_lpf;

    if (host_stop_request != 0U)
    {
      HostCommand_StopMotor();
      host_stop_request = 0U;
    }

    if ((current_offset_ready == 1U) && (Motor_state == 0U) && (host_run_enable == 1U))
    {
      /* offset 完成后自动启动功率 PWM，并允许生成的 FOC 模型进入启动状态机。 */
      rtU.MotorOnOff = 1U;
      Motor_state = 1U;

      HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
      HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_2);
      HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_3);

      HAL_TIMEx_PWMN_Start(&htim1, TIM_CHANNEL_1);
      HAL_TIMEx_PWMN_Start(&htim1, TIM_CHANNEL_2);
      HAL_TIMEx_PWMN_Start(&htim1, TIM_CHANNEL_3);
    }

    HAL_Delay(10);
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1_BOOST);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
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

  /** Initializes the CPU, AHB and APB buses clocks
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

static void HostCommand_ProcessPending(void)
{
  char cmd[HOST_CMD_BUFFER_SIZE];

  if (host_cmd_ready == 0U)
  {
    return;
  }

  __disable_irq();
  memcpy(cmd, host_cmd_line, HOST_CMD_BUFFER_SIZE);
  host_cmd_ready = 0U;
  __enable_irq();

  HostCommand_Parse(cmd);
}

static void HostCommand_Parse(char *cmd)
{
  char *value_text;
  char *end_text;
  float speed;

  for (uint8_t i = 0U; cmd[i] != '\0'; i++)
  {
    if ((cmd[i] >= 'a') && (cmd[i] <= 'z'))
    {
      cmd[i] = (char)(cmd[i] - ('a' - 'A'));
    }
  }

  if ((strcmp(cmd, "RUN=1") == 0) || (strcmp(cmd, "START") == 0))
  {
    host_run_enable = 1U;
    return;
  }

  if ((strcmp(cmd, "RUN=0") == 0) || (strcmp(cmd, "STOP") == 0))
  {
    host_run_enable = 0U;
    host_stop_request = 1U;
    return;
  }

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
    return;
  }

  speed = strtof(value_text, &end_text);
  if (end_text != value_text)
  {
    host_ref_speed = ClampFloat(speed, SPEED_MIN_RPM, SPEED_MAX_RPM);
  }
}

static void HostCommand_StopMotor(void)
{
  rtU.MotorOnOff = 0U;
  Motor_state = 0U;

  TIM1->CCR1 = PWM_MID_COUNTS;
  TIM1->CCR2 = PWM_MID_COUNTS;
  TIM1->CCR3 = PWM_MID_COUNTS;

  HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_1);
  HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_2);
  HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_3);

  HAL_TIMEx_PWMN_Stop(&htim1, TIM_CHANNEL_1);
  HAL_TIMEx_PWMN_Stop(&htim1, TIM_CHANNEL_2);
  HAL_TIMEx_PWMN_Stop(&htim1, TIM_CHANNEL_3);
}

void HAL_ADCEx_InjectedConvCpltCallback(ADC_HandleTypeDef* hadc)
{
  if(hadc->Instance == ADC1){ /* ADC1 注入组完成后统一读取三相，避免 ADC1/ADC2 分别进回调造成重复计算。 */
    ia_adc = HAL_ADCEx_InjectedGetValue(&hadc1, ADC_INJECTED_RANK_1); /* ADC1 rank1: A 相电流。 */
    ic_adc = HAL_ADCEx_InjectedGetValue(&hadc1, ADC_INJECTED_RANK_2); /* ADC1 rank2: C 相电流。 */
    ib_adc = HAL_ADCEx_InjectedGetValue(&hadc2, ADC_INJECTED_RANK_1); /* ADC2 rank1: B 相电流。 */
    
    adc_inj_count++; /* 每完成一轮三相采样加 1，调试器里应持续增长。 */

    if(current_offset_ready == 0U){
      /* 功率 PWM 未启动前统计零电流 ADC 值，作为后续电流采样的 offset。 */
      ia_offset_sum += ia_adc;
      ib_offset_sum += ib_adc;
      ic_offset_sum += ic_adc;

      current_offset_count++;

      if(current_offset_count >= CURRENT_ADC_SAMPLE_COUNT){
        /* 取平均得到三相零偏；完成后主循环会自动启动三相 PWM。 */
        ia_offset = (uint16_t)(ia_offset_sum / CURRENT_ADC_SAMPLE_COUNT);
        ib_offset = (uint16_t)(ib_offset_sum / CURRENT_ADC_SAMPLE_COUNT);
        ic_offset = (uint16_t)(ic_offset_sum / CURRENT_ADC_SAMPLE_COUNT);

        current_offset_ready = 1U;
      }
    }
    else{
      /* offset 完成后，每次注入采样都转换为有符号电流，再执行一次 FOC。 */
      ia_raw = (int16_t)((int32_t)ia_adc - (int32_t)ia_offset);
      ib_raw = (int16_t)((int32_t)ib_adc - (int32_t)ib_offset);
      ic_raw = (int16_t)((int32_t)ic_adc - (int32_t)ic_offset);

      rtU.ia = (float)ia_raw * CURRENT_ADC_TO_AMP; 
      rtU.ib = (float)ib_raw * CURRENT_ADC_TO_AMP;
      rtU.ic = (float)ic_raw * CURRENT_ADC_TO_AMP;

      i_sum = rtU.ia + rtU.ib + rtU.ic;
      
      FOC_step();

      if (Motor_state == 1U)
      {
        /* FOC 输出的是 0..8000 的比较值，对应 TIM1 三相 PWM 占空比。 */
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

      /* VOFA JustFloat: 8 个 float 后接 00 00 80 7F 帧尾。 */
      load_data[0] = rtU.ia;
      load_data[1] = rtU.ib;
      load_data[2] = rtU.ic;
      load_data[3] = FluxTheta;
      load_data[4] = FluxWm;
      load_data[5] = rtU.RefSpeed;
      load_data[6] = rtU.v_bus; /* 控制实际使用的母线电压。 */
      load_data[7] = vbus_raw;  /* ADC 直接换算值，方便观察滤波前的波动。 */
      memcpy(tempData, (uint8_t *)load_data, sizeof(load_data));
      tempData[32] = 0x00;
      tempData[33] = 0x00;
      tempData[34] = 0x80;
      tempData[35] = 0x7F;
      HAL_UART_Transmit_DMA(&huart3, (uint8_t *)tempData, sizeof(tempData));
    }
  }
 
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance == USART3)
  {
    if ((uart_rx_byte == '\n') || (uart_rx_byte == '\r'))
    {
      if ((host_rx_index > 0U) && (host_cmd_ready == 0U))
      {
        memcpy(host_cmd_line, host_rx_buffer, host_rx_index);
        host_cmd_line[host_rx_index] = '\0';
        host_cmd_ready = 1U;
      }
      host_rx_index = 0U;
    }
    else if ((uart_rx_byte >= 32U) && (uart_rx_byte <= 126U))
    {
      if (host_rx_index < (HOST_CMD_BUFFER_SIZE - 1U))
      {
        host_rx_buffer[host_rx_index] = (char)uart_rx_byte;
        host_rx_index++;
      }
      else
      {
        host_rx_index = 0U;
      }
    }

    HAL_UART_Receive_IT(&huart3, &uart_rx_byte, 1U);
  }
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance == USART3)
  {
    HAL_UART_Receive_IT(&huart3, &uart_rx_byte, 1U);
  }
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
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
