# file: test_vehicle_location_fmu.py
from pathlib import Path
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

BASE = Path("myfmu")
FMU = BASE / "VehicleLocation.fmu"

def get_vr_map(md):
    return {v.name: v.valueReference for v in md.modelVariables}

md = read_model_description(str(FMU))
unzipdir = extract(str(FMU))
fmu = FMU2Slave(guid=md.guid,
                unzipDirectory=unzipdir,
                modelIdentifier=md.coSimulation.modelIdentifier,
                instanceName="veh_loc")

fmu.instantiate()
fmu.setupExperiment(startTime=0.0)
fmu.enterInitializationMode()
# 필요 시 외부 경로 지정 가능:
# vmap = get_vr_map(md)
# fmu.setString([vmap["vehicles_json_path"]], [r".\json\06_vehicle_example.json"])
fmu.exitInitializationMode()

t, h = 0.0, 1.0
for k in range(5):
    fmu.doStep(currentCommunicationPoint=t, communicationStepSize=h)
    vmap = get_vr_map(md)
    thing = fmu.getString([vmap["vehicle_thingId"]])[0]
    loc   = fmu.getString([vmap["vehicle_location"]])[0]
    print(f"[step={k:03d} | t={int(t)}s]  vehicle_thingId={thing}  vehicle_location={loc}")
    t += h

fmu.terminate()
fmu.freeInstance()
