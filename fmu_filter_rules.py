# fmu_filter_rules.py

import json


# ==============================================================================
# 유틸리티 함수 (파싱 및 디코딩)
# ==============================================================================

def _decode_str(val):
    """String 출력이 bytes/bytes literal로 올 때도 안전하게 str로 변환"""
    if isinstance(val, (bytes, bytearray)):
        try:
            return val.decode("utf-8", errors="ignore")
        except Exception:
            return str(val)
    if isinstance(val, str) and val.startswith("b'") and val.endswith("'"):
        return val[2:-1]
    return val


def read_string(ctx, var_name):
    """단일 String 변수 읽기(안전 디코드)"""
    vr = ctx["name_to_vr"].get(var_name)
    if vr is None:
        return None
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
    except Exception:
        return []


# ==============================================================================
# 핵심 필터링 함수
# ==============================================================================

def apply_filtering_logic(ctx_map, config):
    """
    Facility open 상태를 기준으로 Zone과 Space를 필터링하고 결과를 반환합니다.
    [수정] Zone 필터링 시 zone_isOpen==1 조건을 항상 적용합니다.
    """
    fac_ctx = ctx_map.get("Facility")
    zones_ctx = ctx_map.get("Zone")
    space_ctx = ctx_map.get("Space")

    results = {}

    # 1. Facility snapshot 읽기 & open 시설 집합
    facilities = read_json_list(fac_ctx, "facilities_snapshot_json") if fac_ctx else []

    open_facility_ids = {
        f.get("facility_thingId")
        for f in facilities
        if f.get("facility_isOpen") == 1
    }

    fac_open_list = [f for f in facilities if f.get("facility_isOpen") == 1]

    fac_open_json = json.dumps(fac_open_list, ensure_ascii=False)
    if len(fac_open_json) > config.TRIM:
        fac_open_json = fac_open_json[:config.TRIM] + " ... (truncated)"

    results["Facility"] = {
        "output_name": "facilities_snapshot_json (open only)",
        "value": fac_open_json
    }

    # 2. Zone snapshot 읽기 & facility 매칭
    zones = read_json_list(zones_ctx, "zones_snapshot_json") if zones_ctx else []

    # config.FILTER_ZONE_ISOPEN_ONLY 조건을 제거하고,
    # 항상 zone_isOpen == 1을 확인하도록 변경합니다.
    zones_filtered = [
        z for z in zones
        if z.get("zone_facilityId") in open_facility_ids
           and z.get("zone_isOpen") == 1  # <--- 항상 이 조건을 강제합니다.
    ]


    zone_ids = {z.get("zone_thingId") for z in zones_filtered if z.get("zone_thingId")}

    zones_json = json.dumps(zones_filtered, ensure_ascii=False)
    if len(zones_json) > config.TRIM:
        zones_json = zones_json[:config.TRIM] + " ... (truncated)"

    results["Zone"] = {
        "output_name": "zones_snapshot_json (filtered)",
        "value": zones_json
    }

    # 3. Space snapshot 읽기 & zone 매칭
    # (수정된 zone_ids 세트가 2단계에서 zone_isOpen==1인 것들만 포함하므로
    #  이 섹션은 수정 없이 그대로 둬도 요청대로 동작합니다.)
    spaces = read_json_list(space_ctx, "spaces_snapshot_json") if space_ctx else []
    spaces_filtered = [s for s in spaces if s.get("space_zoneId") in zone_ids]

    spaces_json = json.dumps(spaces_filtered, ensure_ascii=False)
    if len(spaces_json) > config.TRIM:
        spaces_json = spaces_json[:config.TRIM] + " ... (truncated)"

    results["Space"] = {
        "output_name": "spaces_snapshot_json (filtered)",
        "value": spaces_json
    }

    return results

def read_inout_event(ctx):
    """
    InOutEvent의 모든 변수를 디코딩하여 반환합니다.
    (필터링 없이 모든 출력 변수를 읽는 로직은 오케스트레이터의 유틸 함수로 남겨둡니다.)
    """
    slave = ctx["slave"]
    obt = ctx["outputs_by_type"]

    event_data = {}

    # String (디코드 적용)
    arr = obt.get("String", [])
    for sv in arr:
        val = slave.getString([sv.valueReference])[0]
        val = _decode_str(val)
        event_data[sv.name] = val

    # Integer & Enumeration
    for key in ("Integer", "Enumeration"):
        arr = obt.get(key, [])
        vrs = [sv.valueReference for sv in arr]
        if vrs:
            vals = slave.getInteger(vrs)
            for sv, v in zip(arr, vals):
                event_data[sv.name] = v

    # Boolean
    arr = obt.get("Boolean", [])
    vrs = [sv.valueReference for sv in arr]
    if vrs:
        vals = slave.getBoolean(vrs)
        for sv, v in zip(arr, vals):
            event_data[sv.name] = bool(v)

    # Real
    arr = obt.get("Real", [])
    vrs = [sv.valueReference for sv in arr]
    if vrs:
        vals = slave.getReal(vrs)
        for sv, v in zip(arr, vals):
            event_data[sv.name] = v

    return event_data