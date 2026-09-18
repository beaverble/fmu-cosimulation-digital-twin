# -*- coding: utf-8 -*-
"""
FMU: PaymentInputSimulator (paymentinputfmu.py)
- paymentMethod: 시작 시 1(카드) 또는 2(현금)으로 고정
- trigger_PaymentAttempt: 3~8초 사이 '단 한 번' True
"""

import random, traceback
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    Integer, Boolean
)

class PaymentInput(Fmi2Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 출력 변수 (초기값)
        self.paymentMethod = 0
        self.trigger_PaymentAttempt = False

        self.register_variable(Integer(
            "paymentMethod",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,
            description="결제 방식 (0:NONE, 1:CREDIT_CARD, 2:CASH)"
        ))

        self.register_variable(Boolean(
            "trigger_PaymentAttempt",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,
            description="결제 시도 이벤트 트리거 (단 한 번 발생)"
        ))

        # 내부 상태
        self._payment_trigger_time = None
        self._event_has_happened = False

    def setup_experiment(self, start_time, stop_time=None, tolerance=None):
        # ⚠️ super() 호출 금지 (이전 fatal 원인)
        self.paymentMethod = random.choice([1, 2])
        print(f"[FMU Log T={float(start_time):.1f}s] 시뮬레이션 시작. 결제 방식 고정: {self.paymentMethod}")

        delay = random.uniform(3.0, 8.0)
        self._payment_trigger_time = float(start_time) + float(delay)
        self._event_has_happened = False
        # 반환값 필요 없음

    def enter_initialization_mode(self):
        # 초기화 단계에서 출력 명시 리셋
        self.trigger_PaymentAttempt = False
        # super() 호출 불필요

    def do_step(self, current_time, step_size):
        try:
            # 매 스텝 False로 리셋
            self.trigger_PaymentAttempt = False

            # 예약 시간이 됐고 아직 안 터졌으면 이번 스텝에만 True
            if (self._payment_trigger_time is not None and
                (float(current_time) >= float(self._payment_trigger_time)) and
                (not self._event_has_happened)):

                self.trigger_PaymentAttempt = True
                self._event_has_happened = True
                print(f"[FMU Log T={float(current_time):.1f}s] 결제 시도 이벤트 발생! (방식: {self.paymentMethod})")

            return True

        except Exception as e:
            print("[FMU ERROR] do_step 예외:", repr(e))
            traceback.print_exc()
            return False

# FMU 빌드 시 사용 클래스
slave_class = "PaymentInput"
