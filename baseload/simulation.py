"""Yearly baseload simulation (standard library implementation)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from .site_selection import Site
from .solar_data import SolarProfile


@dataclass
class SimulationConfig:
    pv_capacities_gw: Sequence[float]
    battery_capacities_gwh: Sequence[float]
    baseload_gw: float = 1.0
    round_trip_efficiency: float = 0.9


@dataclass
class SimulationResult:
    hourly_path: Path
    summary_path: Path
    summary_rows: List[dict]


def _simulate_single_configuration(
    site: Site,
    pv_profile: SolarProfile,
    pv_gw: float,
    battery_gwh: float,
    baseload_gw: float,
    rte: float,
    hourly_writer: csv.DictWriter,
) -> dict:
    baseload_mwh = baseload_gw * 1000.0
    pv_multiplier = pv_gw * 1_000_000.0 / 1000.0
    capacity_mwh = battery_gwh * 1000.0
    soc = 0.5 * capacity_mwh
    charge_eff = discharge_eff = rte ** 0.5

    unmet_total = 0.0
    overproduction_total = 0.0
    served_total = 0.0

    for dt, pv_value in zip(pv_profile.datetimes, pv_profile.pv_kwh_per_kw):
        solar_mwh = pv_value * pv_multiplier / 1000.0
        surplus = max(0.0, solar_mwh - baseload_mwh)
        deficit = max(0.0, baseload_mwh - solar_mwh)
        charge_added = 0.0
        discharge_to_load = 0.0
        unmet = 0.0
        overproduction = 0.0

        if surplus > 0:
            potential_charge = surplus * charge_eff
            charge_added = min(capacity_mwh - soc, potential_charge)
            energy_used_for_charge = charge_added / charge_eff if charge_eff > 0 else 0.0
            overproduction = max(0.0, surplus - energy_used_for_charge)
            soc += charge_added
        elif deficit > 0:
            possible_discharge = min(soc, deficit / discharge_eff if discharge_eff > 0 else 0.0)
            soc -= possible_discharge
            discharge_to_load = possible_discharge * discharge_eff
            unmet = max(0.0, deficit - discharge_to_load)
        served = baseload_mwh - unmet
        unmet_total += unmet
        overproduction_total += overproduction
        served_total += served
        hourly_writer.writerow(
            {
                "datetime": dt.isoformat(),
                "site": site.name,
                "latitude": f"{site.latitude:.4f}",
                "longitude": f"{site.longitude:.4f}",
                "pv_gw": f"{pv_gw:.2f}",
                "battery_gwh": f"{battery_gwh:.2f}",
                "solar_generation_mwh": f"{solar_mwh:.6f}",
                "load_mwh": f"{baseload_mwh:.2f}",
                "battery_state_of_charge_mwh": f"{soc:.6f}",
                "battery_charge_mwh": f"{charge_added:.6f}",
                "battery_discharge_mwh": f"{discharge_to_load:.6f}",
                "unmet_load_mwh": f"{unmet:.6f}",
                "overproduction_mwh": f"{overproduction:.6f}",
            }
        )
    hours = len(pv_profile.datetimes)
    load_total = baseload_mwh * hours
    cf = served_total / load_total if load_total > 0 else 0.0
    summary = {
        "site": site.name,
        "latitude": f"{site.latitude:.4f}",
        "longitude": f"{site.longitude:.4f}",
        "pv_gw": f"{pv_gw:.2f}",
        "battery_gwh": f"{battery_gwh:.2f}",
        "annual_load_mwh": f"{load_total:.2f}",
        "energy_served_mwh": f"{served_total:.2f}",
        "unmet_load_mwh": f"{unmet_total:.2f}",
        "overproduction_mwh": f"{overproduction_total:.2f}",
        "capacity_factor": f"{cf:.4f}",
    }
    return summary


def run_yearly_simulation(
    site: Site,
    pv_profile: SolarProfile,
    config: SimulationConfig,
    output_dir: Path,
) -> SimulationResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    hourly_path = output_dir / f"{site.name}_hourly_profiles.csv"
    summary_path = output_dir / f"{site.name}_annual_summary.csv"
    hourly_fieldnames = [
        "datetime",
        "site",
        "latitude",
        "longitude",
        "pv_gw",
        "battery_gwh",
        "solar_generation_mwh",
        "load_mwh",
        "battery_state_of_charge_mwh",
        "battery_charge_mwh",
        "battery_discharge_mwh",
        "unmet_load_mwh",
        "overproduction_mwh",
    ]
    summary_rows: List[dict] = []
    with hourly_path.open("w", newline="") as hourly_handle:
        hourly_writer = csv.DictWriter(hourly_handle, fieldnames=hourly_fieldnames)
        hourly_writer.writeheader()
        for pv_gw in config.pv_capacities_gw:
            for battery_gwh in config.battery_capacities_gwh:
                summary = _simulate_single_configuration(
                    site=site,
                    pv_profile=pv_profile,
                    pv_gw=pv_gw,
                    battery_gwh=battery_gwh,
                    baseload_gw=config.baseload_gw,
                    rte=config.round_trip_efficiency,
                    hourly_writer=hourly_writer,
                )
                summary_rows.append(summary)
    summary_fieldnames = list(summary_rows[0].keys()) if summary_rows else []
    with summary_path.open("w", newline="") as summary_handle:
        writer = csv.DictWriter(summary_handle, fieldnames=summary_fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)
    return SimulationResult(hourly_path=hourly_path, summary_path=summary_path, summary_rows=summary_rows)

