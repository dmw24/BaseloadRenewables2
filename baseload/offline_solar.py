"""Deterministic offline PV profile generator for NASA fallback."""

from __future__ import annotations

from calendar import isleap
from datetime import datetime, timedelta
from math import asin, cos, pi, radians, sin
from typing import List, Tuple

EXPECTED_HOURS = 8760


def _hours_in_year(year: int) -> int:
    return 8784 if isleap(year) else EXPECTED_HOURS


def _declination(day_of_year: int) -> float:
    return radians(23.44) * sin(2 * pi * (day_of_year - 81) / 365)


def _equation_of_time(day_of_year: int) -> float:
    b = 2 * pi * (day_of_year - 81) / 364
    return 9.87 * sin(2 * b) - 7.53 * cos(b) - 1.5 * sin(b)


def _cloudiness(day_of_year: int, hour: float, latitude: float, longitude: float) -> float:
    seasonal = 0.55 + 0.35 * sin(2 * pi * (day_of_year - 1) / 365 + radians(latitude / 2))
    diurnal = 0.08 * sin(2 * pi * hour / 24 + radians(longitude))
    planetary = 0.07 * sin(radians(latitude + longitude))
    wave = 0.05 * sin(2 * pi * (day_of_year * 0.13) + radians(longitude * 3))
    value = seasonal + diurnal + planetary + wave
    return min(1.05, max(0.35, value))


def generate_offline_hourly_profile(
    latitude: float, longitude: float, year: int
) -> Tuple[List[datetime], List[float]]:
    """Return a deterministic 8760-hour PV profile when NASA data is unavailable."""

    hours = _hours_in_year(year)
    start = datetime(year, 1, 1)
    timezone_offset = round(longitude / 15)
    lat_rad = radians(latitude)
    datetimes: List[datetime] = []
    pv_values: List[float] = []
    for hour_index in range(hours):
        utc_dt = start + timedelta(hours=hour_index)
        local_dt = utc_dt + timedelta(hours=timezone_offset)
        day_of_year = local_dt.timetuple().tm_yday
        local_hour = local_dt.hour + local_dt.minute / 60
        decl = _declination(day_of_year)
        eot = _equation_of_time(day_of_year)
        solar_time = local_hour + (eot + 4 * (longitude - timezone_offset * 15)) / 60
        hour_angle = radians(15 * (solar_time - 12))
        altitude = asin(
            sin(lat_rad) * sin(decl) + cos(lat_rad) * cos(decl) * cos(hour_angle)
        )
        sin_alt = max(0.0, sin(altitude))
        clear_sky = (sin_alt ** 1.25) * 1.1
        cloudiness = _cloudiness(day_of_year, local_hour, latitude, longitude)
        pv_kwh = min(1.2, clear_sky * cloudiness)
        datetimes.append(utc_dt)
        pv_values.append(pv_kwh)
    return datetimes, pv_values
