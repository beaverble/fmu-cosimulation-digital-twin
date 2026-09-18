# test_inout_fmu.py
import argparse
import shutil
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

def get_vr(md, name):
    for v in md.modelVariables:
        if v.name == name:
            return v.valueReference
    raise KeyError(f"Variable '{name}' not found")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fmu", required=True, help="Path to InOut.fmu (e.g., ./myfmu/InOut.fmu)")
    ap.add_argument("--stop", type=float, default=5.0)
    ap.add_argument("--dt", type=float, default=1.0)
    args = ap.parse_args()

    md = read_model_description(args.fmu)
    unzipdir = extract(args.fmu)

    if md.coSimulation is None:
        raise RuntimeError("This FMU does not support Co-Simulation.")
    model_id = md.coSimulation.modelIdentifier

    fmu = FMU2Slave(
        guid=md.guid,
        unzipDirectory=unzipdir,
        modelIdentifier=model_id,
        instanceName="inout_tester",
    )

    try:
        # 로깅 비활성화 (FMU 내부 logger 제거와 무관하지만 깔끔하게)
        fmu.instantiate(visible=False, loggingOn=False)
        fmu.setupExperiment(startTime=0.0, stopTime=args.stop)
        fmu.enterInitializationMode()
        fmu.exitInitializationMode()

        vr_vehicle = get_vr(md, "vehicle_thingId")
        vr_status  = get_vr(md, "transaction_status")

        t, k = 0.0, 0
        while t < args.stop + 1e-12:
            try:
                fmu.doStep(currentCommunicationPoint=t, communicationStepSize=args.dt)
            except Exception as e:
                print(f"[ERROR] doStep failed at t={t:.2f}: {e}")
                break

            vehicle_thingId = fmu.getString([vr_vehicle])[0]
            transaction_status = fmu.getInteger([vr_status])[0]
            print(f"[step={k:03d} | t={t:>5.2f}s] "
                  f"vehicle_thingId={vehicle_thingId}  transaction_status={transaction_status}")

            t += args.dt
            k += 1

        fmu.terminate()
    finally:
        fmu.freeInstance()
        shutil.rmtree(unzipdir, ignore_errors=True)

if __name__ == "__main__":
    main()

# python test_inout_fmu.py --fmu myfmu\InOutEvent.fmu --stop 10 --dt 1