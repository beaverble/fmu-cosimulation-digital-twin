# file: test_vehicleproperties_manual.py  (patched)
from pathlib import Path
import shutil, sys
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

def b2s(x):
    if isinstance(x, (bytes, bytearray)):
        return x.decode("utf-8", errors="replace")
    return "" if x is None else str(x)

def main():
    # 콘솔 UTF-8 (가능하면)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    fmu_path = Path("myfmu/VehicleProperties.fmu").resolve()
    assert fmu_path.exists(), f"FMU not found: {fmu_path}"

    md = read_model_description(str(fmu_path))
    unzipdir = extract(str(fmu_path))
    model_id = md.coSimulation.modelIdentifier

    fmu = FMU2Slave(guid=md.guid, modelIdentifier=model_id, unzipDirectory=unzipdir)
    fmu.instantiate()

    start_time, stop_time, step_size = 0.0, 10.0, 1.0
    fmu.setupExperiment(startTime=start_time)
    fmu.enterInitializationMode()
    fmu.exitInitializationMode()

    name_to_vr = {v.name: v.valueReference for v in md.modelVariables}
    vr_thing = name_to_vr["vehicle_thingId"]
    vr_type  = name_to_vr["vehicle_type"]
    vr_plate = name_to_vr["vehicle_licenseplate"]

    t = start_time
    step_idx = 0
    print(f"[OK] running: {fmu_path}")
    print("time, thingId, type, licensePlate")

    while t <= stop_time:
        fmu.doStep(currentCommunicationPoint=t, communicationStepSize=step_size)
        thing = b2s(fmu.getString([vr_thing])[0])
        vtype = b2s(fmu.getString([vr_type])[0])
        plate = b2s(fmu.getString([vr_plate])[0])
        print(f"[step={step_idx:03d} | t={t:.0f}s] {thing}, {vtype}, {plate}")
        t += step_size
        step_idx += 1

    fmu.terminate()
    fmu.freeInstance()
    shutil.rmtree(unzipdir, ignore_errors=True)

if __name__ == "__main__":
    main()
