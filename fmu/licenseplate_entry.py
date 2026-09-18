# file: fmu/license_plate_entry.py
# purpose: 외부에서 받은 번호판(String) -> 입차기록(JSON String) 출력 FMU
#          출력 변수명은 요구사항대로 `ntryRecord` 입니다.
# FMI 규약: 모든 비-Real 변수는 variability=discrete (프로젝트 규칙)

from pythonfmu import (
    Fmi2Slave,
    Fmi2Causality,
    Fmi2Variability,
    String,
)
import json


class LicensePlateEntry(Fmi2Slave):
    """입차 번호판 인식 FMU

    입력:
        - licensePlate (String, input): 외부 인식 번호판. 예: "12가3456"
    출력:
        - ntryRecord   (String, output): JSON 문자열
          예: {"vehicle_plate": "12가3456", "entryTime": 120.5}

    동작 규칙:
        - 입력 licensePlate 가 공백이 아니고 직전 처리 값과 다르면,
          현재 시뮬레이션 시각(current_time)으로 JSON을 만들어 ntryRecord에 기록합니다.
        - 같은 번호판을 다시 기록하려면 입력을 "" 로 한번 비웠다가 다시 설정하세요.
    """

    author = "DTD"
    description = (
        "licensePlate(String) → ntryRecord(JSON String) 변환 FMU"
    )

    def __init__(self, **kwargs):
        # FMI 베이스 초기화 먼저
        super().__init__(**kwargs)

        # --- Inputs ---
        self.licensePlate = ""
        self.register_variable(String(
            "licensePlate",
            causality=Fmi2Causality.input,
            variability=Fmi2Variability.discrete,
            description="인식된 차량 번호판 (예: '12가3456')"
        ))

        # --- Outputs ---
        self.ntryRecord = ""  # JSON 문자열
        self.register_variable(String(
            "ntryRecord",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete,
            description="입차기록 JSON: { 'vehicle_plate': <str>, 'entryTime': <float> }"
        ))

        # --- Internal state ---
        self._last_plate = None  # 마지막으로 JSON을 생성했던 번호판 값
        self._start_time = 0.0

    # 중요: Fmi2Slave 시그니처와 동일하게 유지 (tolerance 포함)

    # stop_time, tolerance, 추가 인자는 이 FMU 로직에서는 사용하지 않습니다.
    # 반환값은 사용되지 않으므로 명시 반환 불필요

    def do_step(self, current_time, step_size):
        # 입력 번호판 읽기 (str 보장 및 양끝 공백 제거)
        plate = self.licensePlate if isinstance(self.licensePlate, str) else ""
        plate = plate.strip()

        if plate:
            # 새 번호판이 들어왔을 때만 JSON 생성
            if self._last_plate != plate:
                record = {
                    "vehicle_plate": plate,
                    # 현재 시뮬레이션 시각(초). 필요 시 소수점 유지
                    "entryTime": float(current_time)
                }
                # ensure_ascii=False로 한글 그대로 보존
                self.ntryRecord = json.dumps(record, ensure_ascii=False)
                self._last_plate = plate
        else:
            # 입력을 비우면 같은 번호판을 다시 이벤트로 발행 가능
            self._last_plate = None

        return True
