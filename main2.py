# -*- coding: utf-8 -*-
"""
시나리오 기반 메인 오케스트레이터
- FacilityStatus.fmu, ZoneOccupancy.fmu, SpaceOccupancy.fmu, InOutEvent.fmu 로드
- 시나리오 (scenario.json) 파일을 읽어 규칙적으로 FMU 상태를 변경하며 시뮬레이션 진행
"""

import os
import json
import shutil
import random
from pathlib import Path
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

# ===== 사용자 설정 =====
BASE = Path("myfmu")  # FMU 기본 경로(프로젝트 규칙)
FMU_PATHS = {
    "Facility": BASE / "FacilityStatus.fmu",
    "Zone": BASE / "ZoneOccupancy.fmu",
    "Space": BASE / "SpaceOccupancy.fmu",
    "InOut": BASE / "InOutEvent.fmu",
}
SCENARIO_FILE = "scenario.json"  # 시나리오 규칙 파일
DT = 3600.0  # 1시간 스텝
STEPS = 5  # 총 스텝 수 (시나리오 실행을 위해 3에서 5로 증가)
SEED = 42  # 랜덤 시드
TRIM = 200  # 긴 문자열 출력 길이 제한

# SpaceOccupancy FMU의 상태 변경 입력 변수명 (가정)
SPACE_SET_VAR = "set_space_status"


# ======================

# --- 유틸리티 함수 (이전과 동일하게 유지) ---

def type_of(sv) -> str:
    """ModelVariable의 기본 타입명을 정확히 리턴"""
    return getattr(sv, 'type', 'Unknown')


def list_resources(unzipdir: Path):
    """FMU 내 리소스(주로 json, py 등) 간단 리스트"""
    # (내용 생략 - 변경 없음)
    res = (Path(unzipdir) / "resources")
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
        # 출력값 분류
        if getattr(sv, "causality", None) in ("output", "local"):
            if bt in outputs_by_type:
                outputs_by_type[bt].append(sv)
            else:
                outputs_by_type.setdefault(bt, []).append(sv)
        # 파라미터/입력 목록도 보관
        if getattr(sv, "causality", None) in ("parameter", "input"):
            params.append(sv)
    return name_to_vr, outputs_by_type, params


def open_fmu(label: str, path: Path):
    """FMU 로드/추출/슬레이브 인스턴스 생성 + 파라미터 주입 + 초기화"""
    if not path.exists():
        raise FileNotFoundError(f"{label} FMU 파일을 찾을 수 없습니다: {path}")

    md = read_model_description(str(path))
    unzipdir = Path(extract(str(path)))
    model_identifier = md.coSimulation.modelIdentifier

    slave = FMU2Slave(
        guid=md.guid,
        unzipDirectory=str(unzipdir),
        modelIdentifier=model_identifier,
        instanceName=f"{label}_instance",
    )

    slave.instantiate()
    slave.setupExperiment(startTime=0.0)

    slave.setupExperiment(startTime=0.0)

    # ---- 파라미터 주입 ----
    name_to_vr, outputs_by_type, params = build_vr_maps(md)

    # 공통: random_seed 있으면 설정
    if "random_seed" in name_to_vr:
        # random_seed 변수를 찾아 실제 타입을 확인합니다.
        seed_sv = next((sv for sv in md.modelVariables if sv.name == "random_seed"), None)

        if seed_sv:
            bt = type_of(seed_sv)
            vr = name_to_vr["random_seed"]

            print(f"    [INFO] Setting 'random_seed' (Type: {bt}, VR: {vr}) to {SEED}...")

            if bt == "Integer" or bt == "Enumeration":
                slave.setInteger([vr], [SEED])
            elif bt == "Real":
                slave.setReal([vr], [float(SEED)])
            elif bt == "String":
                slave.setString([vr], [str(SEED)])
            else:
                print(f"    [WARNING] Unknown type '{bt}' for 'random_seed'. Skipping set.")
        else:
            print("    [WARNING] 'random_seed' in name_to_vr but not in modelVariables list. Skipping set.")

    # ---- 초기화 ----
    slave.enterInitializationMode()
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


def read_all_outputs(ctx):
    """모든 출력 변수를 읽어 딕셔너리로 반환"""
    data = {}
    slave = ctx["slave"]
    obt = ctx["outputs_by_type"]

    for key, arr in obt.items():
        if not arr:
            continue
        vrs = [sv.valueReference for sv in arr]

        if key == "String":
            vals = slave.getString(vrs)
            for sv, v in zip(arr, vals):
                data[sv.name] = v.decode('utf-8') if isinstance(v, bytes) else v
        elif key in ("Integer", "Enumeration"):
            vals = slave.getInteger(vrs)
            for sv, v in zip(arr, vals):
                data[sv.name] = v
        elif key == "Boolean":
            vals = slave.getBoolean(vrs)
            for sv, v in zip(arr, vals):
                data[sv.name] = bool(v)
        elif key == "Real":
            vals = slave.getReal(vrs)
            for sv, v in zip(arr, vals):
                data[sv.name] = v
    return data


def print_step_output(label, outputs):
    """실제 값이 있는 변수만 간결하게 출력"""
    print(f"[{label}]")
    for name, val in outputs.items():
        if isinstance(val, str) and len(val) > TRIM:
            display_val = val[:TRIM] + " ... (truncated)"
        else:
            display_val = val
        print(f"    {name}: {display_val}")
    print("")


# --- 핵심 시나리오 실행 함수 ---

def execute_scenario_rule(ctxs, scenario_data):
    """
    시나리오 규칙을 실행하고 Space FMU의 상태를 변경합니다.
    """
    # 1. 현재 출력값 읽기
    inout_outputs = read_all_outputs(ctxs["InOut"])
    zone_outputs = read_all_outputs(ctxs["Zone"])
    space_outputs = read_all_outputs(ctxs["Space"])

    transaction_status = inout_outputs.get("transaction_status")

    if transaction_status is None:
        print("    [RULE SKIP]: InOutEvent의 transaction_status를 찾을 수 없습니다.")
        return

    print(f"    [RULE TRIGGERED]: transaction_status = {transaction_status}")

    # 2. Zone/Space 데이터 파싱
    try:
        zone_data = json.loads(zone_outputs.get("zones_snapshot_json", "[]"))
        space_data = json.loads(space_outputs.get("spaces_snapshot_json", "[]"))
    except json.JSONDecodeError:
        print("    [RULE ERROR]: Zone/Space JSON 데이터 파싱 실패.")
        return

    # 3. 목표 상태 설정
    # transaction_status = 0 (차량 나감 -> 비어있는 공간 찾기/설정)
    if transaction_status == 0:
        target_zone_isOpen = 1  # 비어있는 zone 찾기
        target_space_isOpen = 1  # 비어있는 space 찾기
        new_space_isOpen = 0  # 비어있지 않은 상태 (점유됨)으로 변경
        action_desc = "점유 (space_isOpen: 1 -> 0)"
    # transaction_status = 1 (차량 진입 -> 점유된 공간 찾기/해제)
    elif transaction_status == 1:
        target_zone_isOpen = 1  # 비어있는 zone 찾기
        target_space_isOpen = 0  # 점유된 space 찾기
        new_space_isOpen = 1  # 비어있는 상태 (해제됨)으로 변경
        action_desc = "해제 (space_isOpen: 0 -> 1)"
    else:
        print(f"    [RULE SKIP]: 알 수 없는 transaction_status 값 ({transaction_status}).")
        return

    # 4. 규칙에 맞는 space_thingId 찾기

    # 4-1. zone_isOpen = 1인 zonethingId 추출
    open_zones = {z["zone_thingId"] for z in zone_data if z.get("zone_isOpen") == target_zone_isOpen}

    # 4-2. 조건에 맞는 space 추출
    eligible_spaces = [
        s for s in space_data
        if s.get("zone_thingId") in open_zones and s.get("space_isOpen") == target_space_isOpen
    ]

    if not eligible_spaces:
        print(f"    [RULE RESULT]: {action_desc} 작업을 위한 조건에 맞는 공간을 찾지 못했습니다.")
        return

    # 5. 랜덤으로 하나 선택
    selected_space = random.choice(eligible_spaces)
    space_to_change = selected_space["space_thingId"]

    print(f"    [RULE ACTION]: Space '{space_to_change}'를 {action_desc} 상태로 변경합니다.")

    # 6. SpaceOccupancy FMU에 상태 변경 명령 주입
    space_ctx = ctxs["Space"]
    space_slave = space_ctx["slave"]
    space_vr = space_ctx["name_to_vr"].get(SPACE_SET_VAR)

    if space_vr is None:
        print(f"    [RULE ERROR]: Space FMU에 입력 변수 '{SPACE_SET_VAR}'가 없습니다. 상태 변경 불가.")
        return

    command = {
        "space_thingId": space_to_change,
        "space_isOpen": new_space_isOpen
    }

    space_slave.setString([space_vr], [json.dumps(command)])


def main():
    random.seed(SEED)

    # === FMU 로드 & 메타 수집
    ctxs_list = []
    for label, path in FMU_PATHS.items():
        ctxs_list.append(open_fmu(label, Path(path)))

    # 레이블 맵 및 컨텍스트 딕셔너리 생성
    ctxs = {c["label"]: c for c in ctxs_list}
    label_map = {
        "Facility": "FacilityStatus",
        "Zone": "ZoneOccupancy",
        "Space": "SpaceOccupancy",
        "InOut": "InOutEvent",
    }

    # === 시나리오 파일 로드 (현재는 사용하지 않지만 구조 유지를 위해 로드)
    # try:
    #     with open(SCENARIO_FILE, 'r', encoding='utf-8') as f:
    #         scenario_data = json.load(f)
    # except FileNotFoundError:
    #     print(f"경고: 시나리오 파일 '{SCENARIO_FILE}'을 찾을 수 없습니다. 규칙만 적용합니다.")
    scenario_data = {}  # 현재 시나리오는 파일 없이 규칙만 사용

    # === 스텝 루프
    for k in range(STEPS):
        t = k * DT
        print(f"\n=======================================================")
        print(f"[step={k:03d} | t={int(t)}s] (모든 FMU 출력값)")

        # 0. 이전 스텝의 상태 변경 명령 초기화 (필수)
        # 상태 변경 명령은 한 스텝만 유효해야 하므로, 매 스텝 시작 시 초기화
        space_ctx = ctxs["Space"]
        space_slave = space_ctx["slave"]
        space_vr = space_ctx["name_to_vr"].get(SPACE_SET_VAR)
        if space_vr is not None:
            space_slave.setString([space_vr], [""])  # 빈 문자열로 초기화

        # 1. 스텝 진행 (직전 스텝의 명령 반영)
        for c in ctxs_list:
            c["slave"].doStep(currentCommunicationPoint=t, communicationStepSize=DT)
            c["t"] += DT

        # 2. 각 FMU의 출력 읽기
        outputs = {}
        for c in ctxs_list:
            outputs[c["label"]] = read_all_outputs(c)
            label_str = label_map.get(c["label"], c["label"])
            print_step_output(label_str, outputs[c["label"]])

        # 3. 규칙 적용 (첫 번째 스텝(k=0)은 실행만 하고 규칙 적용 안 함)
        if k >= 1:
            print("\n-------------------------------------------------------")
            print(f"[step={k:03d} | SCENARIO RULE EXECUTION]")
            execute_scenario_rule(ctxs, scenario_data)

    print("=======================================================\n")

    # === 종료 처리
    for c in ctxs_list:
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