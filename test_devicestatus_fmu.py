# -*- coding: utf-8 -*-
from pathlib import Path
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

FMU = Path("myfmu") / "DeviceStatus.fmu"

def vmap_by_name(md):
    return {v.name: v.valueReference for v in md.modelVariables}

if __name__ == "__main__":
    md = read_model_description(FMU)
    unzipdir = extract(FMU)
    vmap = vmap_by_name(md)

    fmu = FMU2Slave(guid=md.guid,
                    unzipDirectory=unzipdir,
                    modelIdentifier=md.coSimulation.modelIdentifier,
                    instanceName="dev1")

    start_time = 0.0
    step = 1.0

    fmu.instantiate()
    fmu.setupExperiment(startTime=start_time)
    fmu.enterInitializationMode()
    fmu.exitInitializationMode()

    t = start_time
    for k in range(10):
        # doStep
        fmu.doStep(currentCommunicationPoint=t, communicationStepSize=step)
        t += step

        did = fmu.getString([vmap["device_thingId"]])[0]
        status = fmu.getInteger([vmap["device_status"]])[0]
        batt = fmu.getReal([vmap["device_batteryLevel"]])[0]
        rssi = fmu.getReal([vmap["device_signalStrength"]])[0]

        print(f"[step={k:03d} | t={int(t)}s]  "
              f"device_thingId={did}  device_status={status}  "
              f"batterylevel={int(batt)}  signalstrength={int(rssi)}")

    fmu.terminate()
    fmu.freeInstance()
