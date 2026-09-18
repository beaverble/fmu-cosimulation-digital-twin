# file: fmu/vehicle_properties.py
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    String, Boolean
)
from pathlib import Path
import json, time, os, secrets

slave_class = "VehicleProperties"

class VehicleProperties(Fmi2Slave):
    """
    06_vehicle_example.json에서 thingId, type, licensePlate 추출.
    - randomize_each_step=True(기본): 매 스텝마다 '셔플된 랜덤 순열'로 하나씩 출력(중복 최소화)
    - randomize_each_step=False     : 순차 순환 출력
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # -------- Inputs --------
        self.randomize_each_step = True
        self.register_variable(Boolean(
            "randomize_each_step",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete,
            description="True: 셔플 랜덤, False: 순차 순환"
        ))

        # -------- Outputs (모두 discrete String) --------
        self.vehicle_thingId = ""
        self.register_variable(String(
            "vehicle_thingId",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))
        self.vehicle_type = ""
        self.register_variable(String(
            "vehicle_type",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))
        self.vehicle_licenseplate = ""
        self.register_variable(String(
            "vehicle_licenseplate",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        # -------- 내부 상태 --------
        self._records = []   # [(thingId, type, plate), ...]
        self._idx = -1       # 순차 모드용 인덱스
        self._bag = []       # 랜덤 모드용 인덱스 봉투(셔플)

        # 인스턴스별 난수 시드(충분히 랜덤)
        seed = int.from_bytes(os.urandom(16), "big") ^ time.time_ns()
        self._rng = secrets.SystemRandom(seed)  # 암호학적 RNG 사용(시드 불필요하지만 일관성 위해 seed 섞음)

        self._load_vehicles()
        self._advance()  # 초기 1회 출력

    @staticmethod
    def _norm(s):
        return "" if s is None else str(s).strip()

    def _candidates(self):
        cands = []
        for attr in ("resources", "resource_path", "resourceLocation", "_resources_path"):
            p = getattr(self, attr, None)
            if p:
                P = Path(p)
                if P.exists():
                    cands += list(P.glob("06_vehicle_example.json"))
                    cands += list(P.glob("*vehicle*example*.json"))
        here = Path(__file__).resolve().parent
        for P in (here / "resources", here):
            if P.exists():
                cands += list(P.glob("06_vehicle_example.json"))
                cands += list(P.glob("*vehicle*example*.json"))
        return cands

    def _get_fields(self, obj):
        # thingId
        tid = ""
        for k in ("thingId", "vehicleId", "id"):
            v = obj.get(k);
            if v: tid = self._norm(v); break
        if not tid:
            attr = obj.get("attributes") or {}
            for k in ("thingId", "vehicleId", "id"):
                v = attr.get(k);
                if v: tid = self._norm(v); break
        # type
        vtype = ""
        for k in ("type", "vehicleType", "carType"):
            v = obj.get(k);
            if v: vtype = self._norm(v); break
        if not vtype:
            attr = obj.get("attributes") or {}
            for k in ("type", "vehicleType", "carType"):
                v = attr.get(k);
                if v: vtype = self._norm(v); break
        # licensePlate
        plate = ""
        for k in ("licensePlate", "plateNumber", "license", "license_plate"):
            v = obj.get(k);
            if v: plate = self._norm(v); break
        if not plate:
            attr = obj.get("attributes") or {}
            for k in ("licensePlate", "plateNumber", "license", "license_plate"):
                v = attr.get(k);
                if v: plate = self._norm(v); break
        return tid, vtype, plate

    def _load_vehicles(self):
        self._records.clear()
        for f in self._candidates():
            try:
                data = json.loads(Path(f).read_text(encoding="utf-8"))
            except Exception:
                continue

            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for k in ("vehicles", "items", "list"):
                    if isinstance(data.get(k), list):
                        items = data[k]; break
                if not items:
                    items = [data]

            for obj in items:
                if not isinstance(obj, dict):
                    continue
                tid, vtype, plate = self._get_fields(obj)
                if tid:
                    self._records.append((tid, vtype, plate))

            if self._records:
                break  # 첫 성공 파일만 사용

        # 랜덤 모드 봉투 초기화
        if self._records:
            self._bag = list(range(len(self._records)))
            self._rng.shuffle(self._bag)

    def _emit(self, idx):
        tid, vtype, plate = self._records[idx]
        self.vehicle_thingId = tid
        self.vehicle_type = vtype
        self.vehicle_licenseplate = plate

    def _advance(self):
        if not self._records:
            self.vehicle_thingId = ""
            self.vehicle_type = ""
            self.vehicle_licenseplate = ""
            return

        if self.randomize_each_step:
            if not self._bag:
                # 모두 소진되면 다시 셔플
                self._bag = list(range(len(self._records)))
                self._rng.shuffle(self._bag)
            idx = self._bag.pop()
            self._emit(idx)
        else:
            self._idx = (self._idx + 1) % len(self._records)
            self._emit(self._idx)

    def do_step(self, current_time: float, step_size: float) -> bool:
        try:
            self._advance()
            return True
        except Exception:
            return True
