# file: fmu/driver_behavior.py
# -*- coding: utf-8 -*-

from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    Real, Integer, String, Boolean
)
import time, math, random

# pythonfmu 빌더가 사용할 클래스 이름 지정
slave_class = "DriverBehavior"


def _clamp(x, vmin=None, vmax=None):
    if vmin is not None:
        x = max(x, vmin)
    if vmax is not None:
        x = min(x, vmax)
    return x


class DriverBehavior(Fmi2Slave):
    """
    무작위 운전자 행동 시간 FMU
    - 출력(Real): timeToFindSpace [seconds]
    - 분포: uniform / normal / lognormal / exponential
    - 규칙: 모든 비-Real 변수는 variability=discrete (프로젝트 규칙)
    """

    author = "DTD"
    description = "Generates random driver 'time to find a space' duration. [seconds]"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ===== Inputs (모두 discrete: String/Integer/Boolean) =====
        self.seed = 0
        self.register_variable(Integer(
            "seed",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete
        ))

        # 공간 찾기 시간 분포 선택
        self.find_dist = "exponential"
        self.register_variable(String(
            "find_dist",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete
        ))

        # 분포 파라미터 (Real)
        # - normal: mean, std
        # - lognormal: mean, std (목표 평균/표준편차; 내부 변환)
        # - uniform: min, max
        # - exponential: mean (lambda = 1/mean)
        self.find_mean = 180.0  # s
        self.find_std  = 60.0
        self.find_min  = 10.0
        self.find_max  = 900.0
        self.register_variable(Real("find_mean", causality=Fmi2Causality.input))
        self.register_variable(Real("find_std",  causality=Fmi2Causality.input))
        self.register_variable(Real("find_min",  causality=Fmi2Causality.input))
        self.register_variable(Real("find_max",  causality=Fmi2Causality.input))

        # 리샘플 제어 (discrete)
        self.auto_resample = True      # 매 스텝 자동 리샘플
        self.resample_trigger = False  # False->True 후 다음 스텝 1회만 리샘플
        self.register_variable(Boolean(
            "auto_resample",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete
        ))
        self.register_variable(Boolean(
            "resample_trigger",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete
        ))

        # ===== Output (Real) =====
        self.timeToFindSpace = 0.0  # [s]
        self.register_variable(Real(
            "timeToFindSpace",
            causality=Fmi2Causality.output
        ))

        # ===== Internal =====
        self._rng = random.Random()
        self._t = 0.0
        self._step = 0

    # --- FMI life-cycle hooks -------------------------------------------------

    def enter_initialization_mode(self):
        # 시드 설정
        seed_val = int(self.seed) if self.seed else int(time.time() * 1e6) & 0xFFFFFFFF
        self._rng.seed(seed_val)

        # 초기 1회 샘플
        self._resample()

    def do_step(self, current_time: float, step_size: float) -> bool:
        self._t = current_time + step_size
        self._step += 1

        if self.auto_resample or self.resample_trigger:
            self._resample()
            self.resample_trigger = False

        return True

    # --- Sampling helpers -----------------------------------------------------

    def _resample(self):
        self.timeToFindSpace = self._draw(
            self.find_dist, self.find_mean, self.find_std, self.find_min, self.find_max
        )

    def _draw(self, dist: str, mean: float, std: float, vmin: float, vmax: float) -> float:
        d = (dist or "").strip().lower()
        x = 0.0

        if d == "uniform":
            a = vmin if vmin is not None else 0.0
            b = vmax if vmax is not None and vmax > a else max(a + 1.0, mean * 2 if mean > a else a + 1.0)
            x = self._rng.uniform(a, b)

        elif d == "exponential":
            m = max(mean, 1e-6)
            x = self._rng.expovariate(1.0 / m)

        elif d == "lognormal":
            m = max(mean, 1e-6)
            s = max(std, 1e-6)
            sigma2 = math.log(1.0 + (s / m) ** 2)
            sigma = math.sqrt(sigma2)
            mu = math.log(m) - 0.5 * sigma2
            x = self._rng.lognormvariate(mu, sigma)

        else:  # default: normal
            mu = mean
            sd = max(std, 1e-6)
            for _ in range(8):
                x = self._rng.gauss(mu, sd)
                if x >= 0:
                    break
            x = max(0.0, x)

        x = _clamp(x, vmin if vmin is not None else 0.0, vmax if vmax is not None else None)
        return float(x)
