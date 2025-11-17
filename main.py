"""Command-line entry point for the baseload renewable model."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import List

from baseload import fetch_hourly_pv_profile, run_yearly_simulation
from baseload.site_selection import generate_sites
from baseload.simulation import SimulationConfig
from baseload.solar_data import SolarDataError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Baseload renewables simulation")
    parser.add_argument("--sites", type=int, default=10, help="Number of sites to select")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--year", type=int, default=2021, help="Calendar year for NASA data")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"), help="Output directory")
    parser.add_argument("--cache-dir", type=Path, default=Path("data/solar"), help="Solar cache directory")
    return parser.parse_args()


def _write_sites(sites, path: Path) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "latitude", "longitude"])
        writer.writeheader()
        for site in sites:
            writer.writerow({"name": site.name, "latitude": f"{site.latitude:.4f}", "longitude": f"{site.longitude:.4f}"})


def _write_global_summary(rows: List[dict], path: Path) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir
    solar_cache: Path = args.cache_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    sites = generate_sites(args.sites, seed=args.seed)
    sites_csv = output_dir / "selected_sites.csv"
    _write_sites(sites, sites_csv)

    pv_capacities = [float(x) for x in range(1, 9)]  # 1-8 GW
    battery_capacities = [float(x) for x in range(1, 16)]  # 1-15 GWh
    config = SimulationConfig(pv_capacities_gw=pv_capacities, battery_capacities_gwh=battery_capacities)

    global_summary_rows: List[dict] = []
    hourly_dir = output_dir / "hourly_profiles"
    hourly_dir.mkdir(parents=True, exist_ok=True)

    for site in sites:
        print(f"Processing {site.name} ({site.latitude:.2f}, {site.longitude:.2f})")
        try:
            solar_profile = fetch_hourly_pv_profile(site.latitude, site.longitude, year=args.year, cache_dir=solar_cache)
        except SolarDataError as exc:
            print(f"Failed to download NASA data for {site.name}: {exc}")
            sys.exit(1)
        site_dir = hourly_dir / site.name
        result = run_yearly_simulation(site, solar_profile, config, site_dir)
        global_summary_rows.extend(result.summary_rows)

    summary_csv = output_dir / "annual_capacity_factors.csv"
    _write_global_summary(global_summary_rows, summary_csv)
    print(f"Wrote site list to {sites_csv}")
    print(f"Wrote annual summaries to {summary_csv}")


if __name__ == "__main__":
    main()

