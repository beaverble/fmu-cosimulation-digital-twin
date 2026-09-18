# ventilation_controller.py
# -*- coding: utf-8 -*-

from pythonfmu import (
    Fmi2Slave,
    Fmi2Causality,
    Fmi2Variability,
    Real,
)


class VentilationController(Fmi2Slave):
    """CO 농도를 기반으로 환풍기 속도를 비례 제어하는 FMU 컨트롤러."""

    def __init__(self, **kwargs):
        # 반드시 먼저 호출
        super().__init__(**kwargs)

        # ------------------------- 내부 상태/초기값 -------------------------
        self.coLevel_ppm = 0.0
        self.fanSpeed = 0.0
        self.safeThreshold_ppm = 50.0
        self.maxThreshold_ppm = 200.0

        # ------------------------- FMI 변수 등록 ---------------------------
        # 입력
        self.register_variable(
            Real(
                "coLevel_ppm",
                causality=Fmi2Causality.input,
                variability=Fmi2Variability.continuous,
                description="현재 CO 농도(ppm)"
            )
        )

        # 출력
        self.register_variable(
            Real(
                "fanSpeed",
                causality=Fmi2Causality.output,
                variability=Fmi2Variability.continuous,
                description="환풍기 속도 (0.0~1.0)"
            )
        )

        # 파라미터 (튜너블)
        self.register_variable(
            Real(
                "safeThreshold_ppm",
                causality=Fmi2Causality.parameter,
                variability=Fmi2Variability.tunable,
                description="환기 시작 농도(ppm)",
                start=self.safeThreshold_ppm,
            )
        )

        self.register_variable(
            Real(
                "maxThreshold_ppm",
                causality=Fmi2Causality.parameter,
                variability=Fmi2Variability.tunable,
                description="최대 환기 농도(ppm)",
                start=self.maxThreshold_ppm,
            )
        )

    def do_step(self, current_time: float, step_size: float) -> bool:
        # 입력값(coLevel_ppm)과 파라미터로 fanSpeed 갱신
        self.fanSpeed = self._compute_speed(self.coLevel_ppm, self.safeThreshold_ppm, self.maxThreshold_ppm)
        return True

    # ------------------------------------------------------------------
    # 유틸리티: 비례 제어 계산
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_speed(co_ppm: float, safe_ppm: float, max_ppm: float) -> float:
        # 경계/예외 처리
        if max_ppm <= safe_ppm:
            # 역전/동일 임계값인 경우: 단순 스위칭
            return 1.0 if co_ppm >= safe_ppm else 0.0

        if co_ppm < safe_ppm:
            return 0.0
        if co_ppm >= max_ppm:
            return 1.0

        # 선형 보간 (0.0~1.0)
        ratio = (co_ppm - safe_ppm) / (max_ppm - safe_ppm)
        # 수치 오차 안전 클램프
        if ratio < 0.0:
            ratio = 0.0
        elif ratio > 1.0:
            ratio = 1.0
        return ratio



