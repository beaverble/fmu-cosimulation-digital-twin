# -*- coding: utf-8 -*-
"""
LightingController.fmu 간단 시뮬레이션 테스트
- 0~120초, 1초 스텝
- t=20s: 주차 트리거(1초), t=50s: 출차 트리거(1초)
- 기본 파라미터(08~18 주간) 기준: 본 시뮬레이션은 hour=0이라 야간으로 동작
"""

import numpy as np
from fmpy import simulate_fmu


def main():
    fmu_path = r"myfmu/LightingController.fmu"

    start_time = 0.0
    stop_time = 120.0
    step = 1.0
    times = np.arange(start_time, stop_time + step, step)

    # 입력 신호: currentTime, trigger_ParkEvent, trigger_LeaveEvent
    park = np.zeros_like(times)
    leave = np.zeros_like(times)
    park[times == 20.0] = 1.0   # 1초 펄스
    leave[times == 50.0] = 1.0  # 1초 펄스

    # fmpy input 형식: time 필드는 반드시 첫 번째
    input_dtype = [
        ("time", np.float64),
        ("currentTime", np.float64),
        ("trigger_ParkEvent", np.float64),   # Boolean -> 0/1 float로 전달
        ("trigger_LeaveEvent", np.float64),
    ]
    input_data = np.zeros(times.shape[0], dtype=input_dtype)
    input_data["time"] = times
    input_data["currentTime"] = times  # 편의상 시뮬 시간 == currentTime
    input_data["trigger_ParkEvent"] = park
    input_data["trigger_LeaveEvent"] = leave

    result = simulate_fmu(
        filename=fmu_path,
        start_time=start_time,
        stop_time=stop_time,
        output=["lightIntensity", "isNight"],
        input=input_data,
        start_values={
            # 필요 시 파라미터를 여기서 변경 가능
            "dayStartHour": 8,
            "dayEndHour": 18,
            # "dayLightIntensity": 0.1,
            # "nightIdleIntensity": 0.2,
            # "motionHoldSeconds": 10.0,
        },
        output_interval=step,
        record_events=True,
    )

    # 샘플 출력: 처음/중간/끝
    idxs = [0, len(result) // 2, -1]
    for i in idxs:
        t = float(result["time"][i])
        hour = int(t % 86400) // 3600
        intensity = float(result["lightIntensity"][i])
        is_night = int(result["isNight"][i])
        print(f"[sample] t={t:.0f}s (hour={hour}) -> lightIntensity={intensity:.3f}, isNight={is_night}")


if __name__ == "__main__":
    main()
