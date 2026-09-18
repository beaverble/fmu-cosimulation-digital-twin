# -*- coding: utf-8 -*-
"""
PaymentProcessor.fmu 검증 스크립트

시나리오:
 A) 카드(0), 요금 6000원, t=5 한 번만 결제 시도 (성공/실패 확률적)
 B) 모바일(1), 요금 6000원, t=3, t=9 두 번 결제 시도 (각각 확률적)
 C) 현금(2), 요금 6000원, t=4 한 번 결제 시도 (항상 성공)
 D) 트리거 홀드(현금, t=5~7 연속 True) → 상승엣지 1회만 성공 펄스 발생 확인
"""

from pathlib import Path
import numpy as np
from fmpy import simulate_fmu

FMU_PATH = Path("myfmu") / "PaymentProcessor.fmu"


# [수정 1]
def simulate_case(T, fee, pulses, method, hold_ranges=None, verbose=True):
    """
    T: 총 시뮬레이션 시간(초)
    fee: parkingFee 상수값
    pulses: 트리거가 True가 되는 '시점' 리스트(정수 초 단위)
    method: paymentMethod 상수값 (0:카드, 1:모바일, 2:현금)
    hold_ranges: [(start, end)] 형태로 True를 유지할 구간(포함형) 리스트. (옵션)
                 예) [(5,7)]면 t=5,6,7에서 True 유지
    """
    # 1초 간격 타임 벡터
    t = np.arange(0, T + 1, dtype=np.float64)  # 0..T

    # fmpy 입력 구조화 배열 (변수명은 FMU 변수와 동일해야 함)
    input_dtype = [
        ("time", np.float64),
        ("parkingFee", np.float64),
        ("trigger_PaymentAttempt", np.bool_),
        ("paymentMethod", np.int32),
    ]
    u = np.zeros(t.shape[0], dtype=input_dtype)
    u["time"] = t
    u["parkingFee"] = float(fee)
    u["paymentMethod"] = int(method)
    u["trigger_PaymentAttempt"] = False

    # 펄스 지정(한 스텝만 True)
    for pt in (pulses or []):
        if 0 <= pt <= T:
            u["trigger_PaymentAttempt"][int(pt)] = True

    # 홀드 구간 지정(옵션) - 상승엣지 동작 검증용
    if hold_ranges:
        for (s, e) in hold_ranges:
            s = max(0, int(s))
            e = min(T, int(e))
            if s <= e:
                u["trigger_PaymentAttempt"][s : e + 1] = True

    # 시뮬레이션 실행
    res = simulate_fmu(
        filename=str(FMU_PATH),
        start_time=0.0,
        stop_time=float(T),
        input=u,
        output=["isPaymentComplete"],
        output_interval=1.0,
        record_events=True,
    )

    # 결과 해석
    success_times = [int(tt) for tt, val in zip(t, res["isPaymentComplete"]) if bool(val)]

    # --- (로직 수정 지점) ---
    # '시도' 시간은 펄스뿐만 아니라 홀드 구간의 시작(상승엣지)도 포함해야 함
    raw_attempts = set(pulses or [])
    if hold_ranges:
        for (s, e) in hold_ranges:
            if s <= e:
                raw_attempts.add(s)  # 상승엣지가 발생하는 t=s 를 시도로 간주
    # --- (수정 끝) ---


    if verbose:
        print(f"\n=== 결과 요약 (method={method}, fee={fee}, T={T}) ===")
        print(f"- 결제 시도 시점(펄스/엣지): {sorted(list(raw_attempts))}") # 여기도 수정
        if hold_ranges:
            print(f"- 트리거 홀드 구간: {hold_ranges}")
        print(f"- 성공 펄스 시점:     {success_times or '없음'}")

        # 타임라인 간단 출력
        print("시간 | Attempt | Complete")
        for tt in range(0, T + 1):
            attempt = bool(u["trigger_PaymentAttempt"][tt])
            complete = bool(res["isPaymentComplete"][tt])
            mark = "✓" if complete else " "
            print(f"{tt:>3d}  |   {int(attempt)}     |    {mark}")

    return {
        "success_times": success_times,
        "attempt_times": sorted(list(raw_attempts)), # 수정된 시도 시간 반환
        "hold_ranges": hold_ranges or [],
    }


def assert_pulse_subset(attempt_pulse_times, success_pulse_times):
    """
    FMI 2.0 1스텝 관찰 지연을 고려하여 펄스를 검증합니다.
    성공 펄스가 시도 펄스보다 정확히 '1스텝 뒤에' 발생하는지 확인합니다.

    Args:
        attempt_pulse_times (list): 결제 시도를 'True'로 설정한 시간 스텝 리스트 (예: [5])
        success_pulse_times (list): isPaymentComplete가 'True'로 관찰된 시간 스텝 리스트 (예: [6])
    """

    # 1. 시도 펄스 시간(t)을 기반으로 '예상되는' 성공 펄스 시간(t+1) 세트를 만듭니다.
    # 예: 시도 시간이 [5, 10] 이라면, 예상 성공 시간은 {6, 11}이 됩니다.
    expected_success_times = {t + 1 for t in attempt_pulse_times}

    # 2. '실제로' 관찰된 성공 펄스 시간 세트를 만듭니다.
    actual_success_times = set(success_pulse_times)

    # 3. 검증:

    # 3-1. (오류 검증)
    # 실제 성공 리스트에 '예상한 시간' 외의 값이 있는지 확인합니다.
    # (시도도 없었는데 1스텝 뒤가 아닌, 엉뚱한 시간에 성공 펄스가 뜬 경우)
    extra_pulses = actual_success_times - expected_success_times
    assert not extra_pulses, f"시도(t) 대비 1스텝 뒤(t+1)가 아닌 시점에 성공 펄스 발생: {sorted(list(extra_pulses))}"

    # 3-2. (누락 검증)
    # '예상된 시간' 리스트에 '실제 성공'이 누락되었는지 확인합니다.
    # (시도를 했음에도 1스텝 뒤에 성공 펄스가 안 뜬 경우)
    missed_pulses = expected_success_times - actual_success_times
    assert not missed_pulses, f"시도(t) 후 1스텝 뒤(t+1)에 성공 펄스가 누락됨: {sorted(list(missed_pulses))}"

    print("--- 검증 통과: 1스텝 지연된 펄스 응답이 정상 확인되었습니다. ---")


# [수정 2]
def assert_hold_edge_only(prop):
    """홀드 구간에서는 1스텝 지연된 상승엣지 1회만 성공 펄스 검증"""
    if not prop["hold_ranges"]:
        return

    for (s, e) in prop["hold_ranges"]:
        # 1스텝 지연을 고려:
        # 시도(rising edge)가 t=s에 발생하면, 성공 펄스는 t=s+1에서 관찰됨
        expected_success_t = s + 1

        # 1. 예상된 성공 시점(t=s+1)에 펄스가 1회만 있는지 확인
        observed_count = prop["success_times"].count(expected_success_t)
        assert observed_count == 1, \
            f"홀드 시작(t={s}) 1스텝 뒤(t={expected_success_t})에 성공 펄스가 없거나({observed_count}개) 1회가 아님"

        # 2. 그 외 홀드 구간(t=s+2 ... e+1) 동안에는 추가 펄스가 없는지 확인
        extra_pulses = [t for t in prop["success_times"] if t != expected_success_t and (s < t <= e + 1)]
        assert not extra_pulses, f"홀드 지속 중 엉뚱한 추가 성공 펄스 발생: {extra_pulses}"


# [수정 3]
def main():
    # 시나리오 A: 카드(0), t=5 한 번 시도
    prop_a = simulate_case(T=10, fee=6000, pulses=[5], method=0)
    # (수정) 인자를 2개(시도 리스트, 성공 리스트)로 전달
    assert_pulse_subset(prop_a["attempt_times"], prop_a["success_times"])

    # 시나리오 B: 모바일(1), t=3 & t=9 두 번 시도
    prop_b = simulate_case(T=12, fee=6000, pulses=[3, 9], method=1)
    # (수정) 인자를 2개로 전달
    assert_pulse_subset(prop_b["attempt_times"], prop_b["success_times"])

    # 시나리오 C: 현금(2), t=4 한 번 시도
    prop_c = simulate_case(T=8, fee=6000, pulses=[4], method=2)
    # (수정) 인자를 2개로 전달
    assert_pulse_subset(prop_c["attempt_times"], prop_c["success_times"])

    # (수정) t=4 시도 -> t=5 성공을 검증 (1스텝 지연)
    assert 5 in prop_c["success_times"], "현금인데 t=4 시도 후 t=5에서 성공 펄스가 발생하지 않음"

    # 시나리오 D: 트리거 홀드(현금), t=5~7 연속 True
    prop_d = simulate_case(T=10, fee=6000, pulses=[], method=2, hold_ranges=[(5, 7)])
    # (수정) 인자를 2개로 전달 (simulate_case 수정으로 prop_d["attempt_times"]는 [5]가 됨)
    assert_pulse_subset(prop_d["attempt_times"], prop_d["success_times"])

    # (수정된 assert_hold_edge_only 함수가 t=5 시도 -> t=6 성공을 검증함)
    assert_hold_edge_only(prop_d)

    print("\n[OK] 모든 검증을 통과했습니다.")


if __name__ == "__main__":
    main()
