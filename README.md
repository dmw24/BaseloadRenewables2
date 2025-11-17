# Baseload Renewables Model

This repository contains a modular Python workflow that:

1. Selects globally distributed land-based solar sites using a curated pool of major load centers and greedy farthest-point sampling.
2. Downloads hourly NASA POWER solar resource data for each site and converts it to PV output per installed kW.
3. Runs an annual baseload simulation to evaluate how different solar/battery build-outs serve a constant 1 GW load.

## Requirements

The project only relies on the Python standard library. A modern CPython 3.10+ interpreter with internet access (for NASA POWER API calls) is sufficient.

> **Offline fallback:** Some environments (including the execution sandbox used for automated tests) cannot reach the NASA POWER API. When downloads fail, the workflow now switches to a deterministic clear-sky model that approximates hourly PV production so the remainder of the pipeline can still be exercised. The generated values remain deterministic per site/year, are cached like real downloads, and are clearly logged so you know when the fallback was used.

## Usage

Create a virtual environment if desired and run the model end-to-end (selecting 10 sites, downloading 2021 data, and simulating all combinations of 1–8 GW PV with 1–15 GWh batteries):

```bash
python main.py --sites 10 --year 2021
```

Outputs are written to the `outputs/` directory:

- `selected_sites.csv`: latitude/longitude for each chosen site.
- `hourly_profiles/<site>/site_X_hourly_profiles.csv`: 8,760-hour traces for each PV/battery configuration (includes solar output, battery state-of-charge, unmet load, and overproduction).
- `hourly_profiles/<site>/site_X_annual_summary.csv`: Annual stats for every configuration at the site.
- `annual_capacity_factors.csv`: Aggregated capacity-factor table across all sites.

Hourly PV profiles are cached under `data/solar/` so repeated runs do not re-download NASA data.

## Exporting dashboard-ready data

The interactive map hosted under `docs/` expects a compact CSV with one row per site/configuration plus pre-computed LCOE estimates. Generate it with:

```bash
python -m baseload.dashboard_data \
    --summary outputs/annual_capacity_factors.csv \
    --output outputs/dashboard_dataset.csv
```

Behind the scenes the helper uses the summary file to compute a `Location` label (`LatXX.XX_LonYY.YY`), copies the latitude/longitude, and estimates LCOE via a simple cost model (default: $700/kW PV, $150/kWh battery, 7% discount rate, 25-year lifetime, and modest fixed O&M fractions). You can edit those constants inside `baseload/dashboard_data.py` if your study uses different financial assumptions. The resulting CSV works with the dashboard UI as well as the included sample data (`docs/sample_dashboard_data.csv`).

## GitHub Pages dashboard

Everything in `docs/` is a static Tailwind/Leaflet/D3 dashboard suitable for GitHub Pages. After pushing the repository you can enable Pages and point it at the `docs` folder to serve `index.html`. The page lets you upload any CSV produced by `baseload.dashboard_data` or quickly preview the bundled sample via the “Load bundled sample data” button.

To preview locally run:

```bash
python -m http.server --directory docs 8000
```

and visit `http://localhost:8000` in your browser. The current solar-only simulation sweep means the wind slider snaps to the closest available data (0 GW in the sample) but the control remains in the UI for future hybrid studies.

## Configuration

Key modeling assumptions live in the code:

- NASA POWER parameter `ALLSKY_SFC_SW_DWN` (global horizontal irradiance) drives PV output.
- A fixed derate factor of 0.8 converts irradiance to delivered energy per kW installed.
- Battery round-trip efficiency is set to 90% (split evenly between charge/discharge losses).
- Batteries start half full each year.

You can adjust these constants in `baseload/solar_data.py` and `baseload/simulation.py` as needed.
