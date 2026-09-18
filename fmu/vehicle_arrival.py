# -*- coding: utf-8 -*-
"""
FMU: VehicleArrival
설명: 시뮬레이션 시간이 흐르다가 랜덤한 시점에 '한 번만' True(1)로 펄스 출력.
      - vehicle_arrival: Boolean 출력 (펄스; 해당 스텝에만 True)
      - min_gap_s, max_gap_s: 두 펄스 사이 최소/최대 간격(초) 파라미터
      - rng_seed: 0이면 난수 시드 자동, 0이 아니면 고정 시드(재현성)
주의: do_step()가 호출된 스텝에만 True로 보이며, 다음 스텝에는 자동으로 False로 리셋됩니다.
"""

import random
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    Boolean, Integer, Real
)


class VehicleArrival(Fmi2Slave):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # -------- Parameters (초기화 모드에서만 설정) --------
        self.min_gap_s = 3.0   # 두 펄스 사이 최소 간격(초)
        self.max_gap_s = 12.0  # 두 펄스 사이 최대 간격(초)
        self.rng_seed  = 0     # 0이면 자동 시드, 0이 아니면 고정 시드

        self.register_variable(Real(
            "min_gap_s",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.fixed,
            description="두 도착 이벤트 사이 최소 간격(초)"
        ))
        self.register_variable(Real(
            "max_gap_s",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.fixed,
            description="두 도착 이벤트 사이 최대 간격(초)"
        ))
        self.register_variable(Integer(
            "rng_seed",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.fixed,
            description="0: 자동 시드, 그 외: 고정 시드(재현성)"
        ))

        # -------- Outputs --------
        self.vehicle_arrival = False
        self.register_variable(Boolean(
            "vehicle_arrival",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,
            description="해당 스텝에서 도착 이벤트가 발생하면 True(1), 아니면 False(0)"
        ))

        # 내부 상태
        self._start_time = 0.0
        self._stop_time = None
        self._tolerance = None
        self._next_fire_time = None
        self._rng = random.Random()

    # 중요: Fmi2Slave 시그니처와 일치(에러 방지)
    def setup_experiment(self, start_time, stop_time, tolerance=None):
        self._start_time = 0.0 if start_time is None else float(start_time)
        self._stop_time = stop_time
        self._tolerance = tolerance

    def enter_initialization_mode(self):
        super().enter_initialization_mode()

    def exit_initialization_mode(self):
        super().exit_initialization_mode()

        # RNG 시드 설정
        if int(self.rng_seed) != 0:
            self._rng.seed(int(self.rng_seed))
        else:
            self._rng.seed()  # 시스템 시드

        # 첫 이벤트 예약
        self._schedule_next(self._start_time)

    # 다음 이벤트 시간을 현재 기준으로 예약
    def _schedule_next(self, base_time):
        # min/max 보정
        mg = float(self.min_gap_s)
        xg = float(self.max_gap_s)
        if mg <= 0:
            mg = 0.1
        if xg < mg:
            xg = mg

        gap = self._rng.uniform(mg, xg)
        self._next_fire_time = base_time + gap

    def do_step(self, current_time: float, step_size: float) -> bool:
        # 기본값: 펄스 OFF
        self.vehicle_arrival = False

        if self._next_fire_time is None:
            self._schedule_next(current_time)

        window_end = current_time + step_size
        # 현재 스텝 구간 (current_time, window_end] 안에 _next_fire_time이 들어오면 펄스_
