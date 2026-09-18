# main_orchestrator.py

import os
import time
import shutil
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

# 분리된 설정 및 로직 모듈 임포트
import fmu_config as config
import fmu_filter_rules as filter_rules

# ==============================================================================
# FMU 관련 유틸리티 함수
# ==============================================================================

def type_of(sv) -> str:
    """ModelVariable의 기본 타입명을 정확히 리턴"""
    return getattr(sv, 'type', 'Unknown')


def list_resources(unzipdir: config.Path):
    """FMU 내 리소스(주로 json, py 등) 간단 리스트"""
    res = (config.Path(unzipdir) / "resources")
    items = []
    if res.exists():
        for p in sorted(res.rglob("*")):
            rel = p.relative_to(unzipdir)
            if p.is_file():
                items.append(str(rel).replace("\\", "/"))
    return items


def build_vr_maps(md):
    """변수 이름 → valueReference / 타입 / 인덱스 등 맵 구성"""
    name_to_vr = {}
    outputs_by_type = {"String": [], "Integer": [], "Boolean": [], "Real": [], "Enumeration": []}
    params = []
    for sv in md.modelVariables:
        bt = type_of(sv)
        name_to_vr[sv.name] = sv.valueReference
        if getattr(sv, "causality", None) == "output":
            outputs_by_type.setdefault(bt, []).append(sv)
        if getattr(sv, "causality", None) == "parameter":
            params.append(sv)
    return name_to_vr, outputs_by_type, params


def open_fmu(label: str, path: config.Path):
    """FMU 로드/추출/슬레이브 인스턴스 생성 및 초기화"""
    if not path.exists():
        raise FileNotFoundError(f"{label} FMU 파일을 찾을 수 없습니다: {path}")

    md = read_model_description(str(path))
    unzipdir = config.Path(extract(str(path)))
    model_identifier = md.coSimulation.modelIdentifier

    slave = FMU2Slave(
        guid=md.guid,
        unzipDirectory=str(unzipdir),
        modelIdentifier=model_identifier,
        instanceName=f"{label}_instance",
    )

    slave.instantiate()
    slave.setupExperiment(startTime=0.0)

    name_to_vr, outputs_by_type, params = build_vr_maps(md)

    # 파라미터 주입 (SEED 적용)
    if "random_seed" in name_to_vr:
        slave.setInteger([name_to_vr["random_seed"]], [config.SEED])

    slave.enterInitializationMode()
    slave.exitInitializationMode()

    resources = list_resources(unzipdir)

    return {
        "label": label,
        "path": str(path),
        "md": md,
        "unzipdir": unzipdir,
        "slave": slave,
        "name_to_vr": name_to_vr,
        "outputs_by_type": outputs_by_type,
        "resources": resources,
        "t": 0.0,
    }


# ==============================================================================
# 메인 실행 루프
# ==============================================================================

def main():
    # === 1. 로드
    ctxs = []
    for label, path in config.FMU_PATHS.items():
        ctxs.append(open_fmu(label, path))

    ctx_map = {c["label"]: c for c in ctxs}

    # === 2. 스텝 루프
    for k in range(config.STEPS):
        t = k * config.DT
        print(f"\n[step={k:03d} | t={int(t)}s] **필터링된 결과**")

        # 2-1. 필터링 로직 실행 (fmu_filter_rules.py 호출)
        filtered_results = filter_rules.apply_filtering_logic(ctx_map, config)

        # 2-2. 결과 출력
        for label_key, result in filtered_results.items():
            print(f"[{config.LABEL_MAP[label_key]}]")
            print(f"    {result['output_name']}: {result['value']}\n")

        # 2-3. InOutEvent 정보 출력 (필터링 없이)
        inout_ctx = ctx_map.get("InOut")
        if inout_ctx:
            inout_data = filter_rules.read_inout_event(inout_ctx)
            print(f"[{config.LABEL_MAP['InOut']}]")
            for name, value in inout_data.items():
                # TRIM 적용
                if isinstance(value, str) and len(value) > config.TRIM:
                    value = value[:config.TRIM] + " ... (truncated)"
                print(f"    {name}: {value}")
            print("")

        # 2-4. 스텝 진행
        for c in ctxs:
            c["slave"].doStep(currentCommunicationPoint=t, communicationStepSize=config.DT)
            c["t"] += config.DT

        time.sleep(5)

    # === 3. 종료 처리
    for c in ctxs:
        try:
            c["slave"].terminate()
        except Exception:
            pass
        try:
            c["slave"].freeInstance()
        except Exception:
            pass
        shutil.rmtree(c["unzipdir"], ignore_errors=True)


if __name__ == "__main__":
    main()