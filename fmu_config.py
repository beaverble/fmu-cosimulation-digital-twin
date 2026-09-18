# fmu_config.py

from pathlib import Path
import time

# FMU 기본 경로
BASE = Path("myfmu")

# FMU 파일 경로 정의
FMU_PATHS = {
    "Facility":  BASE / "FacilityStatus.fmu",
    "Zone":      BASE / "ZoneOccupancy.fmu",
    "Space":     BASE / "SpaceOccupancy.fmu",
}

# 시뮬레이션 상수
DT = 3600.0     # 1시간 스텝
STEPS = 100      # 총 스텝 수
SEED = int(time.time())      # 랜덤 시드
TRIM = 10000      # 긴 문자열 출력 길이 제한

# FMU 라벨을 출력용 이름으로 매핑 (선택 사항이지만 일관성을 위해 유지)
LABEL_MAP = {
    "Facility": "FacilityStatus",
    "Zone": "ZoneOccupancy",
    "Space": "SpaceOccupancy",
    "InOut": "InOutEvent",
}
