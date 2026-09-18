# -*- coding: utf-8 -*-
from pathlib import Path
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

BASE = Path("myfmu")
FMU = BASE / "DriverBehavior.fmu"

def vmap(md):
    return {sv.name: sv.valueReference for sv in md.modelVariables}

def set_str(fmu, vm, name, val):
    fmu.setString([vm[name]], [str(val)])

def set_int(fmu, vm, name, val):
    fmu.setInteger([vm[name]], [int(val)])

def set_bool(fmu, vm, name, val: bool):
    fmu.setBoolean([vm[name]], [bool(val)])

def set_real(fmu, vm, name, val: float):
    fmu.setReal([vm[name]], [float(val)])

def get_real(fmu, vm, *names):
    return fmu.getReal([vm[n] for n in names])

if __name__ == "__main__":
    md = read_model_description(FMU)
    unzipdir = extract(str(FMU))
    vm = vmap(md)

    fmu = FMU2Slave(
        guid=md.guid,
        unzipDirectory=unzipdir,
        modelIdentifier=md.coSimulation.modelIdentifier,
        instanceName="DriverBehaviorTest"
    )

    fmu.instantiate()
    fmu.setupExperiment(startTime=0.0)
    fmu.enterInitializationMode()

    # ---- 파라미터 주입 (init 이전) ----
    set_int(fmu, vm, "seed", 42)
    set_str(fmu, vm, "find_dist", "exponential")  # "normal" / "lognormal" / "uniform" 가능
    set_real(fmu, vm, "find_mean", 180.0)
    set_real(fmu, vm, "find_std",  60.0)
    set_real(fmu, vm, "find_min",  10.0)
    set_real(fmu, vm, "find_max",  900.0)
    set_bool(fmu, vm, "auto_resample", True)

    fmu.exitInitializationMode()

    t = 0.0
    h = 1.0
    for k in range(5):
        fmu.doStep(currentCommunicationPoint=t, communicationStepSize=h)
        t += h
        (find_s,) = get_real(fmu, vm, "timeToFindSpace")
        print(f"[step={k:03d} | t={int(t)}s]  timeToFindSpace={find_s:.1f}s")

    fmu.terminate()
    fmu.freeInstance()
