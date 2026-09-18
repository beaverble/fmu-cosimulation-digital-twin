# test_findspacetime_steps.py
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

def b2s(x):
    return x.decode('utf-8') if isinstance(x, (bytes, bytearray)) else str(x)

def vr_map(md):
    return {v.name: v.valueReference for v in md.modelVariables}

def main():
    fmu_path = "myfmu/FindSpaceTime.fmu"

    md = read_model_description(fmu_path)
    vrs = vr_map(md)
    unzipdir = extract(fmu_path)
    model_id = md.coSimulation.modelIdentifier

    fmu = FMU2Slave(guid=md.guid, modelIdentifier=model_id, unzipDirectory=unzipdir)

    try:
        fmu.instantiate()
        fmu.setupExperiment(startTime=0.0)
        fmu.enterInitializationMode()

        # 초기 spaceID 설정
        fmu.setString([vrs["spaceID"]], ["smartParking:SpaceA-101"])

        fmu.exitInitializationMode()

        # t=0 시점 값 출력 (exitInitializationMode에서 이미 계산됨)
        spaceId = b2s(fmu.getString([vrs["spaceId"]])[0])
        secs = fmu.getReal([vrs["timeToFindSpace_sec"]])[0]
        print(f"[step=000 | t=0s] {spaceId} {secs:.1f}")

        # 스텝 진행하면서 매번 출력
        t = 0.0
        for step in range(1, 11):  # 10스텝 예시
            fmu.doStep(currentCommunicationPoint=t, communicationStepSize=1.0)
            t += 1.0

            # (옵션) 중간에 spaceID 바꾸어 새 랜덤시간 유도
            # if step == 5:
            #     fmu.setString([vrs["spaceID"]], ["smartParking:SpaceB-202"])

            spaceId = b2s(fmu.getString([vrs["spaceId"]])[0])
            secs = fmu.getReal([vrs["timeToFindSpace_sec"]])[0]
            print(f"[step={step:03d} | t={int(t)}s] {spaceId} {secs:.1f}")

    finally:
        try:
            fmu.terminate()
        except Exception:
            pass
        fmu.freeInstance()

if __name__ == "__main__":
    main()
