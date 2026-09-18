# -*- coding: utf-8 -*-
"""
ParkingFeeCalculator.fmu 단위 테스트
- 시나리오 A: 평일 9분 주차 -> 무료 (0원)
- 시나리오 B: 평일 2시간 5분(125분) -> (125-10)=115분 과금, 10분 단위 올림 12단위, 12*500=6000원
- 시나리오 C: 공휴일 1시간 30분(90분) -> (90-10)=80분 과금, 8단위, 단가 750 => 6000원
- 시나리오 D: 입차>=출차(오류/0초) -> 0원
"""
from pathlib import Path
import numpy as np
from fmpy import simulate_fmu

BASE = Path("myfmu")
FMU_PATH = BASE / "ParkingFeeCalculator.fmu"

def simulate_case(exit_sec, entry_sec, is_holiday):
    """exitTime을 시간축 그대로 흘려보내고, entryRecord/isHoliday는 상수로 공급"""
    # 1초 간격 타임라인
    t = np.arange(0, int(exit_sec) + 1, dtype=np.float64) if exit_sec > 0 else np.array([0.0])

    # fmpy 입력 배열 정의 (컬럼명은 FMU의 변수명과 동일)
    input_dtype = [
        ('time', np.float64),
        ('exitTime', np.float64),
        ('entryRecord', np.float64),
        ('isHoliday', np.bool_)
    ]
    u = np.zeros(t.shape[0], dtype=input_dtype)
    u['time'] = t
    u['exitTime'] = t                 # 출차시간 입력을 시뮬레이션 시간과 동일하게
    u['entryRecord'] = float(entry_sec)  # 상수
    u['isHoliday'] = bool(is_holiday)    # 상수

    # 시뮬레이션 실행 (출력은 parkingFee만 조회)
    res = simulate_fmu(
        filename=str(FMU_PATH),
        start_time=0.0,
        stop_time=float(exit_sec),
        output=['parkingFee'],
        input=u,
        output_interval=1.0,
        record_events=True
    )
    # 마지막 시점의 요금을 반환
    return float(res['parkingFee'][-1])

def main():
    # 시나리오 A: 평일 9분(540초) -> 0원
    fee_a = simulate_case(exit_sec=540, entry_sec=0, is_holiday=False)
    print(f"[A] Weekday 9 min -> {fee_a:.0f}원")

    # 시나리오 B: 평일 125분(7500초) -> 6000원
    fee_b = simulate_case(exit_sec=125*60, entry_sec=0, is_holiday=False)
    print(f"[B] Weekday 125 min -> {fee_b:.0f}원 ")

    # 시나리오 C: 공휴일 90분(5400초) -> 6000원
    fee_c = simulate_case(exit_sec=90*60, entry_sec=0, is_holiday=True)
    print(f"[C] Holiday 90 min -> {fee_c:.0f}원")

    # 시나리오 D: 입차>=출차 -> 0원
    fee_d = simulate_case(exit_sec=3600, entry_sec=4000, is_holiday=False)
    print(f"[D] entry>=exit -> {fee_d:.0f}원")

    # 간단 검증(필요 시 주석 해제)
    assert fee_a == 0.0, "A 실패"
    assert fee_b == 6000.0, "B 실패"
    assert fee_c == 6000.0, "C 실패"
    assert fee_d == 0.0, "D 실패"
    print("\n[OK] 모든 시나리오 예상대로 동작합니다.")

if __name__ == "__main__":
    main()
