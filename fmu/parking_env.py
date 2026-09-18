# -*- coding: utf-8 -*-
# file: fmu/parking_env_random.py
import random
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    Real, Integer
)

# pythonfmu 빌더가 사용할 클래스 이름
slave_class = "ParkingEnv"

class ParkingEnv(Fmi2Slave):
    author = "DTD"
    description = "Random temperature/humidity/CO outputs each step"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ===== Parameters (범위 조절용; 필요 없으면 그대로 둠) =====
        self.temp_min_c = 10.0
        self.temp_max_c = 35.0
        self.humid_min_pct = 30.0
        self.humid_max_pct = 85.0
        self.co_min_ppm = 0.0
        self.co_max_ppm = 60.0
        self.random_seed = 42

        self.register_variable(Real("temp_min_c",    causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed))
        self.register_variable(Real("temp_max_c",    causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed))
        self.register_variable(Real("humid_min_pct", causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed))
        self.register_variable(Real("humid_max_pct", causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed))
        self.register_variable(Real("co_min_ppm",    causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed))
        self.register_variable(Real("co_max_ppm",    causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed))
        self.register_variable(Integer("random_seed", causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed))

        # ===== Outputs (스텝마다 새 랜덤값) =====
        self.env_temperature_c = 0.0
        self.env_humidity_pct = 0.0
        self.env_co_ppm = 0.0

        self.register_variable(Real("env_temperature_c", causality=Fmi2Causality.output))
        self.register_variable(Real("env_humidity_pct",  causality=Fmi2Causality.output))
        self.register_variable(Real("env_co_ppm",        causality=Fmi2Causality.output))

        # 내부 RNG
        self._rng = random.Random(self.random_seed)

    def exit_initialization_mode(self):
        self._rng = random.Random(int(self.random_seed))

    def _rand_between(self, a, b):
        lo = min(float(a), float(b))
        hi = max(float(a), float(b))
        return self._rng.uniform(lo, hi)

    def do_step(self, current_time: float, step_size: float) -> bool:
        self.env_temperature_c = self._rand_between(self.temp_min_c, self.temp_max_c)
        self.env_humidity_pct  = self._rand_between(self.humid_min_pct, self.humid_max_pct)
        self.env_humidity_pct  = max(0.0, min(100.0, self.env_humidity_pct))
        self.env_co_ppm        = max(0.0, self._rand_between(self.co_min_ppm, self.co_max_ppm))
        return True
