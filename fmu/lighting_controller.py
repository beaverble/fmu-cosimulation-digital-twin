# -*- coding: utf-8 -*-
"""
FMU: LightingController (lighting_controller.py)
역할: 주/야간 + 움직임 이벤트(주차/출차) 기반으로 조명 밝기(lightIntensity)를 제어
"""

from pythonfmu import (
    Fmi2Slave,
    Fmi2Causality,
    Fmi2Variability,
    Fmi2Initial,
    Real,
    Integer,
    Boolean,
)

SECONDS_PER_DAY = 86400


class LightingController(Fmi2Slave):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ----------------------------- Inputs ------------------------------
        self.currentTime = 0.0
        self.register_variable(Real(
            "currentTime",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.continuous,
            description="시뮬레이션 현재 시각(초). 0~86400 기준으로 시간대 파생",
        ))

        self.trigger_ParkEvent = False
        self.register_variable(Boolean(
            "trigger_ParkEvent",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete,  # 규약 준수
            description="방금 주차 이벤트 트리거(상승엣지 감지)",
        ))

        self.trigger_LeaveEvent = False
        self.register_variable(Boolean(
            "trigger_LeaveEvent",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete,  # 규약 준수
            description="방금 출차 이벤트 트리거(상승엣지 감지)",
        ))

        # ---------------------------- Parameters ---------------------------
        self.dayStartHour = 8
        self.register_variable(Integer(
            "dayStartHour",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.fixed,     # ✅ FMI 2.0 규격: parameter ⇒ fixed/tunable
            initial=Fmi2Initial.exact,
            start=self.dayStartHour,
            description="주간 시작 시(hour)",
        ))

        self.dayEndHour = 18
        self.register_variable(Integer(
            "dayEndHour",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.fixed,     # ✅
            initial=Fmi2Initial.exact,
            start=self.dayEndHour,
            description="주간 종료 시(hour). [dayStartHour, dayEndHour) 구간이 주간",
        ))

        self.dayLightIntensity = 0.1
        self.register_variable(Real(
            "dayLightIntensity",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.fixed,     # ✅
            initial=Fmi2Initial.exact,
            start=self.dayLightIntensity,
            description="주간 조도(0~1)",
        ))

        self.nightIdleIntensity = 0.2
        self.register_variable(Real(
            "nightIdleIntensity",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.fixed,     # ✅
            initial=Fmi2Initial.exact,
            start=self.nightIdleIntensity,
            description="야간 대기 조도(0~1)",
        ))

        self.motionHoldSeconds = 10.0
        self.register_variable(Real(
            "motionHoldSeconds",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.fixed,     # ✅
            initial=Fmi2Initial.exact,
            start=self.motionHoldSeconds,
            description="이벤트 발생 후 최대 밝기 유지 시간(초)",
        ))

        # ----------------------------- Outputs ----------------------------
        self.lightIntensity = 0.0
        self.register_variable(Real(
            "lightIntensity",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.continuous,
            initial=Fmi2Initial.calculated,
            description="현재 조도(0~1)",
        ))

        self.isNight = False
        self.register_variable(Boolean(
            "isNight",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,  # 규약 준수
            initial=Fmi2Initial.calculated,
            description="야간 여부(디버깅용)",
        ))

        # --------------------------- Internal states -----------------------
        self._prevPark = False
        self._prevLeave = False
        self._lastMotionTime = None  # float | None

    # def setup_experiment(self, start_time, stop_time, tolerance=None):
    #     return True

    def _is_night(self, seconds: float) -> bool:
        seconds_of_day = int(seconds) % SECONDS_PER_DAY
        hour = seconds_of_day // 3600
        return not (self.dayStartHour <= hour < self.dayEndHour)

    def _clamp01(self, x: float) -> float:
        return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x

    def do_step(self, current_time: float, step_size: float) -> bool:
        try:
            # 1) 주/야간 판정
            night = self._is_night(self.currentTime)
            self.isNight = night

            # 2) 트리거 상승엣지 감지
            park_edge = (self.trigger_ParkEvent and not self._prevPark)
            leave_edge = (self.trigger_LeaveEvent and not self._prevLeave)
            event_occurred = park_edge or leave_edge
            if event_occurred:
                self._lastMotionTime = float(self.currentTime)

            # 3) 조도 계산
            if not night:
                self.lightIntensity = self._clamp01(self.dayLightIntensity)
            else:
                if (self._lastMotionTime is not None) and \
                   ((self.currentTime - self._lastMotionTime) <= self.motionHoldSeconds):
                    self.lightIntensity = 1.0
                else:
                    self.lightIntensity = self._clamp01(self.nightIdleIntensity)

            # 4) 트리거 상태 업데이트
            self._prevPark = bool(self.trigger_ParkEvent)
            self._prevLeave = bool(self.trigger_LeaveEvent)
            return True
        except Exception as e:
            return False
