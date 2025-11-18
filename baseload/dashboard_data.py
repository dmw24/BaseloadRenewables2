"""Utilities for exporting aggregated CSVs for the web dashboard."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass
class CostAssumptions:
    """Simple cost model used to back-of-the-envelope LCOE."""

    pv_capex_per_kw: float = 700.0
    battery_capex_per_kwh: float = 150.0
    pv_fixed_om_fraction: float = 0.02
    battery_fixed_om_fraction: float = 0.015
    discount_rate: float = 0.07
    lifetime_years: int = 25

    def annuity_factor(self) -> float:
        r = self.discount_rate
        n = self.lifetime_years
        if r == 0:
            return 1 / n if n else 0
        numerator = r * (1 + r) ** n
        denominator = (1 + r) ** n - 1
        return numerator / denominator if denominator else 0.0

    def annualize_capex(self, capex: float) -> float:
        return capex * self.annuity_factor()

    def annual_fixed_om(self, pv_capex: float, battery_capex: float) -> float:
        return pv_capex * self.pv_fixed_om_fraction + battery_capex * self.battery_fixed_om_fraction


@dataclass
class DashboardRow:
    location: str
    site_name: str
    latitude: float
    longitude: float
    solar_gw: float
    wind_gw: float
    battery_gwh: float
    system_capacity_factor: float
    lcoe_usd_per_mwh: float | None
    annual_load_mwh: float
    energy_served_mwh: float
    unmet_load_mwh: float
    overproduction_mwh: float

    def to_csv_row(self) -> dict:
        return {
            "Location": self.location,
            "Site_Name": self.site_name,
            "Latitude": f"{self.latitude:.4f}",
            "Longitude": f"{self.longitude:.4f}",
            "Solar_GW": f"{self.solar_gw:.2f}",
            "Wind_GW": f"{self.wind_gw:.2f}",
            "Battery_GWh": f"{self.battery_gwh:.2f}",
            "System_Capacity_Factor": f"{self.system_capacity_factor:.4f}",
            "LCOE_USD_per_MWh": "" if self.lcoe_usd_per_mwh is None else f"{self.lcoe_usd_per_mwh:.2f}",
            "Annual_Load_MWh": f"{self.annual_load_mwh:.2f}",
            "Energy_Served_MWh": f"{self.energy_served_mwh:.2f}",
            "Unmet_Load_MWh": f"{self.unmet_load_mwh:.2f}",
            "Overproduction_MWh": f"{self.overproduction_mwh:.2f}",
        }


def _safe_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_location(lat: float, lon: float) -> str:
    return f"Lat{lat:.2f}_Lon{lon:.2f}"


def _estimate_lcoe(
    pv_gw: float,
    battery_gwh: float,
    energy_served_mwh: float,
    *,
    costs: CostAssumptions,
) -> float | None:
    pv_capex = pv_gw * 1_000_000 * costs.pv_capex_per_kw
    battery_capex = battery_gwh * 1_000 * costs.battery_capex_per_kwh
    annualized = costs.annualize_capex(pv_capex + battery_capex)
    fixed_om = costs.annual_fixed_om(pv_capex, battery_capex)
    total_annual_cost = annualized + fixed_om
    if energy_served_mwh <= 0:
        return None
    return total_annual_cost / energy_served_mwh


def build_dashboard_rows(
    summary_rows: Iterable[dict],
    *,
    wind_levels: Sequence[float] | None = None,
    costs: CostAssumptions | None = None,
) -> List[DashboardRow]:
    wind_levels = wind_levels or [0.0]
    costs = costs or CostAssumptions()
    dashboard_rows: List[DashboardRow] = []
    for row in summary_rows:
        site = row.get("site", "")
        latitude = _safe_float(row.get("latitude", 0.0))
        longitude = _safe_float(row.get("longitude", 0.0))
        pv_gw = _safe_float(row.get("pv_gw", 0.0))
        battery_gwh = _safe_float(row.get("battery_gwh", 0.0))
        load_mwh = _safe_float(row.get("annual_load_mwh", 0.0))
        served_mwh = _safe_float(row.get("energy_served_mwh", 0.0))
        unmet_mwh = _safe_float(row.get("unmet_load_mwh", 0.0))
        overprod_mwh = _safe_float(row.get("overproduction_mwh", 0.0))
        cf = _safe_float(row.get("capacity_factor", 0.0))
        lcoe = _estimate_lcoe(pv_gw, battery_gwh, served_mwh, costs=costs)
        location = _format_location(latitude, longitude)
        for wind in wind_levels:
            dashboard_rows.append(
                DashboardRow(
                    location=location,
                    site_name=site,
                    latitude=latitude,
                    longitude=longitude,
                    solar_gw=pv_gw,
                    wind_gw=wind,
                    battery_gwh=battery_gwh,
                    system_capacity_factor=cf,
                    lcoe_usd_per_mwh=lcoe,
                    annual_load_mwh=load_mwh,
                    energy_served_mwh=served_mwh,
                    unmet_load_mwh=unmet_mwh,
                    overproduction_mwh=overprod_mwh,
                )
            )
    return dashboard_rows


def load_summary_csv(path: Path) -> List[dict]:
    with path.open() as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def write_dashboard_csv(rows: Sequence[DashboardRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("Location\n", encoding="utf-8")
        return
    fieldnames = list(rows[0].to_csv_row().keys())
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export dashboard-friendly CSV")
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("outputs/annual_capacity_factors.csv"),
        help="Path to the aggregated simulation summary CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/dashboard_dataset.csv"),
        help="Destination CSV for the dashboard",
    )
    parser.add_argument(
        "--wind-levels",
        type=float,
        nargs="*",
        default=[0.0],
        help="Wind build-outs (GW) to duplicate rows for. Use 0 if the study has no wind",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary_rows = load_summary_csv(args.summary)
    dashboard_rows = build_dashboard_rows(summary_rows, wind_levels=args.wind_levels)
    write_dashboard_csv(dashboard_rows, args.output)


if __name__ == "__main__":
    main()
