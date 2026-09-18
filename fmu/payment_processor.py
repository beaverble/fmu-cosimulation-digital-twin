# -*- coding: utf-8 -*-
"""
FMU: PaymentProcessor (payment_processor.py)
설명: 계산된 parkingFee와 PaymentInputSimulator의 결제 시도를 받아
     결제 성공/실패 여부를 확률적으로 반환합니다.
"""

import random
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    Real, Integer, Boolean
)


class PaymentProcessor(Fmi2Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # -------------------------
        # 내부 저장소(실제 변수 값)
        # -------------------------
        self.parkingFee = 0.0                 # 입력
        self.trigger_PaymentAttempt = False   # 입력
        self.paymentMethod = 0                # 입력 (0: 신용카드, 1: 모바일페이, 2: 현금)
        self.isPaymentComplete = False        # 출력

        # 상승엣지 감지용 내부 상태
        self._last_trigger_state = False

        # -------------------------
        # 변수 등록 (pythonfmu 방식)
        # -------------------------
        # Inputs
        self.register_variable(Real(
            "parkingFee",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.continuous,
            description="계산된 주차 요금(원)"
        ))
        self.register_variable(Boolean(
            "trigger_PaymentAttempt",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete,   # 비-Real은 discrete
            description="결제 시도 트리거(펄스)"
        ))
        self.register_variable(Integer(
            "paymentMethod",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete,   # 비-Real은 discrete
            description="결제 수단 (0:CARD,1:MOBILE,2:CASH)"
        ))

        # Output
        self.register_variable(Boolean(
            "isPaymentComplete",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,   # 비-Real은 discrete
            description="결제 완료 신호(펄스)"
        ))

    def do_step(self, current_time, step_size):
        self.isPaymentComplete = False

        payment_attempted = (self.trigger_PaymentAttempt and not self._last_trigger_state)
        self._last_trigger_state = self.trigger_PaymentAttempt

        if payment_attempted:
            if self.paymentMethod == 0:
                prob = 0.95
            elif self.paymentMethod == 1:
                prob = 0.98
            elif self.paymentMethod == 2:
                prob = 1.00
            else:
                prob = 0.00

            success = (random.random() <= prob)
            self.isPaymentComplete = success

        return True
