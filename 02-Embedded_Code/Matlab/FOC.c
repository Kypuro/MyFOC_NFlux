/*
 * File: FOC.c
 *
 * Code generated for Simulink model 'FOC'.
 *
 * Model version                  : 1.38
 * Simulink Coder version         : 23.2 (R2023b) 01-Aug-2023
 * C/C++ source code generated on : Sun Jun 14 01:21:19 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives:
 *    1. Execution efficiency
 *    2. RAM efficiency
 * Validation result: Not run
 */

#include "FOC.h"
#include "rtwtypes.h"
#include <math.h>
#include <float.h>

/* Named constants for Chart: '<S60>/Chart' */
#define IN_AlignStage                  ((uint8_T)1U)
#define IN_IDLE                        ((uint8_T)2U)
#define IN_OpenStage                   ((uint8_T)3U)
#define IN_RunStage                    ((uint8_T)4U)
#define IN_ThetaAlign                  ((uint8_T)5U)
#define period                         (0.0001)
#ifndef UCHAR_MAX
#include <limits.h>
#endif

#if ( UCHAR_MAX != (0xFFU) ) || ( SCHAR_MAX != (0x7F) )
#error Code was generated for compiler with different sized uchar/char. \
Consider adjusting Test hardware word size settings on the \
Hardware Implementation pane to match your compiler word sizes as \
defined in limits.h of the compiler. Alternatively, you can \
select the Test hardware is the same as production hardware option and \
select the Enable portable word sizes option on the Code Generation > \
Verification pane for ERT based targets, which will disable the \
preprocessor word size checks.
#endif

#if ( USHRT_MAX != (0xFFFFU) ) || ( SHRT_MAX != (0x7FFF) )
#error Code was generated for compiler with different sized ushort/short. \
Consider adjusting Test hardware word size settings on the \
Hardware Implementation pane to match your compiler word sizes as \
defined in limits.h of the compiler. Alternatively, you can \
select the Test hardware is the same as production hardware option and \
select the Enable portable word sizes option on the Code Generation > \
Verification pane for ERT based targets, which will disable the \
preprocessor word size checks.
#endif

#if ( UINT_MAX != (0xFFFFFFFFU) ) || ( INT_MAX != (0x7FFFFFFF) )
#error Code was generated for compiler with different sized uint/int. \
Consider adjusting Test hardware word size settings on the \
Hardware Implementation pane to match your compiler word sizes as \
defined in limits.h of the compiler. Alternatively, you can \
select the Test hardware is the same as production hardware option and \
select the Enable portable word sizes option on the Code Generation > \
Verification pane for ERT based targets, which will disable the \
preprocessor word size checks.
#endif

#if ( ULONG_MAX != (0xFFFFFFFFU) ) || ( LONG_MAX != (0x7FFFFFFF) )
#error Code was generated for compiler with different sized ulong/long. \
Consider adjusting Test hardware word size settings on the \
Hardware Implementation pane to match your compiler word sizes as \
defined in limits.h of the compiler. Alternatively, you can \
select the Test hardware is the same as production hardware option and \
select the Enable portable word sizes option on the Code Generation > \
Verification pane for ERT based targets, which will disable the \
preprocessor word size checks.
#endif

/* Skipping ulong_long/long_long check: insufficient preprocessor integer range. */

/* Exported block signals */
real32_T FluxWm;                       /* '<S62>/sum' */
real32_T FluxTheta;                    /* '<S63>/mod' */
real32_T FocDiagId;
real32_T FocDiagIq;
real32_T FocDiagIdRef;
real32_T FocDiagIqRef;
real32_T FocDiagUd;
real32_T FocDiagUq;
real32_T FocDiagTcmp1;
real32_T FocDiagTcmp2;
real32_T FocDiagTcmp3;
real32_T FocDiagState;

/* Exported data definition */

/* Definition for custom storage class: Struct */
curr_kpki_type curr_kpki = {
  /* curr_d_ki */
  35.0F,

  /* curr_d_kp */
  0.017F,

  /* curr_q_ki */
  35.0F,

  /* curr_q_kp */
  0.017F
};

handover_cfg_type handover_cfg = {
  /* iq_handover */
  0.4F,

  /* iq_ref_slew_down */
  2.0F,

  /* theta_handover_slew_limit */
  5.0F
};

motor_type motor = {
  /* L */
  0.00535F,

  /* Pn */
  4.0F,

  /* Rs */
  6.97F,

  /* flux */
  0.016884F
};

nflux_obs_type nflux_obs = {
  /* Gamma */
  100000.0F,

  /* LPF_K */
  0.003F,

  /* PLL_Ki */
  2500.0F,

  /* PLL_Kp */
  212.1F
};

spd_kpki_type spd_kpki = {
  /* spd_ki */
  0.00165394868F,

  /* spd_kp */
  0.001550577F
};

/* Block signals and states (default storage) */
DW rtDW;

/* External inputs (root inport signals with default storage) */
ExtU rtU;

/* External outputs (root outports fed by signals with default storage) */
ExtY rtY;

/* Real-time model */
static RT_MODEL rtM_;
RT_MODEL *const rtM = &rtM_;
extern real32_T rt_modf(real32_T u0, real32_T u1);
static void Clark(real32_T rtu_ia, real32_T rtu_ib, real32_T rtu_ic, real32_T
                  *rty_ialpha, real32_T *rty_ibeta);
static void In_park(real32_T rtu_ud, real32_T rtu_uq, real32_T rtu_theta_sin,
                    real32_T rtu_theta_cos, real32_T *rty_ualpha, real32_T
                    *rty_ubeta);
static void Park(real32_T rtu_ialpha, real32_T rtu_ibeta, real32_T rtu_theta_sin,
                 real32_T rtu_theta_cos, real32_T *rty_id, real32_T *rty_iq);
static void SVPWM(real32_T rtu_u_alpha, real32_T rtu_u_beta, real32_T rtu_v_bus,
                  real32_T rty_tABC[3]);
static void rate_scheduler(void);

/*
 *         This function updates active task flag for each subrate.
 *         The function is called at model base rate, hence the
 *         generated code self-manages all its subrates.
 */
static void rate_scheduler(void)
{
  /* Compute which subrates run during the next base time step.  Subrates
   * are an integer multiple of the base rate counter.  Therefore, the subtask
   * counter is reset when it reaches its limit (zero means run).
   */
  (rtM->Timing.TaskCounters.TID[1])++;
  if ((rtM->Timing.TaskCounters.TID[1]) > 9) {/* Sample time: [0.001s, 0.0s] */
    rtM->Timing.TaskCounters.TID[1] = 0;
  }
}

/* Output and update for atomic system: '<S3>/Clark' */
static void Clark(real32_T rtu_ia, real32_T rtu_ib, real32_T rtu_ic, real32_T
                  *rty_ialpha, real32_T *rty_ibeta)
{
  /* Sum: '<S55>/Add1' incorporates:
   *  Gain: '<S55>/Gain'
   *  Gain: '<S55>/Gain1'
   *  Sum: '<S55>/Add'
   */
  *rty_ialpha = 0.666666687F * rtu_ia - (rtu_ib + rtu_ic) * 0.333333343F;

  /* Gain: '<S55>/Gain2' incorporates:
   *  Sum: '<S55>/Add2'
   */
  *rty_ibeta = (rtu_ib - rtu_ic) * 0.577350259F;
}

/* Output and update for atomic system: '<S3>/In_park' */
static void In_park(real32_T rtu_ud, real32_T rtu_uq, real32_T rtu_theta_sin,
                    real32_T rtu_theta_cos, real32_T *rty_ualpha, real32_T
                    *rty_ubeta)
{
  /* Sum: '<S56>/Add' incorporates:
   *  Product: '<S56>/Product'
   *  Product: '<S56>/Product1'
   */
  *rty_ualpha = rtu_ud * rtu_theta_cos - rtu_uq * rtu_theta_sin;

  /* Sum: '<S56>/Add1' incorporates:
   *  Product: '<S56>/Product2'
   *  Product: '<S56>/Product3'
   */
  *rty_ubeta = rtu_ud * rtu_theta_sin + rtu_uq * rtu_theta_cos;
}

/* Output and update for atomic system: '<S3>/Park' */
static void Park(real32_T rtu_ialpha, real32_T rtu_ibeta, real32_T rtu_theta_sin,
                 real32_T rtu_theta_cos, real32_T *rty_id, real32_T *rty_iq)
{
  /* Sum: '<S58>/Add' incorporates:
   *  Product: '<S58>/Product'
   *  Product: '<S58>/Product1'
   */
  *rty_id = rtu_ialpha * rtu_theta_cos + rtu_ibeta * rtu_theta_sin;

  /* Sum: '<S58>/Add1' incorporates:
   *  Product: '<S58>/Product2'
   *  Product: '<S58>/Product3'
   */
  *rty_iq = rtu_ibeta * rtu_theta_cos - rtu_ialpha * rtu_theta_sin;
}

/* Output and update for atomic system: '<S3>/SVPWM' */
static void SVPWM(real32_T rtu_u_alpha, real32_T rtu_u_beta, real32_T rtu_v_bus,
                  real32_T rty_tABC[3])
{
  real32_T rtb_Min;
  real32_T rtb_Sum1_h;
  real32_T rtb_Sum_f;

  /* Gain: '<S114>/Gain' */
  rtb_Min = -0.5F * rtu_u_alpha;

  /* Gain: '<S114>/Gain1' */
  rtb_Sum1_h = 0.866025388F * rtu_u_beta;

  /* Sum: '<S114>/Sum' */
  rtb_Sum_f = rtb_Min + rtb_Sum1_h;

  /* Sum: '<S114>/Sum1' */
  rtb_Sum1_h = rtb_Min - rtb_Sum1_h;

  /* Gain: '<S116>/Gain' incorporates:
   *  MinMax: '<S116>/Min'
   *  MinMax: '<S116>/Min1'
   *  Sum: '<S116>/Sum'
   */
  rtb_Min = (fminf(fminf(rtu_u_alpha, rtb_Sum_f), rtb_Sum1_h) + fmaxf(fmaxf
              (rtu_u_alpha, rtb_Sum_f), rtb_Sum1_h)) * -0.5F;

  /* Sum: '<S59>/Sum' */
  rty_tABC[0] = rtb_Min + rtu_u_alpha;
  rty_tABC[1] = rtb_Min + rtb_Sum_f;
  rty_tABC[2] = rtb_Min + rtb_Sum1_h;

  /* Gain: '<S59>/PWM_HalfPeriod' incorporates:
   *  Constant: '<S59>/Constant'
   *  Gain: '<S59>/Gain'
   *  Product: '<S59>/Divide'
   *  Sum: '<S59>/Sum1'
   */
  rty_tABC[0] = (-rty_tABC[0] / rtu_v_bus + 0.5F) * 8000.0F;
  rty_tABC[1] = (-rty_tABC[1] / rtu_v_bus + 0.5F) * 8000.0F;
  rty_tABC[2] = (-rty_tABC[2] / rtu_v_bus + 0.5F) * 8000.0F;
}

real32_T rt_modf(real32_T u0, real32_T u1)
{
  real32_T y;
  y = u0;
  if (u1 == 0.0F) {
    if (u0 == 0.0F) {
      y = u1;
    }
  } else if (u0 == 0.0F) {
    y = 0.0F / u1;
  } else {
    boolean_T yEq;
    y = fmodf(u0, u1);
    yEq = (y == 0.0F);
    if ((!yEq) && (u1 > floorf(u1))) {
      real32_T q;
      q = fabsf(u0 / u1);
      yEq = (fabsf(q - floorf(q + 0.5F)) <= FLT_EPSILON * q);
    }

    if (yEq) {
      y = 0.0F;
    } else if ((u0 < 0.0F) != (u1 < 0.0F)) {
      y += u1;
    }
  }

  return y;
}

/* Model step function */
void FOC_step(void)
{
  real32_T rtb_PWM_HalfPeriod[3];
  real32_T rtb_Add1;
  real32_T rtb_Add1_k;
  real32_T rtb_Add_d;
  real32_T rtb_Cos;
  real32_T rtb_DeadZone_fw;
  real32_T rtb_DiscreteTimeIntegrator;
  real32_T rtb_Gain2;
  real32_T rtb_IProdOut;
  real32_T rtb_Integrator_jp;
  real32_T rtb_Integrator_l_tmp;
  real32_T rtb_Saturation_l;
  real32_T rtb_Sin;
  real32_T rtb_theta;
  uint32_T Speed_loop_ELAPS_T;
  int16_T rtb_IProdOut_c;
  int8_T tmp;
  int8_T tmp_0;

  /* Outputs for Atomic SubSystem: '<S3>/Clark' */
  /* Inport: '<Root>/ia' incorporates:
   *  Inport: '<Root>/ib'
   *  Inport: '<Root>/ic'
   */
  Clark(rtU.ia, rtU.ib, rtU.ic, &rtb_Add1_k, &rtb_Gain2);

  /* End of Outputs for SubSystem: '<S3>/Clark' */

  /* Chart: '<S60>/Chart' incorporates:
   *  Inport: '<Root>/MotorOnOff'
   *  Inport: '<Root>/OpenLoopHold'
   */
  if (rtDW.temporalCounter_i1 < 32767U) {
    rtDW.temporalCounter_i1++;
  }

  if (rtDW.is_active_c3_FOC == 0U) {
    rtDW.is_active_c3_FOC = 1U;
    rtDW.is_c3_FOC = IN_IDLE;
  } else {
    switch (rtDW.is_c3_FOC) {
     case IN_AlignStage:
      if (rtDW.temporalCounter_i1 >= 1000) {
        rtDW.temporalCounter_i1 = 0U;
        rtDW.is_c3_FOC = IN_OpenStage;
        rtDW.cnt = 0.0;
      } else if (!rtU.MotorOnOff) {
        rtDW.is_c3_FOC = IN_IDLE;
      } else {
        rtDW.ZReset = 0.0;
        rtDW.Motor_state = 2.0;
        rtDW.RestsSingal = 0.0;
      }
      break;

     case IN_IDLE:
      if (rtU.MotorOnOff) {
        rtDW.temporalCounter_i1 = 0U;
        rtDW.is_c3_FOC = IN_AlignStage;
      } else {
        rtDW.ZReset = 0.0;
        rtDW.Motor_state = 1.0;
        rtDW.RestsSingal = 0.0;
      }
      break;

     case IN_OpenStage:
      if ((rtDW.temporalCounter_i1 >= 30000) && (rtU.OpenLoopHold == 0.0F)) {
        rtDW.temporalCounter_i1 = 0U;
        rtDW.is_c3_FOC = IN_ThetaAlign;
      } else if (!rtU.MotorOnOff) {
        rtDW.is_c3_FOC = IN_IDLE;
      } else {
        rtDW.Motor_state = 3.0;
        rtDW.RestsSingal = 0.0;
        if (rtDW.cnt == 0.0) {
          rtDW.ZReset = 1.0;
          rtDW.cnt = 1.0;
        } else {
          rtDW.ZReset = 0.0;
        }
      }
      break;

     case IN_RunStage:
      if (!rtU.MotorOnOff) {
        rtDW.is_c3_FOC = IN_IDLE;
      } else {
        rtDW.ZReset = 0.0;
        rtDW.Motor_state = 5.0;
        rtDW.RestsSingal = 1.0;
      }
      break;

     default:
      /* case IN_ThetaAlign: */
      if (rtDW.temporalCounter_i1 >= 5000) {
        rtDW.is_c3_FOC = IN_RunStage;
      } else if (!rtU.MotorOnOff) {
        rtDW.is_c3_FOC = IN_IDLE;
      } else {
        rtDW.ZReset = 0.0;
        rtDW.Motor_state = 4.0;
        rtDW.RestsSingal = 0.0;
      }
      break;
    }
  }

  /* End of Chart: '<S60>/Chart' */

  /* RateTransition: '<S1>/Rate Transition3' */
  if (rtM->Timing.TaskCounters.TID[1] == 0) {
    /* RateTransition: '<S1>/Rate Transition3' */
    rtDW.RateTransition3 = rtDW.RateTransition3_Buffer0;
  }

  /* End of RateTransition: '<S1>/Rate Transition3' */

  /* SwitchCase: '<S60>/Switch Case' */
  switch ((int32_T)rtDW.Motor_state) {
   case 1:
    /* Outputs for IfAction SubSystem: '<S60>/If Action Subsystem' incorporates:
     *  ActionPort: '<S118>/Action Port'
     */
    /* Merge: '<S60>/Merge' incorporates:
     *  Constant: '<S118>/Constant'
     *  SignalConversion generated from: '<S118>/theta_fd'
     */
    rtDW.Merge = 0.0F;

    /* Merge: '<S60>/Merge1' incorporates:
     *  Constant: '<S118>/Constant1'
     *  SignalConversion generated from: '<S118>/iq_ref'
     */
    rtDW.Merge1 = 0.0F;

    /* End of Outputs for SubSystem: '<S60>/If Action Subsystem' */
    break;

   case 2:
    /* Outputs for IfAction SubSystem: '<S60>/If Action Subsystem1' incorporates:
     *  ActionPort: '<S119>/Action Port'
     */
    /* Merge: '<S60>/Merge' incorporates:
     *  Constant: '<S119>/Constant'
     *  SignalConversion generated from: '<S119>/theta_fd'
     */
    rtDW.Merge = 0.0F;

    /* Merge: '<S60>/Merge1' incorporates:
     *  Constant: '<S119>/Constant1'
     *  SignalConversion generated from: '<S119>/iq_ref'
     */
    rtDW.Merge1 = 1.0F;

    /* End of Outputs for SubSystem: '<S60>/If Action Subsystem1' */
    break;

   case 3:
    /* Outputs for IfAction SubSystem: '<S60>/If Action Subsystem2' incorporates:
     *  ActionPort: '<S120>/Action Port'
     */
    /* DiscreteIntegrator: '<S120>/Discrete-Time Integrator' */
    if ((rtDW.ZReset > 0.0) && (rtDW.DiscreteTimeIntegrator_PrevRese <= 0)) {
      rtDW.DiscreteTimeIntegrator_DSTATE_l = 0.0F;
    }

    rtb_DiscreteTimeIntegrator = rtDW.DiscreteTimeIntegrator_DSTATE_l;

    /* End of DiscreteIntegrator: '<S120>/Discrete-Time Integrator' */

    /* DiscreteIntegrator: '<S120>/Discrete-Time Integrator1' */
    if ((rtDW.ZReset > 0.0) && (rtDW.DiscreteTimeIntegrator1_PrevRes <= 0)) {
      rtDW.DiscreteTimeIntegrator1_DSTAT_m = 0.0F;
    }

    /* Merge: '<S60>/Merge' incorporates:
     *  Constant: '<S120>/Constant'
     *  DiscreteIntegrator: '<S120>/Discrete-Time Integrator1'
     *  Math: '<S120>/Mod'
     *  SignalConversion generated from: '<S120>/theta_fd'
     */
    rtDW.Merge = rt_modf(rtDW.DiscreteTimeIntegrator1_DSTAT_m, 6.28318548F);

    /* Merge: '<S60>/Merge1' incorporates:
     *  Constant: '<S120>/Constant2'
     *  SignalConversion generated from: '<S120>/iq_ref'
     */
    rtDW.Merge1 = 1.0F;

    /* Update for DiscreteIntegrator: '<S120>/Discrete-Time Integrator' incorporates:
     *  Gain: '<S120>/Gain'
     *  Product: '<S120>/Product'
     */
    rtDW.DiscreteTimeIntegrator_DSTATE_l += motor.Pn * 62.8318558F *
      0.333333343F * 0.0001F;
    if (rtDW.ZReset > 0.0) {
      rtDW.DiscreteTimeIntegrator_PrevRese = 1;
    } else if (rtDW.ZReset < 0.0) {
      rtDW.DiscreteTimeIntegrator_PrevRese = -1;
    } else if (rtDW.ZReset == 0.0) {
      rtDW.DiscreteTimeIntegrator_PrevRese = 0;
    } else {
      rtDW.DiscreteTimeIntegrator_PrevRese = 2;
    }

    /* End of Update for DiscreteIntegrator: '<S120>/Discrete-Time Integrator' */

    /* Update for DiscreteIntegrator: '<S120>/Discrete-Time Integrator1' */
    rtDW.DiscreteTimeIntegrator1_DSTAT_m += 0.0001F * rtb_DiscreteTimeIntegrator;
    if (rtDW.ZReset > 0.0) {
      rtDW.DiscreteTimeIntegrator1_PrevRes = 1;
    } else if (rtDW.ZReset < 0.0) {
      rtDW.DiscreteTimeIntegrator1_PrevRes = -1;
    } else if (rtDW.ZReset == 0.0) {
      rtDW.DiscreteTimeIntegrator1_PrevRes = 0;
    } else {
      rtDW.DiscreteTimeIntegrator1_PrevRes = 2;
    }

    /* End of Update for DiscreteIntegrator: '<S120>/Discrete-Time Integrator1' */
    /* End of Outputs for SubSystem: '<S60>/If Action Subsystem2' */
    break;

   case 4:
    /* Outputs for IfAction SubSystem: '<S60>/If Action Subsystem4' incorporates:
     *  ActionPort: '<S122>/Action Port'
     */
    /* Math: '<S122>/Mod' incorporates:
     *  Constant: '<S122>/Constant'
     *  DiscreteIntegrator: '<S122>/Discrete-Time Integrator1'
     */
    rtb_theta = rt_modf(rtDW.DiscreteTimeIntegrator1_DSTATE, 6.28318548F);

    /* If: '<S122>/If' incorporates:
     *  Constant: '<S122>/Constant1'
     *  Constant: '<S123>/Constant'
     *  Constant: '<S127>/Const_2pi_a'
     *  Constant: '<S127>/Const_pi_a'
     *  Constant: '<S127>/Const_pi_b'
     *  Math: '<S127>/Mod_2pi'
     *  Product: '<S127>/Alpha_times_delta'
     *  SignalConversion generated from: '<S123>/Out1'
     *  Sum: '<S122>/Add'
     *  Sum: '<S127>/Add_pi'
     *  Sum: '<S127>/Delta_hat_open'
     *  Sum: '<S127>/Sub_pi'
     *  UnitDelay: '<S122>/Unit Delay'
     *  UnitDelay: '<S60>/Unit Delay1'
     */
    if (rtDW.UnitDelay_DSTATE + 0.001F >= 1.0F) {
      /* Outputs for IfAction SubSystem: '<S122>/If Action Subsystem' incorporates:
       *  ActionPort: '<S123>/Action Port'
       */
      rtb_DiscreteTimeIntegrator = 1.0F;

      /* End of Outputs for SubSystem: '<S122>/If Action Subsystem' */
    } else {
      rtb_DiscreteTimeIntegrator = rtDW.UnitDelay_DSTATE + 0.001F;
    }

    /* Outputs for Atomic SubSystem: '<S122>/ThetaShortestBlend' */
    rtb_Saturation_l = (rt_modf((FluxTheta - rtb_theta) + 3.14159274F,
      6.28318548F) - 3.14159274F) * rtb_DiscreteTimeIntegrator;

    /* End of If: '<S122>/If' */

    /* RateLimiter: '<S127>/CorrectionRateLimit' */
    rtb_IProdOut = rtb_Saturation_l - rtDW.PrevY;
    rtb_DiscreteTimeIntegrator = (real32_T)
      (handover_cfg.theta_handover_slew_limit * period);
    if (rtb_IProdOut > rtb_DiscreteTimeIntegrator) {
      rtb_Saturation_l = rtb_DiscreteTimeIntegrator + rtDW.PrevY;
    } else {
      rtb_DiscreteTimeIntegrator = (real32_T)
        (-handover_cfg.theta_handover_slew_limit * period);
      if (rtb_IProdOut < rtb_DiscreteTimeIntegrator) {
        rtb_Saturation_l = rtb_DiscreteTimeIntegrator + rtDW.PrevY;
      }
    }

    rtDW.PrevY = rtb_Saturation_l;

    /* End of RateLimiter: '<S127>/CorrectionRateLimit' */

    /* Merge: '<S60>/Merge' incorporates:
     *  Constant: '<S127>/Const_2pi_b'
     *  Math: '<S127>/Wrap_2pi'
     *  SignalConversion generated from: '<S122>/Theta_fd'
     *  Sum: '<S127>/Add_correction'
     */
    rtDW.Merge = rt_modf(rtb_theta + rtb_Saturation_l, 6.28318548F);

    /* End of Outputs for SubSystem: '<S122>/ThetaShortestBlend' */

    /* Saturate: '<S122>/Saturation' incorporates:
     *  Constant: '<S122>/Constant2'
     *  DiscreteIntegrator: '<S122>/Discrete-Time Integrator'
     *  Sum: '<S122>/Sum'
     */
    if (1.0F - rtDW.DiscreteTimeIntegrator_DSTATE > 1.0F) {
      /* Merge: '<S60>/Merge1' incorporates:
       *  SignalConversion generated from: '<S122>/iq_ref'
       */
      rtDW.Merge1 = 1.0F;
    } else if (1.0F - rtDW.DiscreteTimeIntegrator_DSTATE <
               handover_cfg.iq_handover) {
      /* Merge: '<S60>/Merge1' incorporates:
       *  SignalConversion generated from: '<S122>/iq_ref'
       */
      rtDW.Merge1 = handover_cfg.iq_handover;
    } else {
      /* Merge: '<S60>/Merge1' incorporates:
       *  SignalConversion generated from: '<S122>/iq_ref'
       */
      rtDW.Merge1 = 1.0F - rtDW.DiscreteTimeIntegrator_DSTATE;
    }

    /* End of Saturate: '<S122>/Saturation' */

    /* Update for UnitDelay: '<S122>/Unit Delay' incorporates:
     *  Constant: '<S122>/Constant1'
     *  Sum: '<S122>/Add'
     */
    rtDW.UnitDelay_DSTATE += 0.001F;

    /* Update for DiscreteIntegrator: '<S122>/Discrete-Time Integrator1' incorporates:
     *  Gain: '<S122>/Gain'
     */
    rtDW.DiscreteTimeIntegrator1_DSTATE += motor.Pn * 62.8318558F * 0.0001F;

    /* Update for DiscreteIntegrator: '<S122>/Discrete-Time Integrator' incorporates:
     *  Constant: '<S122>/Constant5'
     */
    rtDW.DiscreteTimeIntegrator_DSTATE += 0.0001F *
      handover_cfg.iq_ref_slew_down;

    /* End of Outputs for SubSystem: '<S60>/If Action Subsystem4' */
    break;

   case 5:
    /* Outputs for IfAction SubSystem: '<S60>/If Action Subsystem3' incorporates:
     *  ActionPort: '<S121>/Action Port'
     */
    /* Merge: '<S60>/Merge' incorporates:
     *  SignalConversion generated from: '<S121>/theta_Close'
     *  UnitDelay: '<S60>/Unit Delay1'
     */
    rtDW.Merge = FluxTheta;

    /* Merge: '<S60>/Merge1' incorporates:
     *  SignalConversion generated from: '<S121>/iq_CloseRef'
     */
    rtDW.Merge1 = rtDW.RateTransition3;

    /* End of Outputs for SubSystem: '<S60>/If Action Subsystem3' */
    break;
  }

  /* End of SwitchCase: '<S60>/Switch Case' */

  /* Trigonometry: '<S3>/Sin' */
  rtb_Sin = sinf(rtDW.Merge);

  /* Trigonometry: '<S3>/Cos' */
  rtb_Cos = cosf(rtDW.Merge);

  /* Outputs for Atomic SubSystem: '<S3>/Park' */
  Park(rtb_Add1_k, rtb_Gain2, rtb_Sin, rtb_Cos, &rtb_DiscreteTimeIntegrator,
       &rtb_Integrator_jp);

  /* End of Outputs for SubSystem: '<S3>/Park' */
  FocDiagId = rtb_DiscreteTimeIntegrator;
  FocDiagIq = rtb_Integrator_jp;
  FocDiagIdRef = 0.0F;
  FocDiagIqRef = rtDW.Merge1;
  FocDiagState = (real32_T)rtDW.Motor_state;

  /* Sum: '<S61>/Sum1' incorporates:
   *  Constant: '<S61>/Constant'
   */
  rtb_theta = 0.0F - rtb_DiscreteTimeIntegrator;

  /* Sum: '<S172>/Sum' incorporates:
   *  Constant: '<S61>/Constant'
   *  Constant: '<S61>/Constant3'
   *  DiscreteIntegrator: '<S163>/Integrator'
   *  Product: '<S168>/PProd Out'
   *  Sum: '<S61>/Sum1'
   */
  rtb_Saturation_l = (0.0F - rtb_DiscreteTimeIntegrator) * curr_kpki.curr_d_kp +
    (real32_T)rtDW.Integrator_DSTATE_h * 0.0001F;

  /* Sum: '<S61>/Sum7' */
  rtb_IProdOut = rtDW.Merge1 - rtb_Integrator_jp;

  /* Sum: '<S222>/Sum' incorporates:
   *  Constant: '<S61>/Constant1'
   *  DiscreteIntegrator: '<S213>/Integrator'
   *  Product: '<S218>/PProd Out'
   */
  rtb_DeadZone_fw = rtb_IProdOut * curr_kpki.curr_q_kp + rtDW.Integrator_DSTATE;

  /* Saturate: '<S170>/Saturation' */
  if (rtb_Saturation_l > 12.4707661F) {
    rtb_DiscreteTimeIntegrator = 12.4707661F;
  } else if (rtb_Saturation_l < -12.4707661F) {
    rtb_DiscreteTimeIntegrator = -12.4707661F;
  } else {
    rtb_DiscreteTimeIntegrator = rtb_Saturation_l;
  }

  /* Saturate: '<S220>/Saturation' */
  if (rtb_DeadZone_fw > 12.4707661F) {
    rtb_Integrator_jp = 12.4707661F;
  } else if (rtb_DeadZone_fw < -12.4707661F) {
    rtb_Integrator_jp = -12.4707661F;
  } else {
    rtb_Integrator_jp = rtb_DeadZone_fw;
  }

  /* Outputs for Atomic SubSystem: '<S3>/In_park' */
  /* Saturate: '<S170>/Saturation' incorporates:
   *  Saturate: '<S220>/Saturation'
   */
  FocDiagUd = rtb_DiscreteTimeIntegrator;
  FocDiagUq = rtb_Integrator_jp;

  In_park(rtb_DiscreteTimeIntegrator, rtb_Integrator_jp, rtb_Sin, rtb_Cos,
          &rtb_Add_d, &rtb_Add1);

  /* End of Outputs for SubSystem: '<S3>/In_park' */

  /* Outputs for Atomic SubSystem: '<S3>/SVPWM' */
  /* Inport: '<Root>/v_bus' */
  SVPWM(rtb_Add_d, rtb_Add1, rtU.v_bus, rtb_PWM_HalfPeriod);

  /* End of Outputs for SubSystem: '<S3>/SVPWM' */

  /* Outport: '<Root>/Tcmp1' */
  rtY.Tcmp1 = rtb_PWM_HalfPeriod[0];
  FocDiagTcmp1 = rtY.Tcmp1;

  /* Outport: '<Root>/Tcmp2' */
  rtY.Tcmp2 = rtb_PWM_HalfPeriod[1];
  FocDiagTcmp2 = rtY.Tcmp2;

  /* Outport: '<Root>/Tcmp3' */
  rtY.Tcmp3 = rtb_PWM_HalfPeriod[2];
  FocDiagTcmp3 = rtY.Tcmp3;

  /* Gain: '<S64>/L_eta2_prev' incorporates:
   *  Gain: '<S64>/L_eta2_now'
   */
  rtb_Cos = motor.L * rtb_Gain2;

  /* Sum: '<S64>/eta2_prev' incorporates:
   *  Gain: '<S64>/L_eta2_prev'
   *  UnitDelay: '<S64>/x2_delay'
   */
  rtb_Sin = rtDW.x2_delay_DSTATE - rtb_Cos;

  /* Gain: '<S64>/L_eta1_prev' incorporates:
   *  Gain: '<S64>/L_eta1_now'
   */
  rtb_Integrator_l_tmp = motor.L * rtb_Add1_k;

  /* Sum: '<S64>/eta1_prev' incorporates:
   *  Gain: '<S64>/L_eta1_prev'
   *  UnitDelay: '<S64>/x1_delay'
   */
  rtb_Integrator_jp = rtDW.x1_delay_DSTATE - rtb_Integrator_l_tmp;

  /* Sum: '<S64>/flux_norm_error' incorporates:
   *  Constant: '<S64>/flux_sq'
   *  Math: '<S64>/eta1_sq'
   *  Math: '<S64>/eta2_sq'
   *  Sum: '<S64>/eta_norm2'
   *
   * About '<S64>/eta1_sq':
   *  Operator: magnitude^2
   *
   * About '<S64>/eta2_sq':
   *  Operator: magnitude^2
   */
  rtb_DiscreteTimeIntegrator = motor.flux * motor.flux - (rtb_Integrator_jp *
    rtb_Integrator_jp + rtb_Sin * rtb_Sin);

  /* Sum: '<S64>/x1_hat_k1' incorporates:
   *  Constant: '<S64>/Gamma2'
   *  Gain: '<S64>/Rs_i2'
   *  Gain: '<S64>/Ts_rhs2'
   *  Product: '<S64>/gamma_eta2_err'
   *  Sum: '<S64>/observer_rhs2'
   *  Sum: '<S64>/y2'
   *  UnitDelay: '<S64>/x2_delay'
   */
  rtb_Add1 = (rtb_Sin * rtb_DiscreteTimeIntegrator * nflux_obs.Gamma + (rtb_Add1
    - motor.Rs * rtb_Gain2)) * 0.0001F + rtDW.x2_delay_DSTATE;

  /* Sum: '<S64>/x1_hat_k' incorporates:
   *  Constant: '<S64>/Gamma1'
   *  Gain: '<S64>/Rs_i1'
   *  Gain: '<S64>/Ts_rhs1'
   *  Product: '<S64>/gamma_eta1_err'
   *  Sum: '<S64>/observer_rhs1'
   *  Sum: '<S64>/y1'
   *  UnitDelay: '<S64>/x1_delay'
   */
  rtb_Integrator_jp = ((rtb_Add_d - motor.Rs * rtb_Add1_k) + rtb_Integrator_jp *
                       rtb_DiscreteTimeIntegrator * nflux_obs.Gamma) * 0.0001F +
    rtDW.x1_delay_DSTATE;

  /* Sum: '<S63>/theta_error' incorporates:
   *  Gain: '<S64>/inv_flux1'
   *  Gain: '<S64>/inv_flux2'
   *  Product: '<S63>/cos_sin_theta'
   *  Product: '<S63>/sin_cos_theta'
   *  Sum: '<S64>/eta1_k'
   *  Sum: '<S64>/eta2_k'
   *  Trigonometry: '<S63>/cos_theta'
   *  Trigonometry: '<S63>/sin_theta'
   *  UnitDelay: '<S63>/theta_z1'
   */
  rtb_DiscreteTimeIntegrator = (rtb_Add1 - rtb_Cos) * (1.0F / motor.flux) * cosf
    (rtDW.theta_z1_DSTATE) - (rtb_Integrator_jp - rtb_Integrator_l_tmp) * (1.0F /
    motor.flux) * sinf(rtDW.theta_z1_DSTATE);

  /* Sum: '<S106>/Sum' incorporates:
   *  DiscreteIntegrator: '<S97>/Integrator'
   *  Gain: '<S102>/Proportional Gain'
   */
  rtb_Sin = nflux_obs.PLL_Kp * rtb_DiscreteTimeIntegrator +
    rtDW.Integrator_DSTATE_a;

  /* Saturate: '<S104>/Saturation' */
  if (rtb_Sin > 6283.18555F) {
    rtb_Sin = 6283.18555F;
  } else if (rtb_Sin < -6283.18555F) {
    rtb_Sin = -6283.18555F;
  }

  /* End of Saturate: '<S104>/Saturation' */

  /* Sum: '<S62>/sum' incorporates:
   *  Constant: '<S62>/LPFFilter'
   *  Gain: '<S57>/30_over_pi'
   *  Gain: '<S57>/Multiply'
   *  Product: '<S62>/x'
   *  Sum: '<S62>/err'
   *  UnitDelay: '<S62>/z1'
   */
  FluxWm = (1.0F / motor.Pn * rtb_Sin * 9.54929638F - rtDW.z1_DSTATE) *
    nflux_obs.LPF_K + rtDW.z1_DSTATE;

  /* RateTransition: '<S1>/Rate Transition' */
  if (rtM->Timing.TaskCounters.TID[1] == 0) {
    /* S-Function (fcgen): '<S1>/Function-Call Generator' incorporates:
     *  SubSystem: '<S1>/Speed_loop'
     */
    if (rtDW.Speed_loop_RESET_ELAPS_T) {
      Speed_loop_ELAPS_T = 0U;
    } else {
      Speed_loop_ELAPS_T = rtM->Timing.clockTick1 - rtDW.Speed_loop_PREV_T;
    }

    rtDW.Speed_loop_PREV_T = rtM->Timing.clockTick1;
    rtDW.Speed_loop_RESET_ELAPS_T = false;

    /* Sum: '<S2>/Sum2' incorporates:
     *  Inport: '<Root>/Speed_ref'
     */
    rtb_Add1_k = rtU.RefSpeed - FluxWm;

    /* DiscreteIntegrator: '<S38>/Integrator' incorporates:
     *  RateTransition: '<S1>/Rate Transition2'
     */
    if (rtDW.Integrator_SYSTEM_ENABLE != 0) {
      /* DiscreteIntegrator: '<S38>/Integrator' */
      rtb_Gain2 = rtDW.Integrator_DSTATE_i;
    } else if ((rtDW.RestsSingal > 0.0) && (rtDW.Integrator_PrevResetState <= 0))
    {
      /* DiscreteIntegrator: '<S38>/Integrator' */
      rtb_Gain2 = 0.0F;
    } else {
      /* DiscreteIntegrator: '<S38>/Integrator' */
      rtb_Gain2 = (real32_T)(0.001 * (real_T)Speed_loop_ELAPS_T
        * rtDW.Integrator_PREV_U) + rtDW.Integrator_DSTATE_i;
    }

    /* End of DiscreteIntegrator: '<S38>/Integrator' */

    /* Sum: '<S47>/Sum' incorporates:
     *  Gain: '<S43>/Proportional Gain'
     */
    rtb_Add_d = spd_kpki.spd_kp * rtb_Add1_k + rtb_Gain2;

    /* Saturate: '<S45>/Saturation' incorporates:
     *  DeadZone: '<S31>/DeadZone'
     */
    if (rtb_Add_d > 3.0F) {
      /* Saturate: '<S45>/Saturation' */
      rtDW.Saturation = 3.0F;
      rtb_Add_d -= 3.0F;
    } else {
      if (rtb_Add_d < -3.0F) {
        /* Saturate: '<S45>/Saturation' */
        rtDW.Saturation = -3.0F;
      } else {
        /* Saturate: '<S45>/Saturation' */
        rtDW.Saturation = rtb_Add_d;
      }

      if (rtb_Add_d >= -3.0F) {
        rtb_Add_d = 0.0F;
      } else {
        rtb_Add_d -= -3.0F;
      }
    }

    /* End of Saturate: '<S45>/Saturation' */

    /* Gain: '<S35>/Integral Gain' */
    rtb_Add1_k *= spd_kpki.spd_ki;

    /* Update for DiscreteIntegrator: '<S38>/Integrator' incorporates:
     *  RateTransition: '<S1>/Rate Transition2'
     */
    rtDW.Integrator_SYSTEM_ENABLE = 0U;
    rtDW.Integrator_DSTATE_i = rtb_Gain2;
    if (rtDW.RestsSingal > 0.0) {
      rtDW.Integrator_PrevResetState = 1;
    } else if (rtDW.RestsSingal < 0.0) {
      rtDW.Integrator_PrevResetState = -1;
    } else if (rtDW.RestsSingal == 0.0) {
      rtDW.Integrator_PrevResetState = 0;
    } else {
      rtDW.Integrator_PrevResetState = 2;
    }

    /* Switch: '<S29>/Switch1' incorporates:
     *  Constant: '<S29>/Clamping_zero'
     *  Constant: '<S29>/Constant'
     *  Constant: '<S29>/Constant2'
     *  RelationalOperator: '<S29>/fix for DT propagation issue'
     */
    if (rtb_Add_d > 0.0F) {
      tmp = 1;
    } else {
      tmp = -1;
    }

    /* Switch: '<S29>/Switch2' incorporates:
     *  Constant: '<S29>/Clamping_zero'
     *  Constant: '<S29>/Constant3'
     *  Constant: '<S29>/Constant4'
     *  RelationalOperator: '<S29>/fix for DT propagation issue1'
     */
    if (rtb_Add1_k > 0.0F) {
      tmp_0 = 1;
    } else {
      tmp_0 = -1;
    }

    /* Switch: '<S29>/Switch' incorporates:
     *  Constant: '<S29>/Clamping_zero'
     *  Logic: '<S29>/AND3'
     *  RelationalOperator: '<S29>/Equal1'
     *  RelationalOperator: '<S29>/Relational Operator'
     *  Switch: '<S29>/Switch1'
     *  Switch: '<S29>/Switch2'
     */
    if ((rtb_Add_d != 0.0F) && (tmp == tmp_0)) {
      /* Update for DiscreteIntegrator: '<S38>/Integrator' incorporates:
       *  Constant: '<S29>/Constant1'
       */
      rtDW.Integrator_PREV_U = 0.0F;
    } else {
      /* Update for DiscreteIntegrator: '<S38>/Integrator' */
      rtDW.Integrator_PREV_U = rtb_Add1_k;
    }

    /* End of Switch: '<S29>/Switch' */
    /* End of Outputs for S-Function (fcgen): '<S1>/Function-Call Generator' */
  }

  /* End of RateTransition: '<S1>/Rate Transition' */

  /* Math: '<S63>/mod' incorporates:
   *  Constant: '<S63>/2pi'
   *  Gain: '<S63>/Ts'
   *  Sum: '<S63>/theta_next'
   *  UnitDelay: '<S63>/theta_z1'
   */
  FluxTheta = rt_modf(0.0001F * rtb_Sin + rtDW.theta_z1_DSTATE, 6.28318548F);

  /* DeadZone: '<S156>/DeadZone' */
  if (rtb_Saturation_l > 12.4707661F) {
    rtb_Saturation_l -= 12.4707661F;
  } else if (rtb_Saturation_l >= -12.4707661F) {
    rtb_Saturation_l = 0.0F;
  } else {
    rtb_Saturation_l -= -12.4707661F;
  }

  /* End of DeadZone: '<S156>/DeadZone' */

  /* Product: '<S160>/IProd Out' incorporates:
   *  Constant: '<S61>/Constant4'
   */
  rtb_IProdOut_c = (int16_T)floorf(rtb_theta * curr_kpki.curr_d_ki);

  /* DeadZone: '<S206>/DeadZone' */
  if (rtb_DeadZone_fw > 12.4707661F) {
    rtb_DeadZone_fw -= 12.4707661F;
  } else if (rtb_DeadZone_fw >= -12.4707661F) {
    rtb_DeadZone_fw = 0.0F;
  } else {
    rtb_DeadZone_fw -= -12.4707661F;
  }

  /* End of DeadZone: '<S206>/DeadZone' */

  /* Product: '<S210>/IProd Out' incorporates:
   *  Constant: '<S61>/Constant2'
   */
  rtb_IProdOut *= curr_kpki.curr_q_ki;

  /* Update for RateTransition: '<S1>/Rate Transition3' */
  if (rtM->Timing.TaskCounters.TID[1] == 0) {
    rtDW.RateTransition3_Buffer0 = rtDW.Saturation;
  }

  /* End of Update for RateTransition: '<S1>/Rate Transition3' */

  /* Switch: '<S154>/Switch1' incorporates:
   *  Constant: '<S154>/Constant'
   *  Constant: '<S154>/Constant2'
   *  RelationalOperator: '<S154>/fix for DT propagation issue'
   */
  if (rtb_Saturation_l > 0.0F) {
    tmp = 1;
  } else {
    tmp = -1;
  }

  /* Switch: '<S154>/Switch2' incorporates:
   *  Constant: '<S154>/Clamping_zero'
   *  Constant: '<S154>/Constant3'
   *  Constant: '<S154>/Constant4'
   *  RelationalOperator: '<S154>/fix for DT propagation issue1'
   */
  if (rtb_IProdOut_c > 0) {
    tmp_0 = 1;
  } else {
    tmp_0 = -1;
  }

  /* Switch: '<S154>/Switch' incorporates:
   *  Constant: '<S154>/Constant1'
   *  Logic: '<S154>/AND3'
   *  RelationalOperator: '<S154>/Equal1'
   *  RelationalOperator: '<S154>/Relational Operator'
   *  Switch: '<S154>/Switch1'
   *  Switch: '<S154>/Switch2'
   */
  if ((rtb_Saturation_l != 0.0F) && (tmp == tmp_0)) {
    rtb_IProdOut_c = 0;
  }

  /* Update for DiscreteIntegrator: '<S163>/Integrator' incorporates:
   *  Switch: '<S154>/Switch'
   */
  rtDW.Integrator_DSTATE_h += rtb_IProdOut_c;

  /* Switch: '<S204>/Switch1' incorporates:
   *  Constant: '<S204>/Clamping_zero'
   *  Constant: '<S204>/Constant'
   *  Constant: '<S204>/Constant2'
   *  RelationalOperator: '<S204>/fix for DT propagation issue'
   */
  if (rtb_DeadZone_fw > 0.0F) {
    tmp = 1;
  } else {
    tmp = -1;
  }

  /* Switch: '<S204>/Switch2' incorporates:
   *  Constant: '<S204>/Clamping_zero'
   *  Constant: '<S204>/Constant3'
   *  Constant: '<S204>/Constant4'
   *  RelationalOperator: '<S204>/fix for DT propagation issue1'
   */
  if (rtb_IProdOut > 0.0F) {
    tmp_0 = 1;
  } else {
    tmp_0 = -1;
  }

  /* Switch: '<S204>/Switch' incorporates:
   *  Constant: '<S204>/Clamping_zero'
   *  Constant: '<S204>/Constant1'
   *  Logic: '<S204>/AND3'
   *  RelationalOperator: '<S204>/Equal1'
   *  RelationalOperator: '<S204>/Relational Operator'
   *  Switch: '<S204>/Switch1'
   *  Switch: '<S204>/Switch2'
   */
  if ((rtb_DeadZone_fw != 0.0F) && (tmp == tmp_0)) {
    rtb_IProdOut = 0.0F;
  }

  /* Update for DiscreteIntegrator: '<S213>/Integrator' incorporates:
   *  Switch: '<S204>/Switch'
   */
  rtDW.Integrator_DSTATE += 0.0001F * rtb_IProdOut;

  /* Update for UnitDelay: '<S64>/x2_delay' */
  rtDW.x2_delay_DSTATE = rtb_Add1;

  /* Update for UnitDelay: '<S64>/x1_delay' */
  rtDW.x1_delay_DSTATE = rtb_Integrator_jp;

  /* Update for UnitDelay: '<S63>/theta_z1' */
  rtDW.theta_z1_DSTATE = FluxTheta;

  /* Update for DiscreteIntegrator: '<S97>/Integrator' incorporates:
   *  Gain: '<S94>/Integral Gain'
   */
  rtDW.Integrator_DSTATE_a += nflux_obs.PLL_Ki * rtb_DiscreteTimeIntegrator *
    0.0001F;

  /* Update for UnitDelay: '<S62>/z1' */
  rtDW.z1_DSTATE = FluxWm;
  if (rtM->Timing.TaskCounters.TID[1] == 0) {
    /* Update absolute timer for sample time: [0.001s, 0.0s] */
    /* The "clockTick1" counts the number of times the code of this task has
     * been executed. The resolution of this integer timer is 0.001, which is the step size
     * of the task. Size of "clockTick1" ensures timer will not overflow during the
     * application lifespan selected.
     */
    rtM->Timing.clockTick1++;
  }

  rate_scheduler();
}

/* Model initialize function */
void FOC_initialize(void)
{
  /* SystemInitialize for IfAction SubSystem: '<S60>/If Action Subsystem2' */
  /* InitializeConditions for DiscreteIntegrator: '<S120>/Discrete-Time Integrator' */
  rtDW.DiscreteTimeIntegrator_PrevRese = 2;

  /* InitializeConditions for DiscreteIntegrator: '<S120>/Discrete-Time Integrator1' */
  rtDW.DiscreteTimeIntegrator1_PrevRes = 2;

  /* End of SystemInitialize for SubSystem: '<S60>/If Action Subsystem2' */

  /* SystemInitialize for S-Function (fcgen): '<S1>/Function-Call Generator' incorporates:
   *  SubSystem: '<S1>/Speed_loop'
   */
  /* InitializeConditions for DiscreteIntegrator: '<S38>/Integrator' */
  rtDW.Integrator_PrevResetState = 2;

  /* End of SystemInitialize for S-Function (fcgen): '<S1>/Function-Call Generator' */

  /* Enable for S-Function (fcgen): '<S1>/Function-Call Generator' incorporates:
   *  SubSystem: '<S1>/Speed_loop'
   */
  rtDW.Speed_loop_RESET_ELAPS_T = true;

  /* Enable for DiscreteIntegrator: '<S38>/Integrator' */
  rtDW.Integrator_SYSTEM_ENABLE = 1U;

  /* End of Enable for S-Function (fcgen): '<S1>/Function-Call Generator' */
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
