# -*- coding: utf-8 -*-
# file: fmu/space_occupancy_modified.py
#
# SpaceOccupancy.fmu 내부 로직(자급자족 버전)
# - 외부에서 JSON 명령( set_space_status )으로 특정 공간의 isOpen을 갱신
# - 내부 상태를 스냅샷(spaces_snapshot_json)으로 내보냄
# - 모든 비-Real 변수 variability=discrete (프로젝트 규칙)

from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    Integer, String
)
from pathlib import Path
import json, random, time

class SpaceOccupancy(Fmi2Slave):
    author = "DTD"
    description = "Manage per-space open/closed flags and emit snapshot."

    def __init__(self, **kwargs):
        # kwargs 안에 builder가 넘겨주는 resources 경로가 들어옵니다.
        super().__init__(**kwargs)
        self._resources_path = Path(kwargs.get("resources", ""))

        # -------- Inputs --------
        # 메인 오케스트레이터에서 JSON 문자열로 명령을 넣어주세요.
        # 예) {"space_thingId": "smartParking:Space42", "space_isOpen": 1}
        self.set_space_status = ""
        self.register_variable(String(
            "set_space_status",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete
        ))

        # -------- Outputs --------
        self.spaces_count = 0
        self.register_variable(Integer(
            "spaces_count",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        self.spaces_snapshot_json = ""
        self.register_variable(String(
            "spaces_snapshot_json",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        # -------- 내부 상태 --------
        # 키: space_thingId -> {"space_zoneId": str, "space_isOpen": 0|1}
        self._spaces_map = {}

        # RNG (시드 고정 원하면 seed 고정하세요)
        self._rng = random.Random()
        self._rng.seed(time.time_ns() & 0xFFFFFFFF)

        # 원본 목록(초기 로드용): [("thingId","zoneId"), ...]
        self._spaces = []

        # 설정/초기화
        self._load_spaces()   # -> self._spaces 채움(없으면 더미)
        self._init_state()    # -> self._spaces_map 채움
        self._emit_snapshot() # 초기 스냅샷

    # ----------------------------------------------------
    # 리소스에서 공간 목록 로드 (없어도 빌드/런타임이 깨지지 않도록 방어)
    # ----------------------------------------------------
    def _load_spaces(self):
        """
        03_space_example.json에서 thingId/zoneId를 읽어
        self._spaces = [(thingId, zoneId), ...] 형태로 구축.
        파일이 없거나 포맷이 달라도 더미 2개로 안전 기동.
        """
        candidates = [
            # 빌드 시(builder)는 script 디렉터리를 resources로 넘겨줌
            self._resources_path / "03_space_example.json",
            # 런타임에 따라 resources/ 하위에 있을 수 있음
            self._resources_path / "resources" / "03_space_example.json",
        ]

        data = None
        for p in candidates:
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    break
                except Exception:
                    data = None

        if isinstance(data, list) and data:
            temp = []
            for row in data:
                tid = row.get("thingId") or row.get("space_thingId")
                zid = row.get("zoneId") or row.get("space_zoneId")
                if tid and zid:
                    temp.append((str(tid), str(zid)))
            if temp:
                self._spaces = temp
                return

        # 파일이 없거나 비어있으면 더미로 진행
        self._spaces = [
            ("smartParking:Space1", "smartParking:Zone1"),
            ("smartParking:Space2", "smartParking:Zone1"),
        ]

    # ----------------------------------------------------
    # 초기 상태 구성: 각 공간에 random isOpen 배정
    # ----------------------------------------------------
    def _init_state(self):
        for tid, zid in self._spaces:
            self._spaces_map[tid] = {
                "space_zoneId": zid,
                "space_isOpen": self._rng.randint(0, 1),
            }
        # 이후 원본 목록은 사용 안 함
        self._spaces = []

    # ----------------------------------------------------
    # 현재 내부 상태 -> 스냅샷(JSON 문자열)
    # ----------------------------------------------------
    def _emit_snapshot(self):
        snap = []
        for tid, rec in self._spaces_map.items():
            snap.append({
                "space_thingId": tid,
                "space_zoneId": rec["space_zoneId"],
                "space_isOpen": rec["space_isOpen"],
            })

        self.spaces_count = len(snap)
        try:
            self.spaces_snapshot_json = json.dumps(snap, ensure_ascii=False)
        except Exception:
            self.spaces_snapshot_json = "[]"

    # ----------------------------------------------------
    # 스텝: 입력 명령 반영 -> 스냅샷 갱신
    # ----------------------------------------------------
    def do_step(self, current_time: float, step_size: float) -> bool:
        if self.set_space_status:
            try:
                command = json.loads(self.set_space_status)
                tid = command.get("space_thingId")
                new_state = command.get("space_isOpen")

                # bool 지원(True/False)도 정수 1/0으로 변환
                if isinstance(new_state, bool):
                    new_state = 1 if new_state else 0

                if tid and (tid in self._spaces_map) and (new_state in (0, 1)):
                    self._spaces_map[tid]["space_isOpen"] = int(new_state)
                    print(f"[SpaceFMU] Updated {tid} -> isOpen={int(new_state)}")
                else:
                    print(f"[SpaceFMU] Ignored command: {self.set_space_status}")
            except json.JSONDecodeError:
                print(f"[SpaceFMU] JSON decode error: {self.set_space_status}")
            finally:
                # 한 번 처리 후 항상 클리어(메인에서도 클리어해도 중복 안전)
                self.set_space_status = ""

        self._emit_snapshot()
        return True
