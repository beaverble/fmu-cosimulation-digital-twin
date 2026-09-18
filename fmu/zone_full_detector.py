# -*- coding: utf-8 -*-
"""
FMU: ZoneFullDetector
입력:
  - zone_thingId (String)
  - occupiedspot (Integer)
동작:
  - resources/02_zone_example.json에서 zone_thingId와 동일한 thingId를 찾아 totalSpaces를 읽고,
    occupiedspot == totalSpaces 이면 isFull=1, 아니면 0
출력:
  - target_zone_thingId (String): 입력값 전달
  - isFull (Integer): 0/1
주의:
  - 모든 비-Real 변수 variability=discrete (FMI 2.0)
"""

import json
from pathlib import Path
from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    String, Integer
)

class ZoneFullDetector(Fmi2Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # -------- 입력 --------
        self.zone_thingId = ""
        self.occupiedspot = 0

        self.register_variable(String(
            "zone_thingId",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete,
            description="존 thingId (예: smartParking:Zone1)"
        ))
        self.register_variable(Integer(
            "occupiedspot",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete,
            description="현재 점유된 주차면 수"
        ))

        # -------- 출력 --------
        self.target_zone_thingId = ""
        self.isFull = 0

        self.register_variable(String(
            "target_zone_thingId",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,
            description="판정 대상 존 thingId (입력값 전달)"
        ))
        self.register_variable(Integer(
            "isFull",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,
            description="만차 여부 (0/1)"
        ))

        # -------- 리소스 JSON 로드 --------
        self._zone_total_spaces = {}
        try:
            # FMU 실행 시 스크립트와 리소스는 같은 resources 폴더에 들어갑니다.
            res_dir = Path(__file__).parent
            json_path = res_dir / "02_zone_example.json"
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    tid = item.get("thingId", "")
                    attrs = item.get("attributes") or {}
                    ts = attrs.get("totalSpaces", None)
                    if tid and ts is not None:
                        self._zone_total_spaces[tid] = int(ts)
            else:
                if self.logger:
                    self.logger.warning("[ZoneFullDetector] resources/02_zone_example.json 미존재")
        except Exception as e:
            if self.logger:
                self.logger.error(f"[ZoneFullDetector] JSON 로드 실패: {e}")

        self._start_time = 0.0

    def enter_initialization_mode(self):
        self.target_zone_thingId = self.zone_thingId
        self.isFull = self._compute_is_full()


    def exit_initialization_mode(self):
        pass

    def do_step(self, current_time, step_size):
        self.target_zone_thingId = self.zone_thingId
        self.isFull = self._compute_is_full()

        return True

    # 내부 판정
    def _compute_is_full(self) -> int:
        ts = self._zone_total_spaces.get(self.zone_thingId)
        if ts is None:
            # 미등록 존은 0 처리(만차 아님)
            return 0
        return 1 if int(self.occupiedspot) == int(ts) else 0

# python -m pythonfmu build -f .\fmu\zone_full_detector.py -d .\myfmu .\json\02_zone_example.json