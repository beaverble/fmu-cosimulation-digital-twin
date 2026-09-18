# file: fmu/zone_occupancy.py
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    String
)
from pathlib import Path
import json, random, time

slave_class = "ZoneOccupancy"

class ZoneOccupancy(Fmi2Slave):
    """
    All-zones random snapshot FMU
    - 입력: (없음)
    - 출력(discrete):
        zones_snapshot_json : String
          [
            {"zone_thingId": "...", "zone_facilityId": "...", "zone_isOpen": 0/1},
            ...
          ]
    - 동작:
        resources/02_zone_example.json(또는 zone_example.json)에서 모든 존을 로드하고,
        매 do_step마다 zone_isOpen을 랜덤(0/1)으로 생성하여 JSON으로 내보냄.
    """

    author = "DTD"
    description = "Emit all zones with random isOpen each step (JSON only)"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ---------- Output (discrete) ----------
        self.zones_snapshot_json = "[]"
        self.register_variable(String(
            "zones_snapshot_json",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        # ---------- 내부 상태 ----------
        # [(thingId, facilityId), ...]
        self._zones = []
        # RNG (인스턴스마다 다른 seed)
        seed = int(time.time() * 1000) ^ (id(self) & 0xFFFFFFFF)
        self._rng = random.Random(seed)

        self._load_zones_from_resources()
        self._emit_snapshot()  # 초기 스냅샷

    # ---------- 리소스 로드 ----------
    @staticmethod
    def _norm(s):
        return "" if s is None else str(s).strip()

    def _resource_candidates(self):
        cands = []
        for attr in ("resources", "resource_path", "resourceLocation", "_resources_path"):
            p = getattr(self, attr, None)
            if p:
                P = Path(p)
                if P.exists():
                    cands += list(P.glob("02_zone_example.json"))
                    cands += list(P.glob("zone_example.json"))
        # fallback: 모듈 폴더/리소스 폴더도 탐색
        here = Path(__file__).resolve().parent
        for P in (here / "resources", here):
            if P.exists():
                cands += list(P.glob("02_zone_example.json"))
                cands += list(P.glob("zone_example.json"))
        return cands

    def _load_zones_from_resources(self):
        self._zones.clear()
        for f in self._resource_candidates():
            try:
                data = json.loads(Path(f).read_text(encoding="utf-8"))
            except Exception:
                continue
            items = data if isinstance(data, list) else [data]
            for obj in items:
                if not isinstance(obj, dict):
                    continue
                tid = self._norm(obj.get("thingId"))
                fac = self._norm((obj.get("attributes") or {}).get("facilityId"))
                if tid and fac:
                    self._zones.append((tid, fac))
            if self._zones:
                return  # 첫 성공 파일만 사용

    # ---------- 스냅샷 생성 ----------
    def _emit_snapshot(self):
        snap = []
        for tid, fac in self._zones:
            snap.append({
                "zone_thingId": tid,
                "zone_facilityId": fac,
                "zone_isOpen": self._rng.randint(0, 1)
            })
        try:
            self.zones_snapshot_json = json.dumps(snap, ensure_ascii=False)
        except Exception:
            self.zones_snapshot_json = "[]"

    # ---------- FMI ----------
    def do_step(self, current_time: float, step_size: float) -> bool:
        # 매 스텝마다 새 랜덤값으로 갱신
        self._emit_snapshot()
        return True
