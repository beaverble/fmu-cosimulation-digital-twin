# -*- coding: utf-8 -*-
"""
FMU: ParkingFeeCalculator (주차 요금 계산기)
설명: 차량이 출차할 때, 입차 기록과 요금표(시간, 공휴일)를 바탕으로 주차 요금을 계산합니다.
(회원 할인 기능 제외 버전)
"""

import math
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    Real, Boolean
)

class ParkingFeeCalculator(Fmi2Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 1) 내부 값(파라미터/입출력의 '실제 저장소')
        self.baseRatePerHour = 3000.0        # 기본 시간당 요금 (원)
        self.holidayRatePerHour = 4500.0     # 공휴일 시간당 요금 (원)
        self.freeParkingMinutes = 10.0       # 무료 주차 시간 (분)
        self.billingUnitMinutes = 10.0       # 요금 부과 단위 (분)

        self.exitTime = 0.0                  # 출차 시간(초)
        self.entryRecord = 0.0               # 입차 시간(초)
        self.isHoliday = False               # 공휴일 여부

        self.parkingFee = 0.0                # 최종 주차 요금(원)

        # 2) 변수 등록 —— pythonfmu 방식 (타입/인과성/변동성 명시)
        # Parameters (FMI 규격: causality=parameter, variability=fixed)
        self.register_variable(Real(
            "baseRatePerHour",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.fixed,
            description="기본 시간당 요금 (원)",
            start=self.baseRatePerHour
        ))
        self.register_variable(Real(
            "holidayRatePerHour",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.fixed,
            description="공휴일 시간당 요금 (원)",
            start=self.holidayRatePerHour
        ))
        self.register_variable(Real(
            "freeParkingMinutes",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.fixed,
            description="무료 주차 시간 (분)",
            start=self.freeParkingMinutes
        ))
        self.register_variable(Real(
            "billingUnitMinutes",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.fixed,
            description="요금 부과 단위 (분)",
            start=self.billingUnitMinutes
        ))

        # Inputs
        self.register_variable(Real(
            "exitTime",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.continuous,
            description="차량 출차 시간 (시뮬레이션 시간, 초)"
        ))
        self.register_variable(Real(
            "entryRecord",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.continuous,
            description="차량 입차 시간 (시뮬레이션 시간, 초)"
        ))
        self.register_variable(Boolean(
            "isHoliday",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete,  # 비-Real은 discrete (프로젝트 규칙)
            description="공휴일 여부"
        ))

        # Output
        self.register_variable(Real(
            "parkingFee",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.continuous,
            description="계산된 최종 주차 요금"
        ))

        # (옵션) 내부 계산용
        self.durationMinutes = 0.0
        self.chargeableMinutes = 0.0

    def do_step(self, current_time, step_size):
        # 0) 기본 유효성 체크
        entry_time = self.entryRecord
        if entry_time >= self.exitTime:
            self.parkingFee = 0.0
            return True

        # 1) 총 주차 시간(분)
        duration_seconds = self.exitTime - entry_time
        self.durationMinutes = duration_seconds / 60.0

        # 2) 무료 구간
        if self.durationMinutes <= self.freeParkingMinutes:
            self.parkingFee = 0.0
            return True

        # 3) 요금제(공휴일/평일)
        current_rate_per_hour = self.holidayRatePerHour if self.isHoliday else self.baseRatePerHour

        # 4) 과금 단위(분) 안정화
        safe_billing_unit = self.billingUnitMinutes if self.billingUnitMinutes > 0 else 10.0
        cost_per_unit = (current_rate_per_hour / 60.0) * safe_billing_unit

        # 5) 과금 대상 시간 및 단위 수
        self.chargeableMinutes = self.durationMinutes - self.freeParkingMinutes
        num_units = math.ceil(self.chargeableMinutes / safe_billing_unit)

        # 6) 요금 계산
        base_fee = num_units * cost_per_unit

        # 7) 최종 요금 (원 단위 반올림)
        self.parkingFee = round(max(0.0, base_fee))
        return True
