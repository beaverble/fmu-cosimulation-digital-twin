# file: test_steps_pretty_print.py
# 사용 예:
#   python test_steps_pretty_print.py --fmu .\myfmu\ZoneOccupancy.fmu
#   python test_steps_pretty_print.py --fmu .\myfmu\ZoneOccupancy.fmu --steps 1 --dt 1.0

import argparse, json, shutil
from pathlib import Path
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

def to_text(val):
    try:
        import numpy as np
        if isinstance(val, np.bytes_):
            val = bytes(val)
    except Exception:
        pass
    if isinstance(val, (bytes, bytearray)):
        try:
            return val.decode("utf-8")
        except Exception:
            return val.decode("cp949", errors="replace")
    return str(val)

def parse_args():
    ap = argparse.ArgumentParser(description="Pretty print zones_snapshot_json per step")
    ap.add_argument("--fmu", required=True, help="Path to ZoneOccupancy.fmu")
    ap.add_argument("--steps", type=int, default=5, help="Number of steps (default 5)")
    ap.add_argument("--dt", type=float, default=1.0, help="Step size seconds (default 1.0)")
    return ap.parse_args()

def main():
    args = parse_args()

    md = read_model_description(args.fmu)
    unzip = extract(args.fmu)

    try:
        model_id = md.coSimulation.modelIdentifier
        fmu = FMU2Slave(guid=md.guid, unzipDirectory=unzip,
                        modelIdentifier=model_id, instanceName="pretty")
        fmu.instantiate()
        total_time = args.steps * args.dt
        fmu.setupExperiment(startTime=0.0, stopTime=total_time)
        fmu.enterInitializationMode(); fmu.exitInitializationMode()

        vr_map = {v.name: v.valueReference for v in md.modelVariables}
        if "zones_snapshot_json" not in vr_map:
            raise RuntimeError("FMU에 'zones_snapshot_json' 출력 변수가 없습니다.")

        t = 0.0
        for k in range(args.steps):
            # 정확히 한 스텝 진행
            fmu.doStep(t, args.dt)

            # 스냅샷 읽기
            raw = fmu.getString([vr_map["zones_snapshot_json"]])[0]
            txt = to_text(raw)

            try:
                arr = json.loads(txt) if txt else []
            except Exception:
                arr = []
                print(f"[WARN] JSON 파싱 실패: {txt}")

            # 원하는 포맷으로 출력
            print(f"\n[step={k:03d} | t={int(t)}s]")
            for o in arr:
                # zone_thingId -> thingId, zone_isOpen -> isOpen 으로 표시
                thing_id = o.get("zone_thingId")
                is_open  = o.get("zone_isOpen")
                print(f"  - thingId={thing_id}  isOpen={is_open}")

            # 시간 업데이트
            t += args.dt

        fmu.terminate(); fmu.freeInstance()

    finally:
        shutil.rmtree(unzip, ignore_errors=True)

if __name__ == "__main__":
    main()

#   python test/test_zone_fmu.py --fmu .\myfmu\ZoneOccupancy.fmu