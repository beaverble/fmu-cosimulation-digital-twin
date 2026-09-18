# -*- coding: utf-8 -*-
"""
FMU: FindSpaceTime
입력 : spaceID (String, input)
출력 : spaceId (String, output), timeToFindSpace_sec (Real, output)
규칙 : spaceID가 비어있지 않고 이전과 다르면 한 번만 랜덤 시간 계산.
주의 : 비-Real 변수 variability는 discrete (팀 규칙)
"""

import random
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    String, Real
)

class FindSpaceTime(Fmi2Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 내부 상태
        self._last_handled_id = None
        self.minSec = 60.0    # 1분
        self.maxSec = 600.0   # 10분

        # 입력
        self.spaceID = ""
        self.register_variable(String(
            "spaceID",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete,
            description="목표 공간 ID (입력)"
        ))

        # 출력 (요청대로 두 개만)
        self.spaceId = ""
        self.register_variable(String(
            "spaceId",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,
            description="목표 공간 ID (출력, 입력 에코)"
        ))

        self.timeToFindSpace_sec = 0.0
        self.register_variable(Real(
            "timeToFindSpace_sec",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,
            description="공간 찾는 데 걸린 시간(초)"
        ))

    # 시그니처 정합(오류 방지)
    def enter_initialization_mode(self):
        # 초기 출력 리셋
        self.spaceId = ""
        self.timeToFindSpace_sec = 0.0
        return super().enter_initialization_mode()

    def exit_initialization_mode(self):
        # t=0 샘플부터 값이 찍히게 초기화 시 바로 계산
        if self.spaceID and self.spaceID != self._last_handled_id:
            lo, hi = sorted((self.minSec, self.maxSec))
            self.spaceId = self.spaceID
            self.timeToFindSpace_sec = float(random.uniform(lo, hi))
            self._last_handled_id = self.spaceID

        return super().exit_initialization_mode()

    def do_step(self, current_time: float, step_size: float) -> bool:
        try:
            # 새 ID가 들어오면 한 번만 재계산
            if self.spaceID and self.spaceID != self._last_handled_id:
                lo, hi = sorted((self.minSec, self.maxSec))
                self.spaceId = self.spaceID
                self.timeToFindSpace_sec = float(random.uniform(lo, hi))
                self._last_handled_id = self.spaceID
            return True
        except Exception as e:
            return False
