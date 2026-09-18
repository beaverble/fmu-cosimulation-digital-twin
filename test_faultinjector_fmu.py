# -*- coding: utf-8 -*-
from pathlib import Path
import shutil

from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

FMU_PATH = Path("myfmu") / "FaultInjector.fmu"

unzipdir = extract(str(FMU_PATH))
md = read_model_description(str(FMU_PATH))
model_id = md.coSimulation.modelIdentifier

# 인스턴스 생성
fmu = FMU2Slave(
    guid=md.guid,
    unzipDirectory=unzipdir,
    modelIdentifier=model_id,
    instanceName='fault'
)

fmu.instantiate()
fmu.setupExperiment(startTime=0.0)
fmu.enterInitializationMode()

# 변수명 -> valueReference 매핑
vr = {v.name: v.valueReference for v in md.modelVariables}

# 입력 설정 (확률과 시드)
fmu.setReal([vr["gate_fail_prob"]],  [0.020])  # 20%/step
fmu.setReal([vr["kiosk_fail_prob"]], [0.10])  # 10%/step
fmu.setInteger([vr["random_seed"]],  [3])

fmu.exitInitializationMode()

t, dt, stop = 0.0, 1.0, 20.0
while t < stop:
    fmu.doStep(currentCommunicationPoint=t, communicationStepSize=dt)
    g = bool(fmu.getBoolean([vr["trigger_GateFailure"]])[0])
    k = bool(fmu.getBoolean([vr["trigger_KioskFailure"]])[0])
    print(f"[t={int(t+dt):02d}s] GateFail={g}  KioskFail={k}")
    t += dt

fmu.terminate()
fmu.freeInstance()
shutil.rmtree(unzipdir, ignore_errors=True)
