# -*- coding: utf-8 -*-
"""
테스트 오케스트레이터: myfmu/PaymentInput.fmu
- 수정된 PaymentInput FMU를 테스트합니다.
- 'paymentMethod'가 고정되는지, 'trigger_PaymentAttempt'가 단 한 번 발생하는지 확인합니다.
"""

from fmpy import simulate_fmu, read_model_description
import os

# --- 1. 설정 ---
# 빌드된 FMU 파일 경로
fmu_filename = 'myfmu/PaymentInput.fmu'
start_time = 0.0
stop_time = 10.0
step_size = 0.1  # 0.1초 간격으로 FMU 상태 확인

# FMU로부터 값을 읽어올 변수 목록
output_vars = ['paymentMethod', 'trigger_PaymentAttempt']

# --- 2. FMU 파일 존재 확인 ---
if not os.path.exists(fmu_filename):
    print(f"오류: '{fmu_filename}' 파일을 찾을 수 없습니다.")
    print("먼저 'paymentinputfmu.py'를 수정하고 'pythonfmu build -f paymentinputfmu.py -d myfmu'로")
    print("빌드했는지 확인하세요.")
else:
    print(f"'{fmu_filename}' 테스트를 시작합니다...")

    # --- 3. 모델 정보 읽기 (확인용) ---
    try:
        model_info = read_model_description(fmu_filename)
        print("FMU 모델 정보 로드 성공.")
        print(f"(ModelIdentifier: {model_info.modelIdentifier})")

        print("--- 모델 변수 (Output) ---")
        for var in model_info.modelVariables:
            if var.causality == 'output':
                print(f"- {var.name} ({var.type}, desc: {var.description})")
        print("--------------------------")

        # --- 4. 시뮬레이션 실행 ---
        # simulate_fmu가 FMU 로드, 초기화(setup_experiment),
        # do_step 반복, 종료(terminate)를 모두 자동으로 처리합니다.
        result = simulate_fmu(
            filename=fmu_filename,
            start_time=start_time,
            stop_time=stop_time,
            step_size=step_size,
            output=output_vars,  # 기록할 변수 지정
            # FMU가 print()로 찍는 로그를 터미널에 실시간 표시
            #fmi_call_logger=lambda call: print(f"[FMU] {call}")
        )

        print("\n시뮬레이션 완료. 결과 분석:")

        # --- 5. 결과 텍스트로 분석 ---

        # 'trigger_PaymentAttempt'가 True인 시점만 필터링
        print("\n=== 결제 시도 (trigger_PaymentAttempt == True) 발생 시점 ===")
        triggered_count = 0
        fixed_payment_method = -1

        # 0.0초 시점의 값 (초기화 직후)
        if len(result['time']) > 0:
            fixed_payment_method = result['paymentMethod'][0]

        for i in range(len(result['time'])):
            if result['trigger_PaymentAttempt'][i]:
                triggered_count += 1
                print(f"  > [발견] 시간: {result['time'][i]:.1f}초, "
                      f"결제 방식(paymentMethod): {result['paymentMethod'][i]}")

        if triggered_count == 0:
            print("  (결제 시도 이벤트가 발생하지 않았습니다. 'delay' 값이 10초보다 컸을 수 있습니다.)")
        elif triggered_count > 1:
            print(f"  [경고!] 이벤트가 {triggered_count}번 발생했습니다. (로직 확인 필요)")

        # paymentMethod가 고정되었는지 확인
       # print("\n=== 결제 방식(paymentMethod) 고정 확인 ===")
        #print(f"  - 0.0초 시점(초기화 직후) 결제 방식: {fixed_payment_method}")

        is_fixed = True
        for method_val in result['paymentMethod']:
            if method_val != fixed_payment_method:
                is_fixed = False
                print(f"  - [경고!] 시뮬레이션 중 값이 {method_val} (으)로 변경되었습니다.")
                break

        if is_fixed:
            print(f"  - (확인) 시뮬레이션 내내 {fixed_payment_method} 값으로 고정되었습니다.")

    except Exception as e:
        print(f"FMU 시뮬레이션 중 오류 발생: {e}")