# -*- coding: utf-8 -*-
"""
메인 오케스트레이터(출력 점검용)
- FacilityStatus.fmu, ZoneOccupancy.fmu, SpaceOccupancy.fmu, InOutEvent.fmu 를 한 번에 로드
- 타입 인식: sv.type 기반 ('Real'/'Integer'/'Boolean'/'String'/'Enumeration')
- 파라미터 주입은 enterInitializationMode() 이전에 수행
- 각 스텝마다 모든 FMU 출력값을 타입에 맞게 읽어 표시
- FMU 리소스(동봉된 json/py 등) 간단 점검 출력
"""

import os
import json
import shutil
from pathlib import Path
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

# ===== 사용자 설정 =====
BASE = Path("myfmu")  # FMU 기본 경로(프로젝트 규칙)
FMU_PATHS = {
    "Facility":  BASE / "FacilityStatus.fmu",
    "Zone":      BASE / "ZoneOccupancy.fmu",
    "Space":     BASE / "SpaceOccupancy.fmu",
    "InOut":     BASE / "InOutEvent.fmu",
}

DT = 3600.0     # 1시간 스텝
STEPS = 3       # 총 스텝 수
SEED = 42       # 랜덤 시드(해당 FMU가 지원할 때만 사용)
TRIM = 200      # 긴 문자열 출력 길이 제한
# ======================


def type_of(sv) -> str:
    """ModelVariable의 기본 타입명을 정확히 리턴"""
    # sv.type 속성 자체가 'Real', 'Integer', 'String' 등의 문자열입니다.
    return getattr(sv, 'type', 'Unknown')


def list_resources(unzipdir: Path):
    """FMU 내 리소스(주로 json, py 등) 간단 리스트"""
    res = (Path(unzipdir) / "resources")
    items = []
    if res.exists():
        for p in sorted(res.rglob("*")):
            rel = p.relative_to(unzipdir)
            # 최상위/리소스 경로만 보기 좋게
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
        # 출력값 분류
        if getattr(sv, "causality", None) == "output":
            if bt in outputs_by_type:
                outputs_by_type[bt].append(sv)
            else:
                # 혹시 모르는 타입은 문자열로 취급하지 말고 따로 둔다
                outputs_by_type.setdefault(bt, []).append(sv)
        # 파라미터 목록도 보관(요약표용)
        if getattr(sv, "causality", None) == "parameter":
            params.append(sv)
    return name_to_vr, outputs_by_type, params


def print_var_table(name, md):
    """변수 테이블 요약"""
    print(f"[{name}]")
    print("  name | type | causality")
    for sv in md.modelVariables:
        print(f"  {sv.name} | {type_of(sv)} | {sv.causality}")
    print("")


def print_fmu_resources_banner(fmu_labels):
    print("=== FMU resources 점검 ===")
    for label, z in fmu_labels:
        print(f"[{label}] {z['path']}")
        for s in z['resources'][:200]:  # 너무 길면 생략
            print(f"  - {s}")
    print("==========================\n")


def print_var_table_banner(metas):
    print("\n=== 변수 테이블 요약 ===")
    for label, z in metas:
        print(f"[{label}]")
        print("  name | type | causality")
        for sv in z["md"].modelVariables:
            print(f"  {sv.name} | {type_of(sv)} | {sv.causality}")
        print("")
    print("========================\n")


def open_fmu(label: str, path: Path):
    """FMU 로드/추출/슬레이브 인스턴스 생성 + 파라미터 주입 + 초기화"""
    if not path.exists():
        raise FileNotFoundError(f"{label} FMU 파일을 찾을 수 없습니다: {path}")

    md = read_model_description(str(path))
    unzipdir = Path(extract(str(path)))
    model_identifier = md.coSimulation.modelIdentifier  # Co-Simulation 전제

    slave = FMU2Slave(
        guid=md.guid,
        unzipDirectory=str(unzipdir),
        modelIdentifier=model_identifier,
        instanceName=f"{label}_instance",
    )

    slave.instantiate()
    slave.setupExperiment(startTime=0.0)

    # ---- 파라미터 주입 (enterInitializationMode 이전) ----
    name_to_vr, outputs_by_type, params = build_vr_maps(md)

    # 공통: random_seed 있으면 설정
    if "random_seed" in name_to_vr:
        slave.setInteger([name_to_vr["random_seed"]], [SEED])


    # (필요시 여기에 다른 FMU의 파라미터들도 추가로 매핑)
    # 예: if label=="Zone" and "zone_json" in name_to_vr: ... 등

    # ---- 초기화 ----
    slave.enterInitializationMode()
    slave.exitInitializationMode()

    # 리소스 목록/메타 반환
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


def read_and_print_all(label, ctx):
    """출력 변수 전부 읽어서 FMU별로 간결하게 출력"""
    slave = ctx["slave"]
    obt = ctx["outputs_by_type"]

    # FMU 헤더 라벨은 다시 출력
    print(f"[{label}]")

    # 문자열
    arr = obt.get("String", [])
    # (주석 처리) 타입별 요약 헤더는 출력하지 않음
    # print("  [String] {} vars".format(len(arr)))
    if arr:
        for sv in arr:
            val = slave.getString([sv.valueReference])[0]
            if isinstance(val, str) and len(val) > TRIM:
                val = val[:TRIM] + " ... (truncated)"
            # (수정) 들여쓰기 유지
            print(f"    {sv.name}: {val}")
    # (주석 처리) (none)은 출력하지 않음
    # else:
    #     print("    (none)")

    # 정수(Enumeration 포함)
    for key in ("Integer", "Enumeration"):
        arr = obt.get(key, [])
        # (주석 처리) 타입별 요약 헤더는 출력하지 않음
        # print(f"  [{key:9s}] {len(arr)}")
        if arr:
            vrs = [sv.valueReference for sv in arr]
            vals = slave.getInteger(vrs)
            for sv, v in zip(arr, vals):
                # (수정) 들여쓰기 유지
                print(f"    {sv.name}: {v}")
        # (주석 처리) (none)은 출력하지 않음
        # else:
        #     print("    (none)")

    # Boolean
    arr = obt.get("Boolean", [])
    # (주석 처리) 타입별 요약 헤더는 출력하지 않음
    # print("  [Boolean] {} vars".format(len(arr)))
    if arr:
        vrs = [sv.valueReference for sv in arr]
        vals = slave.getBoolean(vrs)
        for sv, v in zip(arr, vals):
            # (수정) 들여쓰기 유지
            print(f"    {sv.name}: {bool(v)}")
    # (주석 처리) (none)은 출력하지 않음
    # else:
    #     print("    (none)")

    # Real
    arr = obt.get("Real", [])
    # (주석 처리) 타입별 요약 헤더는 출력하지 않음
    # print("  [Real] {} vars".format(len(arr)))
    if arr:
        vrs = [sv.valueReference for sv in arr]
        vals = slave.getReal(vrs)
        for sv, v in zip(arr, vals):
            # (수정) 들여쓰기 유지
            print(f"    {sv.name}: {v}")
    # (주석 처리) (none)은 출력하지 않음
    # else:
    #     print("    (none)")

    # (수정) FMU 간 구분을 위한 공백 라인 다시 추가
    print("")


def main():
    # === 로드 & 리소스/메타 수집
    ctxs = []
    for label, path in FMU_PATHS.items():
        ctxs.append(open_fmu(label, Path(path)))

    # === 스텝 루프
    for k in range(STEPS):
        t = k * DT
        print(f"\n[step={k:03d} | t={int(t)}s] (모든 변수값)")

        # 각 FMU의 출력 읽기
        for c in ctxs:
            label_map = {
                "Facility": "FacilityStatus",
                "Zone": "ZoneOccupancy",
                "Space": "SpaceOccupancy",
                "InOut": "InOutEvent",
            }

            # c["label"]을 기반으로 최종 출력 이름을 가져옵니다.
            label_str = label_map.get(c["label"], c["label"])

            read_and_print_all(label_str, c)

        # 스텝 진행
        for c in ctxs:
            c["slave"].doStep(currentCommunicationPoint=t, communicationStepSize=DT)
            c["t"] += DT

    # === 종료 처리
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

