# file: test_schedule.py

import fmpy
from fmpy import simulate_fmu
import os
import pandas as pd # 결과를 깔끔하게 보기 위해 pandas 사용

pd.set_option('display.max_columns', None)  # 모든 열을 출력 (가로로 길어질 때 대비)
pd.set_option('display.width', 1000)

# 1. FMU 파일 경로 설정
fmu_filename = 'myfmu/ScheduleManager.fmu'
if not os.path.exists(fmu_filename):
    print(f"오류: {fmu_filename}을 찾을 수 없습니다.")
    print("1단계: 'pythonfmu build -f fmu/schedule_manager.py'를 먼저 실행하세요.")
    exit()

print(f"'{fmu_filename}' 로드 중...")

# 2. 시뮬레이션 매개변수 (Parameters) 설정
# 이 값들을 변경하며 FMU가 잘 작동하는지 테스트합니다.
start_values = {
    'start_datetime_str': "2025-11-05T09:00:00", # 수요일 오전 9시 (피크타임)
    'time_zone_str': "Asia/Seoul",
    'peak_time_windows_str': "08:00-10:00,17:00-19:00", # 피크 타임 설정
    'holiday_list_str': "2025-11-06", # 다음 날(목요일)을 공휴일로 지정
    'peak_days_int': 1234  # 월화수목 (0123)
}

# 3. 시뮬레이션 설정
start_time = 0.0
stop_time = 48 * 3600.0  # 48시간 (초 단위)
step_size = 3600.0       # 1시간 (3600초) 간격으로 스텝 실행

# 4. FMU에서 출력할 변수 목록
# ScheduleManager.fmu의 'output' 변수들
output_vars = [
    'isPeakTime',
    'isHoliday',
    'isWeekend',
    'day_of_week',
    'current_hour_float',
    'current_real_datetime_str'
]

# 5. 시뮬레이션 실행
print("시뮬레이션을 48시간 동안 실행합니다 (1시간 간격)...")
result = simulate_fmu(
    filename=fmu_filename,
    start_time=start_time,
    stop_time=stop_time,
    step_size=step_size,
    start_values=start_values,
    output=output_vars,
    fmi_type='CoSimulation',
    output_interval=step_size
)

# 6. 결과 출력 (Pandas DataFrame 활용)
print("\n--- 시뮬레이션 결과 ---")
df = pd.DataFrame(result)

# 시간을 '초'에서 '시'로 변환
df['time_hours'] = df['time'] / 3600.0
df = df.set_index('time_hours') # 시간을 인덱스로 설정
df = df.drop('time', axis=1)    # 기존 time 컬럼 삭제

# day_of_week를 요일 문자열로 변환 (0=월, 1=화, 2=수, 3=목...)
days = ["월", "화", "수", "목", "금", "토", "일"]
df['day_of_week_str'] = df['day_of_week'].apply(lambda x: days[x])

print(df)