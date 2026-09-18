# file: test_vehiclearrival_fmu.py
# -*- coding: utf-8 -*-
from fmpy import simulate_fmu

def main():
    fmu_path = r".\myfmu\VehicleArrival.fmu"

    # 0~60초, 1초 스텝으로 출력 변수 기록
    result = simulate_fmu(
        fmu_path,
        start_time=0.0,
        stop_time=60.0,
        step_size=1.0,
        output=['vehicle_arrival'],
        # 파라미터 변경 예시 (초기화 모드에서만 적용)
        start_values={
            'min_gap_s': 3.0,   #
            'max_gap_s': 10.0,   #
            'rng_seed':   0     # 0이면 매번 다른 랜덤, 123 등으로 고정 가능
        },
        record_events=True
    )

    # 펄스 발생 시점만 출력
    times = result['time']
    vals  = result['vehicle_arrival']
    for t, v in zip(times, vals):
        if v == 1 or v is True:
            print(f"[t={int(t)}s] vehicle_arrival=1 (도착 이벤트)")

if __name__ == "__main__":
    main()
