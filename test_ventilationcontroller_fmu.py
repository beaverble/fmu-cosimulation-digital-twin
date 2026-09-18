# ----------------------------------------------------------------------
# 테스트 스크립트 (별도 파일 권장): test_ventilation_controller.py
# ----------------------------------------------------------------------
# 아래는 fmpy.simulation.simulate_fmu()를 이용한 간단 검증 예시입니다.
# 사용 방법
#   1) 위 FMU를 빌드해 myfmu/VentilationController.fmu 생성
#   2) 아래 스크립트를 별도 파일(test_ventilation_controller.py)로 저장 후 실행
#
# 출력: fanSpeed 시간응답 및 일부 샘플 프린트

if __name__ == "__main__":
    # 선택적으로, 단일 파일에서 빠르게 함수 테스트할 수 있게 구성
    import numpy as np
    from fmpy import simulate_fmu
    from pathlib import Path

    fmu_path = Path("myfmu") / "VentilationController.fmu"

    # 0~300초, 1초 간격
    t0, t1, dt = 0.0, 300.0, 1.0
    times = np.arange(t0, t1 + dt, dt)

    # CO 입력: 30 ppm에서 시작하여 완만히 증가(임의 시나리오)
    co_input = 30.0 + 0.7 * times  # 50ppm을 지나 200ppm까지 도달하도록

    # simulate_fmu용 구조화 배열 생성 (변수명은 FMU 입력명과 동일해야 함)
    u = np.zeros(times.shape[0], dtype=[('time', np.float64), ('coLevel_ppm', np.float64)])
    u['time'] = times
    u['coLevel_ppm'] = co_input

    # 파라미터 시작값 (필요 시 조정)
    start_values = {
        'safeThreshold_ppm': 50.0,
        'maxThreshold_ppm': 200.0,
    }

    result = simulate_fmu(
        filename=str(fmu_path),
        start_time=float(t0),
        stop_time=float(t1),
        input=u,
        start_values=start_values,
        output=['fanSpeed'],
        output_interval=float(dt),
        record_events=True,
        validate=True,
        initialize=True,
        terminate=True,
    )

    fs = result['fanSpeed']
    N = len(times)
    print("[1분간격요약]")
    for i in range(0, N, 60):
        print(f"t={times[i]:.0f}s, CO={co_input[i]:.1f} ppm -> fanSpeed={fs[i]:.3f}")