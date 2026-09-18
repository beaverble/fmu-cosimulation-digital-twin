# -*- coding: utf-8 -*-
"""
FMU: FaultInjector (fault_injector.py)
설명:
- 매 스텝(step)마다 주어진 확률로 고장 트리거를 '1(True)'로 발생시키는 FMU
- 트리거는 해당 스텝에서만 True인 펄스(pulse) 신호로 동작하고, 다음 스텝에서 자동으로 False로 초기화됩니다.
- 확률 입력값: gate_fail_prob, kiosk_fail_prob (0.0 ~ 1.0)
- 시드 입력값: random_seed (0이면 현재 시간 기반으로 시드 설정)
"""

from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    Real, Integer, Boolean
)
import random, time

# pythonfmu 빌더가 사용할 클래스 이름(명시적 지정)
slave_class = "FaultInjector"

class FaultInjector(Fmi2Slave):

    def __init__(self, **kwargs):
        # 반드시 먼저 호출
        super().__init__(**kwargs)

        # ------------ Inputs (설정) ------------
        # 확률 기본값(퍼센트가 아니라 0~1 구간 확률)
        self.gate_fail_prob = 0.01
        self.kiosk_fail_prob = 0.01
        # 0이면 time 기반 시드
        self.random_seed = 0

        self.register_variable(Real(
            "gate_fail_prob",
            causality=Fmi2Causality.input,
            description="게이트 고장 발생 확률 (0.0~1.0, per step)"
        ))
        self.register_variable(Real(
            "kiosk_fail_prob",
            causality=Fmi2Causality.input,
            description="키오스크 고장 발생 확률 (0.0~1.0, per step)"
        ))
        self.register_variable(Integer(
            "random_seed",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete,
            description="난수 시드(0이면 현재 시간 기반)"
        ))

        # ------------ Outputs (트리거: 펄스) ------------
        self.trigger_GateFailure = False
        self.trigger_KioskFailure = False

        self.register_variable(Boolean(
            "trigger_GateFailure",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,
            description="게이트 고장 트리거 (해당 스텝에만 True)"
        ))
        self.register_variable(Boolean(
            "trigger_KioskFailure",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,
            description="키오스크 고장 트리거 (해당 스텝에만 True)"
        ))

        # 내부 RNG
        self._rng = random.Random()

    # 초기화 종료 시점에 시드 확정
    def exit_initialization_mode(self):
        seed = int(self.random_seed)
        if seed == 0:
            seed = int(time.time() * 1000) & 0xFFFFFFFF
        self._rng.seed(seed)

    # 매 스텝 호출
    def do_step(self, current_time: float, step_size: float):
        # 펄스 성격을 위해 스텝 시작마다 False로 초기화
        self.trigger_GateFailure = False
        self.trigger_KioskFailure = False

        # 확률 클램프
        p_gate = min(max(float(self.gate_fail_prob), 0.0), 1.0)
        p_kiosk = min(max(float(self.kiosk_fail_prob), 0.0), 1.0)

        # 확률적으로 트리거 1 발생
        if self._rng.random() < p_gate:
            self.trigger_GateFailure = True
        if self._rng.random() < p_kiosk:
            self.trigger_KioskFailure = True

        # 정상 종료
        return True
