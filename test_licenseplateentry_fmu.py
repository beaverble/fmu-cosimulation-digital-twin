# -*- coding: utf-8 -*-
"""
Built FMU 테스트 (FMI 2.0 Co-Simulation)
- 입력 String 변수: licensePlate
- 출력 String 변수: ntryRecord (JSON 문자열)
- 시나리오:
  t=0  : ""
  t=1  : "12가3456"  -> ntryRecord 생성
  t=2  : "12가3456"  -> 변화 없음
  t=3  : ""          -> 리셋
  t=4  : "34나7890"  -> ntryRecord 생성
  t=5  : "12가3456"  -> 다시 생성
"""

import os
import json
import shutil
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave


def get_vr_map(model_description):
    """변수명 -> valueReference 매핑 딕셔너리 생성"""
    vr_map = {}
    for v in model_description.modelVariables:
        vr_map[v.name] = v.valueReference
    return vr_map


def s(obj):
    """bytes/str 안전 출력용"""
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except Exception:
            return repr(obj)
    return obj


def main():
    # 1) FMU 경로 (프로젝트 기본 규칙: myfmu/ 아래)
    fmu_path = os.path.abspath(os.path.join("myfmu", "LicensePlateEntry.fmu"))
    if not os.path.isfile(fmu_path):
        raise FileNotFoundError(f"FMU not found: {fmu_path}")

    unzipdir = None
    fmu = None
    try:
        # 2) 모델 설명 읽기 + 압축 해제
        md = read_model_description(fmu_path)
        unzipdir = os.path.abspath(extract(fmu_path))

        # 3) Co-Simulation FMU 인스턴스 생성
        if md.coSimulation is None:
            raise RuntimeError("This FMU is not a Co-Simulation FMU.")

        model_identifier = md.coSimulation.modelIdentifier
        fmu = FMU2Slave(
            guid=md.guid,
            modelIdentifier=model_identifier,
            unzipDirectory=unzipdir,
            instanceName="LicensePlateEntryTest",
        )

        # 4) instantiate -> setupExperiment -> init
        fmu.instantiate()
        # stopTime은 필수 아님, tolerance도 생략 가능
        fmu.setupExperiment(startTime=0.0)
        fmu.enterInitializationMode()
        fmu.exitInitializationMode()

        # 5) valueReference 매핑
        vr = get_vr_map(md)
        vr_license = vr.get("licensePlate")
        vr_record = vr.get("ntryRecord")
        assert vr_license is not None and vr_record is not None, "FMU 변수명이 맞는지 확인하세요."

        # 6) 테스트 타임라인
        timeline = [
            (0.0, ""),             # 초기: 빈 문자열
            (1.0, "12가3456"),     # 신규 번호판 -> 이벤트 발생
            (2.0, "123나3456"),     # 동일 번호판 -> 변화 없음
            (3.0, ""),             # 리셋
            (4.0, "34나7890"),     # 신규 번호판 -> 이벤트 발생
            (5.0, "55호56"),     # 재감지 -> 이벤트 발생
        ]

        last_t = 0.0
        for step_idx, (t, plate) in enumerate(timeline):
            # 입력 설정 (String)
            fmu.setString([vr_license], [plate])

            # 도스텝
            dt = max(1e-9, t - last_t)
            ok = fmu.doStep(currentCommunicationPoint=t, communicationStepSize=dt)


            # 출력 읽기 (String)
            record = fmu.getString([vr_record])[0]

            # 보기 좋게 출력
            hdr = f"[step={step_idx:03d} | t={t:.1f}s] licensePlate={plate!r}"
            if record:
                text = s(record)
                try:
                    obj = json.loads(text)
                    print(f"{hdr} -> ntryRecord(JSON) = {obj}")
                except Exception:
                    print(f"{hdr} -> ntryRecord(str)  = {text}")
            else:
                print(f"{hdr} -> ntryRecord(empty)")

            last_t = t

        # 7) 종료
        fmu.terminate()
        fmu.freeInstance()
        fmu = None
        print("\n테스트 완료!")

    finally:
        # 자원 정리
        try:
            if fmu is not None:
                fmu.freeInstance()
        except Exception:
            pass
        if unzipdir and os.path.isdir(unzipdir):
            shutil.rmtree(unzipdir, ignore_errors=True)


if __name__ == "__main__":
    main()
