# test_parkingenv_fmu.py (임시폴더 버전)
from pathlib import Path
import tempfile
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave
import time

FMU = Path("myfmu/ParkingEnv.fmu").resolve()   # FMU 절대경로로
md = read_model_description(str(FMU))

with tempfile.TemporaryDirectory() as unzipdir:       # 임시폴더 = 절대경로
    extract(str(FMU), unzipdir)

    # 변수 참조 맵
    vr = {v.name: v.valueReference for v in md.modelVariables}

    slave = FMU2Slave(guid=md.guid,
                      modelIdentifier=md.coSimulation.modelIdentifier,
                      unzipDirectory=unzipdir,             # 절대경로 OK
                      instanceName="env")
    slave.instantiate()
    slave.setupExperiment(startTime=0.0)
    slave.enterInitializationMode()
    slave.setInteger([vr['random_seed']], [int(time.time())])  # 매 실행마다 다른 값
    # (원하면 파라미터 조정)
    # slave.setReal([vr['temp_min_c'], vr['temp_max_c']], [15.0, 30.0])
    slave.exitInitializationMode()

    t, h = 0.0, 1.0
    for i in range(10):
        slave.doStep(currentCommunicationPoint=t, communicationStepSize=h)
        T = slave.getReal([vr['env_temperature_c']])[0]
        H = slave.getReal([vr['env_humidity_pct']])[0]
        C = slave.getReal([vr['env_co_ppm']])[0]
        print(f"[step={i:03d} | t={t:.1f}s] T={T:.2f}℃, RH={H:.1f}%, CO={C:.1f}ppm")
        t += h

    slave.terminate()
    slave.freeInstance()
