
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    Integer, String
)
from pathlib import Path
import json, random, time

# pythonfmu 빌더가 사용할 클래스 이름 지정
slave_class = "SpaceOccupancy"

class SpaceOccupancy(Fmi2Slave):
    """
    03_space_example.json을 읽어 모든 space의 thingId/zoneId를 수집하고,
    매 스텝마다 각 space에 대해 space_isOpen(0/1)을 랜덤으로 부여하여
    JSON 배열 형태로 한 번에 출력합니다.

    출력(discrete):

      - spaces_snapshot_json    : String
        예) [
              {"space_thingId": "...", "space_zoneId": "...", "space_isOpen": 0/1},
              ...
            ]
    """
    author = "DTD"
    description = "Emit ALL spaces with random isOpen each step (from 03_space_example.json)."

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # -------- Outputs (모두 discrete, start 지정 금지) --------
        self.spaces_count = 0


        self.spaces_snapshot_json = ""
        self.register_variable(String(
            "spaces_snapshot_json",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        # -------- 내부 상태 --------
        # 원천 목록: [(thingId, zoneId), ...]
        self._spaces = []
        # 인스턴스별 RNG (seed 분산)
        seed = int(time.time() * 1000) ^ (id(self) & 0xFFFFFFFF)
        self._rng = random.Random(seed)

        self._load_spaces()
        self._emit_snapshot()  # 초기 1회

    # ----------------- JSON 로딩 -----------------
    @staticmethod
    def _norm(s):
        return "" if s is None else str(s).strip()

    def _candidates(self):
        cands = []
        # FMU 리소스 경로 후보
        for attr in ("resources", "resource_path", "resourceLocation", "_resources_path"):
            p = getattr(self, attr, None)
            if p:
                P = Path(p)
                if P.exists():
                    cands += list(P.glob("03_space_example.json"))
                    cands += list(P.glob("*space*example*.json"))
        # 스크립트 인접 경로도 백업으로 탐색
        here = Path(__file__).resolve().parent
        for P in (here / "resources", here):
            if P.exists():
                cands += list(P.glob("03_space_example.json"))
                cands += list(P.glob("*space*example*.json"))
        return cands

    def _get_thingId(self, obj):
        for k in ("thingId", "spaceId", "id"):
            v = obj.get(k)
            if v: return self._norm(v)
        attr = obj.get("attributes") or {}
        for k in ("thingId", "spaceId", "id"):
            v = attr.get(k)
            if v: return self._norm(v)
        return ""

    def _get_zoneId(self, obj):
        for k in ("zoneId", "zone_thingId", "zoneThingId", "zone"):
            v = obj.get(k)
            if v: return self._norm(v)
        attr = obj.get("attributes") or {}
        for k in ("zoneId", "zone_thingId", "zoneThingId", "zone"):
            v = attr.get(k)
            if v: return self._norm(v)
        rel = obj.get("relations") or {}
        for k in ("zoneId", "zone_thingId", "zoneThingId", "zone"):
            v = rel.get(k)
            if v: return self._norm(v)
        return ""

    def _load_spaces(self):
        self._spaces.clear()
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
                for k in ("spaces", "items", "list"):
                    if isinstance(data.get(k), list):
                        items = data[k]
                        break
                if not items:
                    items = [data]  # 단일 오브젝트도 수용

            for obj in items:
                if not isinstance(obj, dict):
                    continue
                tid = self._get_thingId(obj)
                if not tid:
                    continue
                zid = self._get_zoneId(obj)
                self._spaces.append((tid, zid))

            if self._spaces:
                return  # 첫 성공 파일만 사용

    # ----------------- 스냅샷 생성 -----------------
    def _emit_snapshot(self):
        snap = []
        for tid, zid in self._spaces:
            snap.append({
                "space_thingId": tid,
                "space_zoneId": zid,
                "space_isOpen": self._rng.randint(0, 1)
            })
        self.spaces_count = len(snap)
        try:
            self.spaces_snapshot_json = json.dumps(snap, ensure_ascii=False)
        except Exception:
            self.spaces_snapshot_json = "[]"

    # ----------------- FMI -----------------
    def do_step(self, current_time: float, step_size: float) -> bool:
        # 매 스텝마다 새로운 랜덤 스냅샷 생성
        self._emit_snapshot()
        return True

