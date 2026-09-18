# -*- coding: utf-8 -*-
# file: fmu/schedule_manager.py

from pythonfmu import Fmi2Slave, Fmi2Causality, Fmi2Variability
from pythonfmu.variables import Real, String, Boolean, Integer

from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

current_time_str = datetime.now().isoformat(timespec='seconds')

class ScheduleManager(Fmi2Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 1. 매개변수 (Parameters) 정의
        self.start_datetime_str = current_time_str
        self.time_zone_str = "Asia/Seoul"
        self.peak_time_windows_str = "08:00-10:00,17:00-19:00"  # 콤마로 구분
        self.holiday_list_str = "2025-01-01,2025-05-05"  # 콤마로 구분
        self.peak_days_int = 12345  # 1=월, 2=화... (01234가 더 나을 수 있음)

        # 2. 출력 (Outputs) 정의
        self.isPeakTime = False
        self.isHoliday = False
        self.isWeekend = False
        self.day_of_week = 0  # 0=Mon, 6=Sun
        self.current_real_datetime_str = ""
        self.current_hour_float = 0.0

        # --- 변수 등록 (Parameter) ---
        self.register_variable(
            String("start_datetime_str", causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed,
                   description="시뮬레이션 0초의 실제 시간 (ISO 8601)"))
        self.register_variable(
            String("time_zone_str", causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed,
                   description="기준 시간대 (예: Asia/Seoul)"))
        self.register_variable(
            String("peak_time_windows_str", causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed,
                   description="피크 타임 윈도우 (예: 08:00-10:00,17:00-19:00)"))
        self.register_variable(
            String("holiday_list_str", causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed,
                   description="공휴일 목록 (예: 2025-01-01,2025-05-05)"))
        self.register_variable(
            Integer("peak_days_int", causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed,
                    description="피크 타임 적용 요일 (예: 12345)"))

        # --- 변수 등록 (Output) ---
        # [수정됨] Boolean, Integer, String 타입에 variability=Fmi2Variability.discrete 추가
        self.register_variable(Boolean("isPeakTime",
                                       causality=Fmi2Causality.output,
                                       variability=Fmi2Variability.discrete,
                                       description="현재 피크 타임 여부"))

        self.register_variable(Boolean("isHoliday",
                                       causality=Fmi2Causality.output,
                                       variability=Fmi2Variability.discrete,
                                       description="현재 공휴일 여부"))

        self.register_variable(Boolean("isWeekend",
                                       causality=Fmi2Causality.output,
                                       variability=Fmi2Variability.discrete,
                                       description="현재 주말 여부"))

        self.register_variable(Integer("day_of_week",
                                       causality=Fmi2Causality.output,
                                       variability=Fmi2Variability.discrete,
                                       description="현재 요일 (0=월, 6=일)"))

        self.register_variable(String("current_real_datetime_str",
                                      causality=Fmi2Causality.output,
                                      variability=Fmi2Variability.discrete,
                                      description="현재 실제 시간 (디버깅용)"))

        self.register_variable(Real("current_hour_float",
                                    causality=Fmi2Causality.output,
                                    variability=Fmi2Variability.discrete,
                                    description="현재 시간(소수점) (예: 9.5)"))

        # --- 내부 처리용 변수 ---
        self.start_datetime = None
        self.time_zone = None
        self.parsed_peak_windows = []  # (start_hour_float, end_hour_float) 튜플의 리스트
        self.parsed_holidays = set()  # "YYYY-MM-DD" 문자열의 집합
        self.peak_days_str = ""

    def setup_experiment(self, start_time: float):
        # 시뮬레이션 시작 전, 매개변수 값을 파싱하여 내부 변수 초기화

        # 1. 시간대 설정
        try:
            self.time_zone = ZoneInfo(self.time_zone_str)
        except ZoneInfoNotFoundError:
            self.log(f"경고: 시간대 '{self.time_zone_str}'를 찾을 수 없습니다. UTC로 대체합니다.")
            self.time_zone = ZoneInfo("UTC")

        # 2. 시작 시간 파싱
        try:
            # 매개변수로 받은 문자열을 datetime 객체로 변환
            dt = datetime.fromisoformat(self.start_datetime_str)
            # 만약 시간대 정보가 없다면, 설정된 time_zone을 강제로 적용
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=self.time_zone)
            self.start_datetime = dt
        except ValueError:
            self.log(f"치명적 오류: start_datetime_str '{self.start_datetime_str}' 파싱 실패.")
            return False  # 시뮬레이션 시작 실패

        # 3. 공휴일 목록 파싱
        self.parsed_holidays = set(self.holiday_list_str.split(','))

        # 4. 피크 타임 윈도우 파싱
        self.parsed_peak_windows = []
        try:
            windows = self.peak_time_windows_str.split(',')
            for window in windows:
                if not window: continue
                start_str, end_str = window.split('-')
                start_t = time.fromisoformat(start_str)
                end_t = time.fromisoformat(end_str)
                start_h = start_t.hour + start_t.minute / 60.0
                end_h = end_t.hour + end_t.minute / 60.0
                self.parsed_peak_windows.append((start_h, end_h))
        except Exception as e:
            self.log(f"경고: peak_time_windows_str 파싱 실패. '{e}'")

        # 5. 피크 타임 요일
        self.peak_days_str = str(self.peak_days_int)

        self.log(f"ScheduleManager 초기화 완료. 시작 시간: {self.start_datetime}")
        return True

    # [수정됨] 계산 로직을 별도 헬퍼 함수로 분리
    def _update_outputs(self, current_simulation_time: float) -> bool:
        """시뮬레이션 시간을 기준으로 모든 출력 변수를 계산합니다."""

        # 1. "실제 시간" 계산
        current_real_datetime = self.start_datetime + timedelta(seconds=current_simulation_time)

        # 2. 기본 시간 정보 업데이트
        self.current_real_datetime_str = current_real_datetime.isoformat()
        self.day_of_week = current_real_datetime.weekday()  # 0=월, 6=일
        self.current_hour_float = current_real_datetime.hour + (current_real_datetime.minute / 60.0) + (
                    current_real_datetime.second / 3600.0)
        self.isWeekend = (self.day_of_week >= 5)  # 5=토, 6=일

        # 3. isHoliday 계산
        current_date_str = current_real_datetime.strftime("%Y-%m-%d")
        self.isHoliday = (current_date_str in self.parsed_holidays)

        # 4. isPeakTime 계산
        is_peak = False  # 기본값

        is_peak_applicable_day = (
                not self.isWeekend and
                not self.isHoliday and
                (str(self.day_of_week) in self.peak_days_str)
        )

        if is_peak_applicable_day:
            for start_h, end_h in self.parsed_peak_windows:
                if start_h <= self.current_hour_float < end_h:
                    is_peak = True
                    break

        self.isPeakTime = is_peak

        return True

    # [수정됨] t=0일 때의 값을 계산하기 위해 exit_initialization_mode 추가
    def exit_initialization_mode(self):
        """시뮬레이션 시작(t=0) 직전 초기값을 계산합니다."""
        return self._update_outputs(current_simulation_time=0.0)

    # [수정됨] do_step 로직 변경
    def do_step(self, current_time: float, step_size: float) -> bool:
        """
        FMI Co-Simulation 표준에 따라,
        do_step(t, dt)는 t+dt 시점 (즉, 스텝이 끝나는 시점)의 값을 계산합니다.
        """

        # current_time은 스텝의 시작 시간입니다.
        # (예: t=0.0, dt=3600.0 -> 3600.0 시점의 값을 계산)
        # (예: t=3600.0, dt=3600.0 -> 7200.0 시점의 값을 계산)
        next_time = current_time + step_size

        return self._update_outputs(current_simulation_time=next_time)