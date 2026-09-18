# file: test_space_all_open_print.py
# 사용 예:
#   python test_space_all_open_print.py --fmu .\myfmu\SpaceAllOpen.fmu
#   python test_space_all_open_print.py --fmu .\myfmu\SpaceAllOpen.fmu --steps 3 --dt 0.5

import argparse, json, os, shutil
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

def b2s(x):
    """bytes -> str 안전 변환"""
    return x.decode("utf-8", "ignore") if isinstance(x, (bytes, bytearray)) else x

def vr(md, name):
    for v in md.modelVariables:
        if v.name == name:
            return v.valueReference
    raise KeyError(name)

def main():
    ap = argparse.ArgumentParser(description="Print ALL spaces per step (thingId, zoneId, isOpen)")
    ap.add_argument("--fmu", required=True, help="Path to SpaceAllOpen.fmu")
    ap.add_argument("--steps", type=int, default=5, help="Number of steps (default: 5)")
    ap.add_argument("--dt", type=float, default=1.0, help="Step size seconds (default: 1.0)")
    args = ap.parse_args()

    unzip = None
    try:
        md = read_model_description(args.fmu)
        unzip = extract(args.fmu)
        mi = md.coSimulation.modelIdentifier

        fmu = FMU2Slave(guid=md.guid, unzipDirectory=unzip, modelIdentifier=mi, instanceName="space_all_print")
        fmu.instantiate()
        fmu.setupExperiment(startTime=0.0)
        fmu.enterInitializationMode()
        fmu.exitInitializationMode()

        vr_snap = vr(md, "spaces_snapshot_json")

        t = 0.0
        for k in range(args.steps):
            # 한 스텝 진행 (키워드 대신 위치 인자 사용)
            fmu.doStep(t, args.dt)

            # 스냅샷 읽고 파싱
            raw = fmu.getString([vr_snap])[0]
            txt = b2s(raw)
            try:
                arr = json.loads(txt) if txt else []
                if isinstance(arr, dict):
                    arr = [arr]
            except Exception:
                arr = []
                print(f"[WARN] JSON 파싱 실패: {txt[:200]} ...")

            # 예쁜 출력 (요청 포맷 + zoneId 추가)
            print(f"\n[step={k:03d} | t={int(t)}s]")
            for o in arr:
                thing_id = o.get("space_thingId")
                zone_id  = o.get("space_zoneId")
                is_open  = o.get("space_isOpen")
                print(f" - thingId={thing_id} zoneId={zone_id} isOpen={is_open}")

            t += args.dt

        fmu.terminate()
        fmu.freeInstance()

    finally:
        if unzip and os.path.isdir(unzip):
            shutil.rmtree(unzip, ignore_errors=True)

if __name__ == "__main__":
    main()

# python test_space_fmu.py --fmu .\myfmu\SpaceOccupancy.fmu