# orchestrator_fmu_runner.py
# FMU들을 순차 스텝으로 실행하고 각 스텝별 출력(output)을 보기 좋게 찍어주는 오케스트레이터
# 기본 경로는 'myfmu/' 를 사용합니다.

import os
import sys
import math
import shutil
import tempfile
from typing import Dict, List, Tuple

from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

# =========================
# 유틸 함수
# =========================

def _platform_bin():
    if sys.platform.startswith("linux"):   return "linux64", ".so"
    if sys.platform == "darwin":           return "darwin64", ".dylib"
    return "win64", ".dll"


def _sv_basetype(sv) -> str:
    """ScalarVariable 의 베이스 타입을 문자열로 반환(Real/Integer/Boolean/String/Enumeration).
    fmpy의 ScalarVariable은 real/integer/boolean/string/enumeration 중 하나의 필드를 가짐.
    """
    if getattr(sv, 'real', None) is not None:         return 'Real'
    if getattr(sv, 'integer', None) is not None:      return 'Integer'
    if getattr(sv, 'boolean', None) is not None:      return 'Boolean'
    if getattr(sv, 'string', None) is not None:       return 'String'
    if getattr(sv, 'enumeration', None) is not None:  return 'Enumeration'
    return 'Unknown'


def _collect_vars(md):
    """모든 변수의 name -> (vr, type, causality) 맵 구성"""
    name2meta = {}
    for sv in md.modelVariables:
        name2meta[sv.name] = (sv.valueReference, _sv_basetype(sv), sv.causality)
    return name2meta


def _filter_vars(name2meta: Dict[str, Tuple[int, str, str]], causality: str = None, baseType: str = None) -> Dict[str, Tuple[int, str, str]]:
    out = {}
    for n, (vr, tp, cs) in name2meta.items():
        if causality and cs != causality:
            continue
        if baseType and tp != baseType:
            continue
        out[n] = (vr, tp, cs)
    return out


def _values_by_type(fmu: FMU2Slave, vars_map: Dict[str, Tuple[int, str, str]]) -> Dict[str, object]:
    """주어진 변수 맵(보통 outputs)을 타입별 getXXX로 읽어서 name->value 반환"""
    by_type: Dict[str, List[Tuple[str, int]]] = {"Real": [], "Integer": [], "Boolean": [], "String": [], "Enumeration": []}
    for name, (vr, tp, _cs) in vars_map.items():
        by_type.setdefault(tp, []).append((name, vr))

    result: Dict[str, object] = {}
    # Real
    if by_type.get("Real"):
        vrs = [vr for _n, vr in by_type["Real"]]
        vals = fmu.getReal(vrs)
        for (n, _vr), val in zip(by_type["Real"], vals):
            result[n] = float(val)
    # Integer / Enumeration -> 정수로 처리
    for t in ("Integer", "Enumeration"):
        if by_type.get(t):
            vrs = [vr for _n, vr in by_type[t]]
            vals = fmu.getInteger(vrs)
            for (n, _vr), val in zip(by_type[t], vals):
                result[n] = int(val)
    # Boolean
    if by_type.get("Boolean"):
        vrs = [vr for _n, vr in by_type["Boolean"]]
        vals = fmu.getBoolean(vrs)
        for (n, _vr), val in zip(by_type["Boolean"], vals):
            result[n] = bool(val)
    # String
    if by_type.get("String"):
        vrs = [vr for _n, vr in by_type["String"]]
        vals = fmu.getString(vrs)
        for (n, _vr), val in zip(by_type["String"], vals):
            result[n] = str(val)

    return result


def _set_inputs(fmu: FMU2Slave, name2meta: Dict[str, Tuple[int, str, str]], values: Dict[str, object]):
    """입력 변수에 값을 세팅(타입에 맞춰 setXXX 사용). values는 name->value."""
    # 타입별로 모아서 한 번에 set
    buckets: Dict[str, List[Tuple[int, object]]] = {"Real": [], "Integer": [], "Boolean": [], "String": [], "Enumeration": []}
    for name, val in values.items():
        meta = name2meta.get(name)
        if not meta:
            continue
        vr, tp, cs = meta
        if cs != 'input':
            continue
        buckets.setdefault(tp, []).append((vr, val))

    if buckets["Real"]:
        fmu.setReal([vr for vr, _ in buckets["Real"]], [float(v) for _vr, v in buckets["Real"]])
    if buckets["Integer"] or buckets["Enumeration"]:
        ints = buckets["Integer"] + buckets["Enumeration"]
        if ints:
            fmu.setInteger([vr for vr, _ in ints], [int(v) for _vr, v in ints])
    if buckets["Boolean"]:
        fmu.setBoolean([vr for vr, _ in buckets["Boolean"]], [bool(v) for _vr, v in buckets["Boolean"]])
    if buckets["String"]:
        fmu.setString([vr for vr, _ in buckets["String"]], [str(v) for _vr, v in buckets["String"]])


def _pretty_kv_line(name: str, val: object) -> str:
    if isinstance(val, str):
        s = val.replace('\n', ' ')
        # JSON 스냅샷 같은 긴 문자열은 앞부분만 미리보기
        if len(s) > 140:
            s = s[:140] + '...'
        return f"  - {name} = \"{s}\""
    return f"  - {name} = {val}"


# =========================
# FMU 로딩/수명주기
# =========================
class LoadedFMU:
    def __init__(self, name: str, fmu_path: str):
        self.name = name
        self.fmu_path = fmu_path
        self.unzipdir = None
        self.md = None
        self.fmu: FMU2Slave = None
        self.vars: Dict[str, Tuple[int, str, str]] = {}
        self.inputs: Dict[str, Tuple[int, str, str]] = {}
        self.outputs: Dict[str, Tuple[int, str, str]] = {}

    def load(self):
        self.md = read_model_description(self.fmu_path)
        self.unzipdir = extract(self.fmu_path)
        platform, _ext = _platform_bin()
        model_id = self.md.coSimulation.modelIdentifier
        self.fmu = FMU2Slave(guid=self.md.guid,
                             unzipDirectory=self.unzipdir,
                             modelIdentifier=model_id,
                             instanceName=self.name,
                             fmiCallLogger=None)
        self.fmu.instantiate()
        self.fmu.setupExperiment(startTime=0.0)
        self.fmu.enterInitializationMode()
        self.fmu.exitInitializationMode()
        self.vars = _collect_vars(self.md)
        self.inputs = _filter_vars(self.vars, causality='input')
        self.outputs = _filter_vars(self.vars, causality='output')

    def step(self, t: float, dt: float):
        ok = self.fmu.doStep(currentCommunicationPoint=t, communicationStepSize=dt)
        if not ok:
            raise RuntimeError(f"doStep failed in {self.name} at t={t}")

    def read_outputs(self) -> Dict[str, object]:
        return _values_by_type(self.fmu, self.outputs)

    def set_inputs(self, values: Dict[str, object]):
        return _set_inputs(self.fmu, self.vars, values)

    def terminate(self):
        try:
            if self.fmu is not None:
                self.fmu.terminate()
                self.fmu.freeInstance()
        finally:
            if self.unzipdir and os.path.isdir(self.unzipdir):
                shutil.rmtree(self.unzipdir, ignore_errors=True)


# =========================
# 오케스트레이터 본체
# =========================

def run_orchestrator(
    facility_fmu: str = 'myfmu/FacilityStatus.fmu',
    zone_fmu: str = 'myfmu/ZoneOccupancy.fmu',
    space_fmu: str = 'myfmu/SpaceOccupancy.fmu',
    entry_fmu: str = 'myfmu/EntryExitEvent.fmu',
    stop_time: float = 10.0,
    step_size: float = 1.0
):
    """
    1~4개의 FMU를 순환 실행하며, 각 스텝마다 output을 출력.
    - Facility -> Zone -> Space -> Entry 순으로 실행하며, 이름이 일치하는 입력은 자동으로 전달(예: facility_isOpen 등).
    - FMU가 존재하지 않으면 해당 단계는 건너뜀.
    """
    modules: List[LoadedFMU] = []

    def _maybe_load(title: str, path: str) -> LoadedFMU:
        if path and os.path.isfile(path):
            m = LoadedFMU(title, path)
            m.load()
            print(f"[LOAD] {title} from {path}")
            return m
        return None

    fac = _maybe_load('Facility', facility_fmu)
    zon = _maybe_load('Zone', zone_fmu)
    spa = _maybe_load('Space', space_fmu)
    ent = _maybe_load('Entry', entry_fmu)

    for m in (fac, zon, spa, ent):
        if m: modules.append(m)

    if not modules:
        print("로드된 FMU가 없습니다. 경로를 확인하세요.")
        return

    t = 0.0
    k = 0
    try:
        while t <= stop_time + 1e-12:
            print(f"\n[step={k:03d} | t={int(t)}s]")

            fac_out = {}
            zon_out = {}
            spa_out = {}
            ent_out = {}

            # 1) Facility
            if fac:
                fac.step(t, step_size)
                fac_out = fac.read_outputs()
                if fac_out:
                    print("[Facility outputs]")
                    for n, v in sorted(fac_out.items()):
                        print(_pretty_kv_line(n, v))

            # 2) Zone (Facility -> Zone 입력 전달 시도)
            if zon:
                if fac_out:
                    pass_down = {}
                    for key in ("facility_isOpen", "facility_thingId", "facilityId", "facility_health"):
                        if key in fac_out and key in zon.inputs:
                            pass_down[key] = fac_out[key]
                    if pass_down:
                        zon.set_inputs(pass_down)
                zon.step(t, step_size)
                zon_out = zon.read_outputs()
                if zon_out:
                    print("[Zone outputs]")
                    for n, v in sorted(zon_out.items()):
                        print(_pretty_kv_line(n, v))

            # 3) Space (Zone -> Space 입력 전달 시도)
            if spa:
                pass_down = {}
                for key in ("zone_isOpen", "zone_thingId", "zone_facilityId"):
                    if key in zon_out and key in spa.inputs:
                        pass_down[key] = zon_out[key]
                for key in ("facility_isOpen", "facility_thingId"):
                    if key in fac_out and key in spa.inputs:
                        pass_down[key] = fac_out[key]
                if pass_down:
                    spa.set_inputs(pass_down)
                spa.step(t, step_size)
                spa_out = spa.read_outputs()
                if spa_out:
                    print("[Space outputs]")
                    for n, v in sorted(spa_out.items()):
                        print(_pretty_kv_line(n, v))

            # 4) Entry/Exit Event (Space/Zone/Facility -> Entry 전달 시도)
            if ent:
                pass_down = {}
                for src in (fac_out, zon_out, spa_out):
                    for key, val in src.items():
                        if key in ent.inputs:
                            pass_down[key] = val
                if pass_down:
                    ent.set_inputs(pass_down)
                ent.step(t, step_size)
                ent_out = ent.read_outputs()
                if ent_out:
                    print("[Entry/Exit outputs]")
                    for n, v in sorted(ent_out.items()):
                        print(_pretty_kv_line(n, v))

            # 간단한 시나리오 제어(예: 시설이 닫히면 조기 종료)
            fin_flag = False
            if 'facility_isOpen' in fac_out and not bool(int(fac_out['facility_isOpen'])):
                print("→ 시설이 닫혀 있어 시뮬레이션을 종료합니다.")
                fin_flag = True
            if 'zone_isOpen' in zon_out and not bool(int(zon_out['zone_isOpen'])):
                print("→ 존이 가득 차 있어 이후 단계를 생략합니다.")
                # 공간/입출차는 계속 찍고 싶지 않다면 여기서 조정 가능

            if fin_flag:
                break

            k += 1
            t = round(t + step_size, 12)

    finally:
        for m in modules:
            m.terminate()


if __name__ == '__main__':
    # 예시 실행: 기본 myfmu 경로 기준
    run_orchestrator(
        facility_fmu='myfmu/FacilityStatus.fmu',
        zone_fmu='myfmu/ZoneOccupancy.fmu',
        space_fmu='myfmu/SpaceOccupancy.fmu',
        entry_fmu='myfmu/EntryExitEvent.fmu',
        stop_time=10.0,
        step_size=1.0,
    )
