# file: fmu/vehicle_location.py
# FMI 2.0 Co-Simulation / pythonfmu 기반
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    Integer, String
)
from pathlib import Path
import json, random

# pythonfmu 빌더가 사용할 클래스 이름
slave_class = "VehicleLocation"

class VehicleLocation(Fmi2Slave):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ===== Inputs (외부 JSON 경로 등) =====
        self.vehicles_json_path = ""
        self.register_variable(String(
            "vehicles_json_path",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete
        ))

        self.random_seed = 0
        self.register_variable(Integer(
            "random_seed",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete
        ))

        # ===== Outputs (모두 discrete) =====
        self.vehicle_thingId = ""
        self.register_variable(String(
            "vehicle_thingId",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        self.vehicle_location = ""
        self.register_variable(String(
            "vehicle_location",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        self.vehicles_count = 0
        self.register_variable(Integer(
            "vehicles_count",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        # 내부 상태
        self._vehicles = []
        self._idx = -1
        self._facilities = (
            "smartParking:Facility1",
            "smartParking:Facility2",
            "smartParking:Facility3",
        )
        self._loaded = False

    def _load_from_resource_candidates(self):
        """FMU 리소스 폴더 기준으로 여러 후보 경로를 시도."""
        base = Path(__file__).parent  # FMU resource 디렉터리
        candidates = [
            base / "06_vehicle_example.json",       # 평탄화 케이스
            base / "json" / "06_vehicle_example.json",  # 하위폴더 포함 케이스
        ]
        for p in candidates:
            if p.is_file():
                return p
        # 혹시 모를 다른 구조까지 커버: 파일명으로 탐색
        found = list(base.rglob("06_vehicle_example.json"))
        return found[0] if found else None

    def _load_vehicles(self):
        # 1) 사용자가 입력으로 경로를 준 경우 최우선
        candidate = self.vehicles_json_path.strip()
        if candidate:
            p = Path(candidate)
        else:
            # 2) FMU 리소스에서 탐색
            p = self._load_from_resource_candidates()

        data = []
        if p and p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = []

        self._vehicles = []
        for obj in data:
            tid = obj.get("thingId", "")
            if isinstance(tid, str) and tid:
                self._vehicles.append(tid)

        self.vehicles_count = len(self._vehicles)
        self._loaded = True

        # 랜덤 시드 적용(원하면 입력으로 제어)
        if self.random_seed:
            random.seed(int(self.random_seed))

    def _ensure_loaded(self):
        if not self._loaded:
            self._load_vehicles()

    def do_step(self, current_time: float, step_size: float) -> bool:
        self._ensure_loaded()

        if not self._vehicles:
            # 방어적 기본 동작
            self.vehicle_thingId = ""
            self.vehicle_location = random.choice(self._facilities)
            return True

        # 라운드 로빈 선택
        from random import choice
        self.vehicle_thingId = choice(self._vehicles)

        # 위치는 Facility1/2/3 중 임의 선택
        self.vehicle_location = random.choice(self._facilities)
        return True
