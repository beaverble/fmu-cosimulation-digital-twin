# -*- coding: utf-8 -*-
"""
FacilityThingsSnapshot (FMI 2.0, Co-Simulation)
- 입력 파라미터(모두 tunable):
    facility_json (String): JSON 경로(기본: json/01_facility_example.json)
    random_seed   (Integer): 난수 시드(>=0 이면 시드 고정, <0이면 매 실행마다 다른 난수)
- 출력(1개):
    facilities_snapshot_json (String, discrete):
        [
          {"facility_thingId":"...", "facility_isOpen":0|1},
          ...
        ]
- 동작:
    초기화 시 JSON에서 모든 thingId를 수집하고, 각 스텝마다 각 항목의 facility_isOpen을 랜덤(0/1)으로 갱신하여
    facilities_snapshot_json 문자열로 제공합니다. (가변 길이 출력을 위해 스냅샷 JSON 1개로 묶었습니다)
"""
import os
import json
import random
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    String, Integer
)

slave_class = "ZoneOccupancy"

class FacilityStatus(Fmi2Slave):
    author = "DTD"
    description = "Emit snapshot of all facility_thingId with random isOpen(0/1) per step."

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 내부 상태
        self._thing_ids = []           # ['id1','id2',...]
        self._rng = random.Random()
        self.facility_json = "json/01_facility_example.json"
        self.random_seed = -1          # <0: 자유난수 / >=0: 고정 시드

        # 출력: 스냅샷(JSON 문자열) — 비-Real 출력은 discrete
        self.register_variable(String(
            "facilities_snapshot_json",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,
            description="JSON array of {facility_thingId, facility_isOpen(0/1)}"
        ))

        # 파라미터: tunable (parameter+discrete 조합은 FMI 2.0 위반이므로 주의)
        self.register_variable(String(
            "facility_json",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.tunable,
            start=self.facility_json,
            description="Path to 01_facility_example.json"
        ))
        self.register_variable(Integer(
            "random_seed",
            causality=Fmi2Causality.parameter,
            variability=Fmi2Variability.tunable,
            start=self.random_seed,
            description="Random seed (>=0 to fix sequence)"
        ))

        # 출력 값 보관용(모델 변수 값)
        self.facilities_snapshot_json = "[]"

    # 초기화: JSON 로드, thingId 수집, RNG 시드 설정, 최초 스냅샷 생성
    def enter_initialization_mode(self) -> bool:
        path = self._resolve_json_path(self.facility_json)
        self._thing_ids = self._load_thing_ids(path)
        if isinstance(self.random_seed, int) and self.random_seed >= 0:
            self._rng.seed(self.random_seed)
        self._update_snapshot_random()
        return True

    # 매 스텝마다 랜덤 갱신
    def do_step(self, current_time: float, step_size: float) -> bool:
        self._update_snapshot_random()
        return True

    # ---------- 내부 유틸 ----------
    def _resolve_json_path(self, given: str) -> str:
        # 1) 그대로 존재
        if given and os.path.isfile(given):
            return given
        # 2) CWD 기준
        if given:
            cand = os.path.join(os.getcwd(), given)
            if os.path.isfile(cand):
                return cand
        # 3) 스크립트 근처 기본 경로들
        here = os.path.dirname(os.path.abspath(__file__))
        for rel in (
            "01_facility_example.json",
            os.path.join("json", "01_facility_example.json"),
            "facility_example.json",
            os.path.join("json", "facility_example.json"),
        ):
            cand = os.path.join(here, rel)
            if os.path.isfile(cand):
                return cand
        # 4) 폴백
        return os.path.join(os.getcwd(), "json", "01_facility_example.json")

    def _load_thing_ids(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []

        # 다양한 스키마 대응: 배열 / 래퍼객체+배열 / 단일 객체
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ("facilities", "items", "records", "data", "list"):
                if isinstance(data.get(key), list):
                    items = data[key]
                    break
            else:
                items = [data]
        else:
            items = []

        ids, seen = [], set()
        for obj in items:
            if isinstance(obj, dict):
                tid = obj.get("thingId") or obj.get("facilityId")
                if isinstance(tid, str) and tid and tid not in seen:
                    seen.add(tid)
                    ids.append(tid)
        return ids

    def _update_snapshot_random(self):
        arr = []
        for tid in self._thing_ids:
            arr.append({
                "facility_thingId": tid,
                "facility_isOpen": int(self._rng.randint(0, 1))  # 0 또는 1
            })
        self.facilities_snapshot_json = json.dumps(arr, ensure_ascii=False)
