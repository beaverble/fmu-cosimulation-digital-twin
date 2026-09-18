# test_zone_full_checker.py
# -*- coding: utf-8 -*-
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave
from pathlib import Path
import shutil

FMU_PATH = Path("myfmu/ZoneFullDetector.fmu")

def b2s(x):
    """bytes / numpy.bytes_ -> str (utf-8)"""
    if isinstance(x, str):
        return x
    try:
        return x.decode('utf-8', 'ignore')   # bytes, bytearray
    except (AttributeError, UnicodeDecodeError):
        try:
            return bytes(x).decode('utf-8', 'ignore')  # numpy.bytes_ 등
        except Exception:
            return str(x)

def get_vr(md, name: str):
    for v in md.modelVariables:
        if v.name == name:
            return v.valueReference
    raise KeyError(name)

def main():
    md = read_model_description(FMU_PATH)
    unzipdir = extract(FMU_PATH)

    try:
        fmu = FMU2Slave(
            guid=md.guid,
            unzipDirectory=unzipdir,
            modelIdentifier=md.coSimulation.modelIdentifier,
            instanceName="inst"
        )

        # 변수 참조 준비
        vr_zone_in   = get_vr(md, "zone_thingId")
        vr_occ_in    = get_vr(md, "occupiedspot")
        vr_zone_out  = get_vr(md, "target_zone_thingId")
        vr_isfull    = get_vr(md, "isFull")

        # 실험 설정/초기화
        fmu.instantiate()
        fmu.setupExperiment(startTime=0.0)
        fmu.enterInitializationMode()

        # 초기 입력값 설정
        fmu.setString([vr_zone_in],   ["smartParking:Zone1"])
        fmu.setInteger([vr_occ_in],   [0])

        fmu.exitInitializationMode()

        # 시나리오: 점유수 변화를 매 초마다 변경
        # Zone1의 totalSpaces는 50이므로(예시 데이터), 50에서 isFull=1을 기대
        timeline = [
            (0.0, 10),
            (1.0, 50),   # == totalSpaces -> isFull=1
            (2.0, 45),
            (3.0, 50),   # 다시 만차
            (4.0, 49),
        ]

        current_time = 0.0
        for t, occ in timeline:
            # 스텝 시작 전 입력 갱신
            fmu.setInteger([vr_occ_in], [int(occ)])

            step = t - current_time
            if step < 0:
                step = 0.0
            fmu.doStep(currentCommunicationPoint=current_time, communicationStepSize=step)
            current_time = t

            # 출력 읽기
            out_zone = fmu.getString([vr_zone_out])[0]
            out_zone = b2s(out_zone)
            is_full  = fmu.getInteger([vr_isfull])[0]
            print(f"[t={current_time:.0f}s] zone={out_zone}, occupied={occ} -> isFull={is_full}")

        fmu.terminate()
        fmu.freeInstance()
    finally:
        shutil.rmtree(unzipdir, ignore_errors=True)

if __name__ == "__main__":
    main()
