# file: fmu/inout_event.py
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    Integer, String
)
from pathlib import Path
import json, random, time

# pythonfmu 빌더가 사용할 클래스 이름
slave_class = "InOutEvent"

class InOutEvent(Fmi2Slave):
    """
    06_vehicle_example.json을 읽어 배열에서 thingId들을 수집하고,
    매 스텝마다 무작위 vehicle_thingId 1개와 transaction_status(0/1)를 출력.

    출력(discrete):
      - vehicle_thingId     : String
      - transaction_status  : Integer (0 또는 1)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # -------- Outputs (모두 discrete) --------
        self.vehicle_thingId = ""
        self.register_variable(String(
            "vehicle_thingId",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        self.transaction_status = 0
        self.register_variable(Integer(
            "transaction_status",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        # -------- 내부 상태 --------
        self._thing_ids = []

        # 인스턴스별 RNG (seed 분산)
        seed = int(time.time() * 1000) ^ (id(self) & 0xFFFFFFFF)
        self._rng = random.Random(seed)

        # JSON 로딩 및 초기 1회 샘플 방출
        self._load_vehicles()
        self._emit_sample()

    # ----------------- 유틸 -----------------
    @staticmethod
    def _norm(s):
        return "" if s is None else str(s).strip()

    def _candidates(self):
        """FMU 내부/외부 여러 경로에서 06_vehicle_example.json 후보를 수집"""
        cands = []
        # FMU 리소스 경로 후보
        for attr in ("resources", "resource_path", "resourceLocation", "_resources_path"):
            p = getattr(self, attr, None)
            if p:
                P = Path(p)
                if P.exists():
                    cands += list(P.glob("06_vehicle_example.json"))
                    cands += list(P.glob("*vehicle*example*.json"))
        # 스크립트 인접 경로(백업 탐색)
        here = Path(__file__).resolve().parent
        for P in (here / "resources", here):
            if P.exists():
                cands += list(P.glob("06_vehicle_example.json"))
                cands += list(P.glob("*vehicle*example*.json"))
        return cands

    def _get_thingId(self, obj):
        """여러 필드명 가능성 대응해서 thingId 추출"""
        for k in ("thingId", "vehicleId", "id"):
            v = obj.get(k)
            if v: return self._norm(v)
        attr = obj.get("attributes") or {}
        for k in ("thingId", "vehicleId", "id"):
            v = attr.get(k)
            if v: return self._norm(v)
        return ""

    # ----------------- JSON 로딩 -----------------
    def _load_vehicles(self):
        self._thing_ids.clear()

        for f in self._candidates():
            try:
                data = json.loads(Path(f).read_text(encoding="utf-8"))
            except Exception:
                continue

            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # 흔한 컨테이너 키
                for k in ("vehicles", "items", "list"):
                    if isinstance(data.get(k), list):
                        items = data[k]
                        break
                if not items:
                    items = [data]  # 단일 오브젝트도 수용

            for obj in items:
                if not isinstance(obj, dict):
                    continue
                tid = self._get_thingId(obj)
                if tid:
                    self._thing_ids.append(tid)

            if self._thing_ids:
                return  # 첫 성공 파일만 사용

        # 비어있어도 예외는 던지지 않고, 빈 문자열 출력로 동작

    # ----------------- 스텝 출력 -----------------
    def _emit_sample(self):
        # 차량 thingId 무작위 선택 (비어있으면 빈 문자열 유지)
        if self._thing_ids:
            self.vehicle_thingId = self._rng.choice(self._thing_ids)
        else:
            self.vehicle_thingId = ""

        # 0/1 무작위
        self.transaction_status = self._rng.randint(0, 1)

    # ----------------- FMI -----------------
    def do_step(self, current_time: float, step_size: float) -> bool:
        try:
            self._emit_sample()
            return True
        except Exception:
            # 안전하게 이전 값 유지하고 계속 진행
            return True
