/*
 * File: FOC.h
 *
 * Code generated for Simulink model 'FOC'.
 *
 * Model version                  : 1.51
 * Simulink Coder version         : 23.2 (R2023b) 01-Aug-2023
 * C/C++ source code generated on : Wed Jun 17 20:08:16 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: ARM Compatible->ARM Cortex-M
 * Code generation objectives:
 *    1. Execution efficiency
 *    2. RAM efficiency
 * Validation result: Not run
 */

#ifndef RTW_HEADER_FOC_h_
#define RTW_HEADER_FOC_h_
#ifndef FOC_COMMON_INCLUDES_
#define FOC_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* FOC_COMMON_INCLUDES_ */

/* Macros for accessing real-time model data structure */
#ifndef rtmGetErrorStatus
#define rtmGetErrorStatus(rtm)         ((rtm)->errorStatus)
#endif

#ifndef rtmSetErrorStatus
#define rtmSetErrorStatus(rtm, val)    ((rtm)->errorStatus = (val))
#endif

/* Forward declaration for rtModel */
typedef struct tag_RTM RT_MODEL;

/* Block signals and states (default storage) for system '<Root>' */
typedef struct {
  real_T Motor_state;                  /* '<S60>/Chart' */
  real_T RestsSingal;                  /* '<S60>/Chart' */
  real_T ZReset;                       /* '<S60>/Chart' */
  real_T cnt;                          /* '<S60>/Chart' */
  real32_T RateTransition3;            /* '<S1>/Rate Transition3' */
  real32_T Merge;                      /* '<S60>/Merge' */
  real32_T Merge1;                     /* '<S60>/Merge1' */
  real32_T Saturation;                 /* '<S45>/Saturation' */
  real32_T Integrator_DSTATE;          /* '<S214>/Integrator' */
  real32_T x2_delay_DSTATE;            /* '<S64>/x2_delay' */
  real32_T x1_delay_DSTATE;            /* '<S64>/x1_delay' */
  real32_T theta_z1_DSTATE;            /* '<S63>/theta_z1' */
  real32_T Integrator_DSTATE_a;        /* '<S97>/Integrator' */
  real32_T z1_DSTATE;                  /* '<S62>/z1' */
  real32_T UnitDelay_DSTATE;           /* '<S122>/Unit Delay' */
  real32_T DiscreteTimeIntegrator1_DSTATE;/* '<S122>/Discrete-Time Integrator1' */
  real32_T DiscreteTimeIntegrator_DSTATE;/* '<S122>/Discrete-Time Integrator' */
  real32_T DiscreteTimeIntegrator_DSTATE_l;/* '<S120>/Discrete-Time Integrator' */
  real32_T DiscreteTimeIntegrator1_DSTAT_m;/* '<S120>/Discrete-Time Integrator1' */
  real32_T Integrator_DSTATE_i;        /* '<S38>/Integrator' */
  real32_T RateTransition3_Buffer0;    /* '<S1>/Rate Transition3' */
  real32_T PrevY;                      /* '<S128>/CorrectionRateLimit' */
  real32_T Integrator_PREV_U;          /* '<S38>/Integrator' */
  uint32_T Speed_loop_PREV_T;          /* '<S1>/Speed_loop' */
  int16_T Integrator_DSTATE_h;         /* '<S164>/Integrator' */
  uint16_T temporalCounter_i1;         /* '<S60>/Chart' */
  int8_T DiscreteTimeIntegrator_PrevRese;/* '<S120>/Discrete-Time Integrator' */
  int8_T DiscreteTimeIntegrator1_PrevRes;/* '<S120>/Discrete-Time Integrator1' */
  int8_T Integrator_PrevResetState;    /* '<S38>/Integrator' */
  uint8_T is_active_c3_FOC;            /* '<S60>/Chart' */
  uint8_T is_c3_FOC;                   /* '<S60>/Chart' */
  uint8_T Integrator_SYSTEM_ENABLE;    /* '<S38>/Integrator' */
  boolean_T Speed_loop_RESET_ELAPS_T;  /* '<S1>/Speed_loop' */
} DW;

/* External inputs (root inport signals with default storage) */
typedef struct {
  real32_T v_bus;                      /* '<Root>/v_bus' */
  real32_T SpeedRefToFOC;              /* '<Root>/Speed_ref' */
  boolean_T MotorOnOff;                /* '<Root>/MotorOnOff' */
  real32_T OpenLoopHold;               /* '<Root>/OpenLoopHold' */
  real32_T ia;                         /* '<Root>/ia' */
  real32_T ib;                         /* '<Root>/ib' */
  real32_T ic;                         /* '<Root>/ic' */
} ExtU;

/* External outputs (root outports fed by signals with default storage) */
typedef struct {
  real32_T Tcmp1;                      /* '<Root>/Tcmp1' */
  real32_T Tcmp2;                      /* '<Root>/Tcmp2' */
  real32_T Tcmp3;                      /* '<Root>/Tcmp3' */
} ExtY;

/* Type definition for custom storage class: Struct */
typedef struct curr_kpki_tag {
  real32_T curr_d_ki;                  /* Referenced by: '<S61>/Constant4' */
  real32_T curr_d_kp;                  /* Referenced by: '<S61>/Constant3' */
  real32_T curr_q_ki;                  /* Referenced by: '<S61>/Constant2' */
  real32_T curr_q_kp;                  /* Referenced by: '<S61>/Constant1' */
} curr_kpki_type;

typedef struct handover_cfg_tag {
  real32_T iq_handover;                /* Referenced by: '<S122>/Saturation' */
  real32_T iq_ref_slew_down;           /* Referenced by: '<S122>/Constant5' */
  real32_T theta_handover_slew_limit;
                               /* Referenced by: '<S128>/CorrectionRateLimit' */
} handover_cfg_type;

typedef struct motor_tag {
  real32_T L;                          /* Referenced by:
                                        * '<S64>/L_eta1_now'
                                        * '<S64>/L_eta1_prev'
                                        * '<S64>/L_eta2_now'
                                        * '<S64>/L_eta2_prev'
                                        */
  real32_T Pn;                         /* Referenced by:
                                        * '<S57>/Multiply'
                                        * '<S120>/Gain'
                                        * '<S122>/Gain'
                                        */
  real32_T Rs;                         /* Referenced by:
                                        * '<S64>/Rs_i1'
                                        * '<S64>/Rs_i2'
                                        */
  real32_T flux;                       /* Referenced by:
                                        * '<S64>/flux_sq'
                                        * '<S64>/inv_flux1'
                                        * '<S64>/inv_flux2'
                                        */
} motor_type;

typedef struct nflux_obs_tag {
  real32_T Gamma;                      /* Referenced by:
                                        * '<S64>/Gamma1'
                                        * '<S64>/Gamma2'
                                        */
  real32_T LPF_K;                      /* Referenced by: '<S62>/LPFFilter' */
  real32_T PLL_Ki;                    /* Referenced by: '<S94>/Integral Gain' */
  real32_T PLL_Kp;               /* Referenced by: '<S102>/Proportional Gain' */
} nflux_obs_type;

typedef struct spd_kpki_tag {
  real32_T spd_ki;                    /* Referenced by: '<S35>/Integral Gain' */
  real32_T spd_kp;                /* Referenced by: '<S43>/Proportional Gain' */
} spd_kpki_type;

/* Real-time Model Data Structure */
struct tag_RTM {
  const char_T * volatile errorStatus;

  /*
   * Timing:
   * The following substructure contains information regarding
   * the timing information for the model.
   */
  struct {
    uint32_T clockTick1;
    struct {
      uint8_T TID[2];
    } TaskCounters;
  } Timing;
};

/* Block signals and states (default storage) */
extern DW rtDW;

/* External inputs (root inport signals with default storage) */
extern ExtU rtU;

/* External outputs (root outports fed by signals with default storage) */
extern ExtY rtY;

/*
 * Exported Global Signals
 *
 * Note: Exported global signals are block signals with an exported global
 * storage class designation.  Code generation will declare the memory for
 * these signals and export their symbols.
 *
 */
extern real32_T FluxWm;                /* '<S62>/sum' */
extern real32_T FluxTheta;             /* '<S63>/mod' */
extern real32_T FocDiagId;
extern real32_T FocDiagIq;
extern real32_T FocDiagIdRef;
extern real32_T FocDiagIqRef;
extern real32_T FocDiagUd;
extern real32_T FocDiagUq;
extern real32_T FocDiagTcmp1;
extern real32_T FocDiagTcmp2;
extern real32_T FocDiagTcmp3;
extern real32_T FocDiagState;

/* Model entry point functions */
extern void FOC_initialize(void);
extern void FOC_step(void);

/* Exported data declaration */

/* Declaration for custom storage class: Struct */
extern curr_kpki_type curr_kpki;
extern handover_cfg_type handover_cfg;
extern motor_type motor;
extern nflux_obs_type nflux_obs;
extern spd_kpki_type spd_kpki;

/* Real-time Model object */
extern RT_MODEL *const rtM;

/*-
 * These blocks were eliminated from the model due to optimizations:
 *
 * Block '<S1>/Scope' : Unused code path elimination
 * Block '<S2>/Scope' : Unused code path elimination
 * Block '<S57>/Scope' : Unused code path elimination
 * Block '<S57>/Scope1' : Unused code path elimination
 * Block '<S59>/Add' : Unused code path elimination
 * Block '<S59>/Constant2' : Unused code path elimination
 * Block '<S59>/Multiply' : Unused code path elimination
 * Block '<S59>/Scope' : Unused code path elimination
 * Block '<S59>/Scope1' : Unused code path elimination
 * Block '<S59>/Scope10' : Unused code path elimination
 * Block '<S59>/Scope11' : Unused code path elimination
 * Block '<S59>/Scope2' : Unused code path elimination
 * Block '<S59>/Scope3' : Unused code path elimination
 * Block '<S59>/Scope4' : Unused code path elimination
 * Block '<S59>/Scope5' : Unused code path elimination
 * Block '<S59>/Scope6' : Unused code path elimination
 * Block '<S59>/Scope7' : Unused code path elimination
 * Block '<S59>/Scope9' : Unused code path elimination
 * Block '<S59>/Subtract' : Unused code path elimination
 * Block '<S3>/Scope' : Unused code path elimination
 * Block '<S3>/Scope1' : Unused code path elimination
 * Block '<S3>/Scope2' : Unused code path elimination
 * Block '<S3>/Scope3' : Unused code path elimination
 * Block '<S3>/Scope4' : Unused code path elimination
 * Block '<S3>/Scope5' : Unused code path elimination
 * Block '<S3>/Scope6' : Unused code path elimination
 * Block '<S3>/Scope7' : Unused code path elimination
 * Block '<S120>/Scope1' : Unused code path elimination
 * Block '<S120>/Scope2' : Unused code path elimination
 * Block '<S122>/Add1' : Unused code path elimination
 * Block '<S122>/Add4' : Unused code path elimination
 * Block '<S122>/Constant3' : Unused code path elimination
 * Block '<S122>/Constant4' : Unused code path elimination
 * Block '<S122>/Mod1' : Unused code path elimination
 * Block '<S122>/Product' : Unused code path elimination
 * Block '<S122>/Product1' : Unused code path elimination
 * Block '<S122>/Rate Limiter' : Unused code path elimination
 * Block '<S122>/Scope' : Unused code path elimination
 * Block '<S122>/Scope1' : Unused code path elimination
 * Block '<S122>/Scope10' : Unused code path elimination
 * Block '<S122>/Scope2' : Unused code path elimination
 * Block '<S122>/Scope3' : Unused code path elimination
 * Block '<S122>/Scope4' : Unused code path elimination
 * Block '<S122>/Scope5' : Unused code path elimination
 * Block '<S122>/Scope6' : Unused code path elimination
 * Block '<S122>/Scope7' : Unused code path elimination
 * Block '<S122>/Scope8' : Unused code path elimination
 * Block '<S128>/Scope' : Unused code path elimination
 * Block '<S128>/Scope1' : Unused code path elimination
 * Block '<S128>/Scope2' : Unused code path elimination
 * Block '<S60>/Scope' : Unused code path elimination
 * Block '<S60>/Scope1' : Unused code path elimination
 * Block '<S61>/Scope' : Unused code path elimination
 * Block '<S1>/Rate Transition1' : Eliminated since input and output rates are identical
 */

/*-
 * The generated code includes comments that allow you to trace directly
 * back to the appropriate location in the model.  The basic format
 * is <system>/block_name, where system is the system number (uniquely
 * assigned by Simulink) and block_name is the name of the block.
 *
 * Note that this particular code originates from a subsystem build,
 * and has its own system numbers different from the parent model.
 * Refer to the system hierarchy for this subsystem below, and use the
 * MATLAB hilite_system command to trace the generated code back
 * to the parent model.  For example,
 *
 * hilite_system('PMSM_NFLUX_v1_1_FwdRev/FOC')    - opens subsystem PMSM_NFLUX_v1_1_FwdRev/FOC
 * hilite_system('PMSM_NFLUX_v1_1_FwdRev/FOC/Kp') - opens and selects block Kp
 *
 * Here is the system hierarchy for this model
 *
 * '<Root>' : 'PMSM_NFLUX_v1_1_FwdRev'
 * '<S1>'   : 'PMSM_NFLUX_v1_1_FwdRev/FOC'
 * '<S2>'   : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop'
 * '<S3>'   : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop'
 * '<S4>'   : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3'
 * '<S5>'   : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Anti-windup'
 * '<S6>'   : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/D Gain'
 * '<S7>'   : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Filter'
 * '<S8>'   : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Filter ICs'
 * '<S9>'   : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/I Gain'
 * '<S10>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Ideal P Gain'
 * '<S11>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Ideal P Gain Fdbk'
 * '<S12>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Integrator'
 * '<S13>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Integrator ICs'
 * '<S14>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/N Copy'
 * '<S15>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/N Gain'
 * '<S16>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/P Copy'
 * '<S17>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Parallel P Gain'
 * '<S18>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Reset Signal'
 * '<S19>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Saturation'
 * '<S20>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Saturation Fdbk'
 * '<S21>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Sum'
 * '<S22>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Sum Fdbk'
 * '<S23>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Tracking Mode'
 * '<S24>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Tracking Mode Sum'
 * '<S25>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Tsamp - Integral'
 * '<S26>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Tsamp - Ngain'
 * '<S27>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/postSat Signal'
 * '<S28>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/preSat Signal'
 * '<S29>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Anti-windup/Disc. Clamping Parallel'
 * '<S30>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Anti-windup/Disc. Clamping Parallel/Dead Zone'
 * '<S31>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Anti-windup/Disc. Clamping Parallel/Dead Zone/Enabled'
 * '<S32>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/D Gain/Disabled'
 * '<S33>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Filter/Disabled'
 * '<S34>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Filter ICs/Disabled'
 * '<S35>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/I Gain/Internal Parameters'
 * '<S36>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Ideal P Gain/Passthrough'
 * '<S37>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Ideal P Gain Fdbk/Disabled'
 * '<S38>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Integrator/Discrete'
 * '<S39>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Integrator ICs/Internal IC'
 * '<S40>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/N Copy/Disabled wSignal Specification'
 * '<S41>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/N Gain/Disabled'
 * '<S42>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/P Copy/Disabled'
 * '<S43>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Parallel P Gain/Internal Parameters'
 * '<S44>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Reset Signal/External Reset'
 * '<S45>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Saturation/Enabled'
 * '<S46>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Saturation Fdbk/Disabled'
 * '<S47>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Sum/Sum_PI'
 * '<S48>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Sum Fdbk/Disabled'
 * '<S49>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Tracking Mode/Disabled'
 * '<S50>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Tracking Mode Sum/Passthrough'
 * '<S51>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Tsamp - Integral/TsSignalSpecification'
 * '<S52>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/Tsamp - Ngain/Passthrough'
 * '<S53>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/postSat Signal/Forward_Path'
 * '<S54>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/Speed_loop/PID Controller3/preSat Signal/Forward_Path'
 * '<S55>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Clark'
 * '<S56>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/In_park'
 * '<S57>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer'
 * '<S58>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Park'
 * '<S59>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/SVPWM'
 * '<S60>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem'
 * '<S61>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller'
 * '<S62>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/LPF'
 * '<S63>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL'
 * '<S64>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/flux observer'
 * '<S65>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)'
 * '<S66>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Anti-windup'
 * '<S67>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/D Gain'
 * '<S68>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Filter'
 * '<S69>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Filter ICs'
 * '<S70>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/I Gain'
 * '<S71>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Ideal P Gain'
 * '<S72>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Ideal P Gain Fdbk'
 * '<S73>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Integrator'
 * '<S74>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Integrator ICs'
 * '<S75>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/N Copy'
 * '<S76>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/N Gain'
 * '<S77>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/P Copy'
 * '<S78>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Parallel P Gain'
 * '<S79>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Reset Signal'
 * '<S80>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Saturation'
 * '<S81>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Saturation Fdbk'
 * '<S82>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Sum'
 * '<S83>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Sum Fdbk'
 * '<S84>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Tracking Mode'
 * '<S85>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Tracking Mode Sum'
 * '<S86>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Tsamp - Integral'
 * '<S87>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Tsamp - Ngain'
 * '<S88>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/postSat Signal'
 * '<S89>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/preSat Signal'
 * '<S90>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Anti-windup/Passthrough'
 * '<S91>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/D Gain/Disabled'
 * '<S92>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Filter/Disabled'
 * '<S93>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Filter ICs/Disabled'
 * '<S94>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/I Gain/Internal Parameters'
 * '<S95>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Ideal P Gain/Passthrough'
 * '<S96>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Ideal P Gain Fdbk/Disabled'
 * '<S97>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Integrator/Discrete'
 * '<S98>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Integrator ICs/Internal IC'
 * '<S99>'  : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/N Copy/Disabled wSignal Specification'
 * '<S100>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/N Gain/Disabled'
 * '<S101>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/P Copy/Disabled'
 * '<S102>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Parallel P Gain/Internal Parameters'
 * '<S103>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Reset Signal/Disabled'
 * '<S104>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Saturation/Enabled'
 * '<S105>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Saturation Fdbk/Disabled'
 * '<S106>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Sum/Sum_PI'
 * '<S107>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Sum Fdbk/Disabled'
 * '<S108>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Tracking Mode/Disabled'
 * '<S109>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Tracking Mode Sum/Passthrough'
 * '<S110>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Tsamp - Integral/TsSignalSpecification'
 * '<S111>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/Tsamp - Ngain/Passthrough'
 * '<S112>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/postSat Signal/Forward_Path'
 * '<S113>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Nonlinear Flux Observer/PLL/PI(z)/preSat Signal/Forward_Path'
 * '<S114>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/SVPWM/InvClark'
 * '<S115>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/SVPWM/MATLAB Function'
 * '<S116>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/SVPWM/ei_t'
 * '<S117>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem/Chart'
 * '<S118>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem/If Action Subsystem'
 * '<S119>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem/If Action Subsystem1'
 * '<S120>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem/If Action Subsystem2'
 * '<S121>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem/If Action Subsystem3'
 * '<S122>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem/If Action Subsystem4'
 * '<S123>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem/SpeedRefIsNegative'
 * '<S124>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem/If Action Subsystem4/If Action Subsystem'
 * '<S125>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem/If Action Subsystem4/If Action Subsystem1'
 * '<S126>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem/If Action Subsystem4/If Action Subsystem2'
 * '<S127>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem/If Action Subsystem4/If Action Subsystem3'
 * '<S128>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/Subsystem/If Action Subsystem4/ThetaShortestBlend'
 * '<S129>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1'
 * '<S130>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2'
 * '<S131>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Anti-windup'
 * '<S132>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/D Gain'
 * '<S133>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Filter'
 * '<S134>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Filter ICs'
 * '<S135>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/I Gain'
 * '<S136>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Ideal P Gain'
 * '<S137>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Ideal P Gain Fdbk'
 * '<S138>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Integrator'
 * '<S139>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Integrator ICs'
 * '<S140>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/N Copy'
 * '<S141>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/N Gain'
 * '<S142>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/P Copy'
 * '<S143>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Parallel P Gain'
 * '<S144>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Reset Signal'
 * '<S145>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Saturation'
 * '<S146>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Saturation Fdbk'
 * '<S147>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Sum'
 * '<S148>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Sum Fdbk'
 * '<S149>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Tracking Mode'
 * '<S150>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Tracking Mode Sum'
 * '<S151>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Tsamp - Integral'
 * '<S152>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Tsamp - Ngain'
 * '<S153>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/postSat Signal'
 * '<S154>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/preSat Signal'
 * '<S155>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Anti-windup/Disc. Clamping Parallel'
 * '<S156>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Anti-windup/Disc. Clamping Parallel/Dead Zone'
 * '<S157>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Anti-windup/Disc. Clamping Parallel/Dead Zone/Enabled'
 * '<S158>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/D Gain/Disabled'
 * '<S159>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Filter/Disabled'
 * '<S160>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Filter ICs/Disabled'
 * '<S161>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/I Gain/External Parameters'
 * '<S162>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Ideal P Gain/Passthrough'
 * '<S163>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Ideal P Gain Fdbk/Disabled'
 * '<S164>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Integrator/Discrete'
 * '<S165>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Integrator ICs/Internal IC'
 * '<S166>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/N Copy/Disabled wSignal Specification'
 * '<S167>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/N Gain/Disabled'
 * '<S168>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/P Copy/Disabled'
 * '<S169>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Parallel P Gain/External Parameters'
 * '<S170>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Reset Signal/Disabled'
 * '<S171>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Saturation/Enabled'
 * '<S172>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Saturation Fdbk/Disabled'
 * '<S173>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Sum/Sum_PI'
 * '<S174>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Sum Fdbk/Disabled'
 * '<S175>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Tracking Mode/Disabled'
 * '<S176>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Tracking Mode Sum/Passthrough'
 * '<S177>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Tsamp - Integral/TsSignalSpecification'
 * '<S178>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/Tsamp - Ngain/Passthrough'
 * '<S179>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/postSat Signal/Forward_Path'
 * '<S180>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller1/preSat Signal/Forward_Path'
 * '<S181>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Anti-windup'
 * '<S182>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/D Gain'
 * '<S183>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Filter'
 * '<S184>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Filter ICs'
 * '<S185>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/I Gain'
 * '<S186>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Ideal P Gain'
 * '<S187>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Ideal P Gain Fdbk'
 * '<S188>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Integrator'
 * '<S189>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Integrator ICs'
 * '<S190>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/N Copy'
 * '<S191>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/N Gain'
 * '<S192>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/P Copy'
 * '<S193>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Parallel P Gain'
 * '<S194>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Reset Signal'
 * '<S195>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Saturation'
 * '<S196>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Saturation Fdbk'
 * '<S197>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Sum'
 * '<S198>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Sum Fdbk'
 * '<S199>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Tracking Mode'
 * '<S200>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Tracking Mode Sum'
 * '<S201>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Tsamp - Integral'
 * '<S202>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Tsamp - Ngain'
 * '<S203>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/postSat Signal'
 * '<S204>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/preSat Signal'
 * '<S205>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Anti-windup/Disc. Clamping Parallel'
 * '<S206>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Anti-windup/Disc. Clamping Parallel/Dead Zone'
 * '<S207>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Anti-windup/Disc. Clamping Parallel/Dead Zone/Enabled'
 * '<S208>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/D Gain/Disabled'
 * '<S209>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Filter/Disabled'
 * '<S210>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Filter ICs/Disabled'
 * '<S211>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/I Gain/External Parameters'
 * '<S212>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Ideal P Gain/Passthrough'
 * '<S213>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Ideal P Gain Fdbk/Disabled'
 * '<S214>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Integrator/Discrete'
 * '<S215>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Integrator ICs/Internal IC'
 * '<S216>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/N Copy/Disabled wSignal Specification'
 * '<S217>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/N Gain/Disabled'
 * '<S218>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/P Copy/Disabled'
 * '<S219>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Parallel P Gain/External Parameters'
 * '<S220>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Reset Signal/Disabled'
 * '<S221>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Saturation/Enabled'
 * '<S222>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Saturation Fdbk/Disabled'
 * '<S223>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Sum/Sum_PI'
 * '<S224>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Sum Fdbk/Disabled'
 * '<S225>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Tracking Mode/Disabled'
 * '<S226>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Tracking Mode Sum/Passthrough'
 * '<S227>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Tsamp - Integral/TsSignalSpecification'
 * '<S228>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/Tsamp - Ngain/Passthrough'
 * '<S229>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/postSat Signal/Forward_Path'
 * '<S230>' : 'PMSM_NFLUX_v1_1_FwdRev/FOC/current_loop/idq_Controller/PID Controller2/preSat Signal/Forward_Path'
 */
#endif                                 /* RTW_HEADER_FOC_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
