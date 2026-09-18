# -*- coding: utf-8 -*-
import os, argparse, shutil, json
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fmu",      default="./myfmu/FacilityStatus.fmu")
    ap.add_argument("--json",     default="json/01_facility_example.json")
    ap.add_argument("--steps",    type=int, default=5)
    ap.add_argument("--step-sec", type=float, default=3600.0)
    ap.add_argument("--seed",     type=int, default=-1, help=">=0이면 난수 고정")
    args = ap.parse_args()

    FMU = os.path.abspath(args.fmu)
    JSON = os.path.abspath(args.json)
    dt = float(args.step_sec)
    n  = int(args.steps)

    md = read_model_description(FMU)
    unzipdir = extract(FMU)
    vr = {v.name: v.valueReference for v in md.modelVariables}

    slave = FMU2Slave(
        guid=md.guid,
        unzipDirectory=unzipdir,
        modelIdentifier=md.coSimulation.modelIdentifier,
        instanceName="inst"
    )

    try:
        slave.instantiate()
        slave.setupExperiment(startTime=0.0)

        # 파라미터 설정 (리스트로 넘기기!)
        slave.setString([vr["facility_json"]], [JSON])
        if "random_seed" in vr and args.seed is not None:
            slave.setInteger([vr["random_seed"]], [int(args.seed)])

        slave.enterInitializationMode()
        slave.exitInitializationMode()

        t = 0.0
        for k in range(n + 1):
            snap = slave.getString([vr["facilities_snapshot_json"]])[0]
            try:
                arr = json.loads(snap) if snap else []
            except Exception:
                arr = []
            print(f"\n[step={k:03d} | t={int(t)}s]")
            for o in arr:
                print(f"  - thingId={o.get('facility_thingId')}  isOpen={o.get('facility_isOpen')}")

            if k == n:
                break
            slave.doStep(currentCommunicationPoint=t, communicationStepSize=dt)
            t += dt

        slave.terminate()
    finally:
        slave.freeInstance()
        shutil.rmtree(unzipdir, ignore_errors=True)

if __name__ == "__main__":
    main()
