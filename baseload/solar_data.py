"""NASA POWER data utilities using only the Python standard library."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
from urllib import parse, request
from urllib.error import URLError

SYSTEM_DERATE = 0.8
DEFAULT_YEAR = 2021
NASA_ENDPOINT = "https://power.larc.nasa.gov/api/temporal/hourly/point"
USER_AGENT = "BaseloadRenewables/1.0 (OpenAI Assistant)"
EXPECTED_HOURS = 8760


class SolarDataError(RuntimeError):
    """Raised when solar data cannot be retrieved."""


@dataclass
class SolarProfile:
    latitude: float
    longitude: float
    year: int
    datetimes: List[datetime]
    pv_kwh_per_kw: List[float]

    def rows(self):
        for dt, value in zip(self.datetimes, self.pv_kwh_per_kw):
            yield {"datetime": dt, "pv_kwh_per_kw": value}


def _cache_path(cache_dir: Path, latitude: float, longitude: float, year: int) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = f"lat{latitude:+.2f}_lon{longitude:+.2f}_{year}.csv"
    return cache_dir / filename


def _download_hourly_power(latitude: float, longitude: float, year: int) -> SolarProfile:
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN",
        "community": "RE",
        "longitude": longitude,
        "latitude": latitude,
        "start": year,
        "end": year,
        "format": "JSON",
    }
    url = f"{NASA_ENDPOINT}?{parse.urlencode(params)}"
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with request.urlopen(req, timeout=120) as resp:
            payload = json.load(resp)
    except URLError as exc:
        raise SolarDataError(f"NASA POWER request failed: {exc}") from exc
    try:
        raw = payload["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
    except KeyError as exc:
        raise SolarDataError(f"Unexpected NASA POWER payload: {payload}") from exc
    items = []
    for ts, value in raw.items():
        if value is None:
            continue
        dt = datetime.strptime(ts, "%Y%m%d%H")
        items.append((dt, float(value) * SYSTEM_DERATE))
    items.sort(key=lambda item: item[0])
    datetimes = [dt for dt, _ in items]
    values = [val for _, val in items]
    if len(datetimes) != EXPECTED_HOURS:
        start = datetime(year, 1, 1)
        expected = [start + timedelta(hours=i) for i in range(EXPECTED_HOURS)]
        mapping = {dt: val for dt, val in items}
        datetimes = expected
        values = [mapping.get(dt, 0.0) for dt in expected]
    return SolarProfile(latitude=latitude, longitude=longitude, year=year, datetimes=datetimes, pv_kwh_per_kw=values)


def _load_cached_profile(path: Path, latitude: float, longitude: float, year: int) -> SolarProfile:
    datetimes: List[datetime] = []
    values: List[float] = []
    with path.open("r", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            datetimes.append(datetime.fromisoformat(row["datetime"]))
            values.append(float(row["pv_kwh_per_kw"]))
    return SolarProfile(latitude=latitude, longitude=longitude, year=year, datetimes=datetimes, pv_kwh_per_kw=values)


def _save_profile(path: Path, profile: SolarProfile) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["datetime", "pv_kwh_per_kw"])
        for dt, value in zip(profile.datetimes, profile.pv_kwh_per_kw):
            writer.writerow([dt.isoformat(), f"{value:.6f}"])


def fetch_hourly_pv_profile(
    latitude: float,
    longitude: float,
    year: int = DEFAULT_YEAR,
    cache_dir: str | Path = "data/solar",
) -> SolarProfile:
    """Fetch (and cache) hourly PV yield per kW for the requested site."""

    cache_path = _cache_path(Path(cache_dir), latitude, longitude, year)
    if cache_path.exists():
        return _load_cached_profile(cache_path, latitude, longitude, year)
    profile = _download_hourly_power(latitude, longitude, year)
    _save_profile(cache_path, profile)
    return profile

