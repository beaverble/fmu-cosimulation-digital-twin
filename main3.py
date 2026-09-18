# -*- coding: utf-8 -*-
"""
메인 오케스트레이터(필터링 출력)
- Facility_isOpen==1인 facility_thingId와 zone_facilityId 일치 구간만 출력
- 그 존들에 속한 space만 출력
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

}

DT = 3600.0     # 1시간 스텝
STEPS = 3       # 총 스텝 수
SEED = 2       # 랜덤 시드(해당 FMU가 지원할 때만 사용)
TRIM = 200      # 긴 문자열 출력 길이 제한

# (옵션) 존도 isOpen==1 인 것만 보고 싶으면 True (이전 질문에서 제공했던 기본 값 유지)
FILTER_ZONE_ISOPEN_ONLY = False  # 모든 Zone을 검토하도록 False로 설정 (선택사항)
# ======================


def type_of(sv) -> str:
    return getattr(sv, 'type', 'Unknown')


def list_resources(unzipdir: Path):
    res = (Path(unzipdir) / "resources")
    items = []
    if res.exists():
        for p in sorted(res.rglob("*")):
            rel = p.relative_to(unzipdir)
            if p.is_file():
                items.append(str(rel).replace("\\", "/"))
    return items


def build_vr_maps(md):
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


def open_fmu(label: str, path: Path):
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

    name_to_vr, outputs_by_type, params = build_vr_maps(md)



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


def _decode_str(val):
    """String 출력이 bytes/bytes literal로 올 때도 안전하게 str로 변환"""
    # 1. bytes/bytearray인 경우 (fmi2.getString의 기본 결과)
    if isinstance(val, (bytes, bytearray)):
        try:
            return val.decode("utf-8", errors="ignore")
        except Exception:
            return str(val)
    # 2. b'...' 형태의 str literal인 경우 (출력값 자체가 string literal인 경우)
    if isinstance(val, str) and val.startswith("b'") and val.endswith("'"):
        # b'' 제거 후 문자열로 반환
        return val[2:-1]
    return val


def read_string(ctx, var_name):
    """단일 String 변수 읽기(안전 디코드)"""
    vr = ctx["name_to_vr"].get(var_name)
    if vr is None:
        return None
    # getString은 bytes를 리턴할 수 있으므로, _decode_str로 처리
    v = ctx["slave"].getString([vr])[0]
    return _decode_str(v)


def read_json_list(ctx, var_name):
    """JSON 배열(String) 읽어 파싱해 list 반환. 실패시 []"""
    s = read_string(ctx, var_name)
    if s is None:
        return []
    s = s.strip()
    try:
        data = json.loads(s)
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        # print(f"Warning: JSON decoding failed for {var_name}: {e} / Raw: {s[:50]}...")
        return []


def read_and_print_all(label, ctx):
    """(InOutEvent용) 모든 출력 변수를 원형대로 출력하되 디코드 개선 적용"""
    slave = ctx["slave"]
    obt = ctx["outputs_by_type"]

    # InOutEvent는 원본 그대로 출력하는 것을 유지
    print(f"[{label}]")

    # String (디코드 적용)
    arr = obt.get("String", [])
    if arr:
        for sv in arr:
            val = slave.getString([sv.valueReference])[0]
            val = _decode_str(val) # 디코드 적용
            if isinstance(val, str) and len(val) > TRIM:
                val = val[:TRIM] + " ... (truncated)"
            print(f"    {sv.name}: {val}")

    # Integer & Enumeration
    for key in ("Integer", "Enumeration"):
        arr = obt.get(key, [])
        if arr:
            vrs = [sv.valueReference for sv in arr]
            vals = slave.getInteger(vrs)
            for sv, v in zip(arr, vals):
                print(f"    {sv.name}: {v}")

    # Boolean
    arr = obt.get("Boolean", [])
    if arr:
        vrs = [sv.valueReference for sv in arr]
        vals = slave.getBoolean(vrs)
        for sv, v in zip(arr, vals):
            print(f"    {sv.name}: {bool(v)}")

    # Real
    arr = obt.get("Real", [])
    if arr:
        vrs = [sv.valueReference for sv in arr]
        vals = slave.getReal(vrs)
        for sv, v in zip(arr, vals):
            print(f"    {sv.name}: {v}")

    print("")


def main():
    # === 로드
    ctxs = []
    for label, path in FMU_PATHS.items():
        ctxs.append(open_fmu(label, Path(path)))

    # 라벨 → 컨텍스트 맵
    ctx_map = {c["label"]: c for c in ctxs}

    # FMU 이름 매핑 (출력용)
    label_map = {
        "Facility": "FacilityStatus",
        "Zone": "ZoneOccupancy",
        "Space": "SpaceOccupancy",
        "InOut": "InOutEvent",
    }

    for k in range(STEPS):
        t = k * DT
        print(f"\n[step={k:03d} | t={int(t)}s] **필터링된 결과**")

        # 1) Facility snapshot 읽기 & open 시설 집합
        fac_ctx = ctx_map.get("Facility")
        zones_ctx = ctx_map.get("Zone")
        space_ctx = ctx_map.get("Space")
        inout_ctx = ctx_map.get("InOut")

        facilities = read_json_list(fac_ctx, "facilities_snapshot_json") if fac_ctx else []
        # Facility_isOpen==1인 facility_thingId 수집
        open_facility_ids = {
            f.get("facility_thingId")
            for f in facilities
            if f.get("facility_isOpen") == 1
        }

        print(f"[{label_map['Facility']}]")
        fac_open_list = [f for f in facilities if f.get("facility_isOpen") == 1]
        fac_open_json = json.dumps(fac_open_list, ensure_ascii=False)
        if len(fac_open_json) > TRIM:
            fac_open_json = fac_open_json[:TRIM] + " ... (truncated)"
        print(f"    facilities_snapshot_json (open only): {fac_open_json}\n")

        # 2) Zone snapshot 읽기 & facility 매칭(옵션으로 zone_isOpen==1 필터)
        zones = read_json_list(zones_ctx, "zones_snapshot_json") if zones_ctx else []
        zones_filtered = [
            z for z in zones
            # Facility ID 일치
            if z.get("zone_facilityId") in open_facility_ids
               # (옵션) Zone의 isOpen 필터 적용
               and (z.get("zone_isOpen") == 1 if FILTER_ZONE_ISOPEN_ONLY else True)
        ]
        zone_ids = {z.get("zone_thingId") for z in zones_filtered if z.get("zone_thingId")}

        print(f"[{label_map['Zone']}]")
        zones_json = json.dumps(zones_filtered, ensure_ascii=False)
        if len(zones_json) > TRIM:
            zones_json = zones_json[:TRIM] + " ... (truncated)"
        print(f"    zones_snapshot_json (filtered): {zones_json}\n")

        # 3) Space snapshot 읽기 & zone 매칭
        spaces = read_json_list(space_ctx, "spaces_snapshot_json") if space_ctx else []
        spaces_filtered = [s for s in spaces if s.get("space_zoneId") in zone_ids]

        print(f"[{label_map['Space']}]")
        spaces_json = json.dumps(spaces_filtered, ensure_ascii=False)
        if len(spaces_json) > TRIM:
            spaces_json = spaces_json[:TRIM] + " ... (truncated)"
        print(f"    spaces_snapshot_json (filtered): {spaces_json}\n")

        # 4) InOutEvent는 원본 그대로 참고 출력 (디코드 개선 포함)
        if inout_ctx:
            read_and_print_all(label_map['InOut'], inout_ctx)

        # === doStep
        for c in ctxs:
            c["slave"].doStep(currentCommunicationPoint=t, communicationStepSize=DT)
            c["t"] += DT

    # === 종료
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