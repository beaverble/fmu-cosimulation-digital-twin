# -*- coding: utf-8 -*-
# file: fmu/device_status_monitor.py

from pythonfmu import (
    Fmi2Slave, Fmi2Causality, Fmi2Variability,
    Integer, Real, String
)
from pathlib import Path
import json, random

# pythonfmu 빌더가 사용할 클래스 이름 -> FMU 파일명이 됩니다: DeviceStatus.fmu
slave_class = "DeviceStatus"

class DeviceStatus(Fmi2Slave):
    author = "DTD"
    description = "Random device status generator (thingId/status/battery/signal)"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ---------- Outputs (모두 discrete, start 지정하지 않음) ----------
        self.device_thingId = ""
        self.register_variable(String(
            "device_thingId",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        self.device_status = 0
        self.register_variable(Integer(
            "device_status",          # 0=OFF/FAULT, 1=ON/OK 예시
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        self.device_batteryLevel = 0.0
        self.register_variable(Real(
            "device_batteryLevel",    # 0~100
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        self.device_signalStrength = 0.0
        self.register_variable(Real(
            "device_signalStrength",  # dBm, 대략 -95 ~ -45
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        # 스냅샷(JSON)도 필요하면 함께 제공
        self.devices_snapshot_json = ""
        self.register_variable(String(
            "devices_snapshot_json",
            causality=Fmi2Causality.output,
            variability=Fmi2Variability.discrete
        ))

        # 리소스에 07_device_example.json이 있으면 해당 thingId 목록 사용
        self._device_ids = self._load_device_ids()

    # 리소스에서 장치 목록 로드 (없으면 기본값 생성)
    def _load_device_ids(self):
        try:
            path = Path(self.resources) / "07_device_example.json"
            ids = []
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                for o in data:
                    did = o.get("device_thingId") or o.get("thingId") or o.get("id")
                    if isinstance(did, str) and did:
                        ids.append(did)
            if not ids:
                ids = [f"smartParking:Device{n:03d}" for n in range(1, 21)]
            return ids
        except Exception:
            return [f"smartParking:Device{n:03d}" for n in range(1, 21)]

    # 한 스텝마다 랜덤 값 출력
    def do_step(self, current_time: float, step_size: float) -> bool:
        device_id = random.choice(self._device_ids)

        self.device_thingId = device_id
        self.device_status = random.randint(0, 1)
        self.device_batteryLevel = float(random.randint(0, 100))
        self.device_signalStrength = float(random.randint(-95, -45))

        snapshot = [{
            "device_thingId": self.device_thingId,
            "device_status": self.device_status,
            "batteryLevel": self.device_batteryLevel,
            "signalStrength": self.device_signalStrength
        }]
        self.devices_snapshot_json = json.dumps(snapshot, ensure_ascii=False)

        return True
