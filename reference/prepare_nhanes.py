"""Build the NHANES extracts used by the data visualization tutorials.

This script is run MANUALLY and never during a documentation build. It
downloads SAS transport files from the United States Centers for Disease
Control and Prevention, joins them, subsets and renames the columns, and
writes plain CSV files into the tutorial data directories.

The downloaded ``xpt`` files are binary and must never be committed. Only the
derived CSV files belong in version control.

Usage::

    python utils/data/prepare_nhanes.py

Downloaded files are cached in ``utils/data/.cache`` so that repeated runs do
not re-download roughly 80 megabytes of source data. Delete that directory to
force a fresh download.
"""

import sys
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

# Cycle letter suffix mapped to the first year of the cycle, which also forms
# part of the download path.
CYCLES = {"H": 2013, "I": 2015, "J": 2017}

# The most recent cycle carries every component. Earlier cycles are used only
# for trend figures and are limited to components that stayed comparable.
LATEST_CYCLE = "J"
TREND_COMPONENTS = ("DEMO", "BMX", "DR1TOT")
LATEST_COMPONENTS = TREND_COMPONENTS + ("BPX", "TCHOL", "GHB")

URL_TEMPLATE = (
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{file}.xpt"
)

RENAMES = {
    "SEQN": "seqn",
    "RIAGENDR": "sex",
    "RIDAGEYR": "age_years",
    "RIDRETH3": "race_ethnicity",
    "INDFMPIR": "income_poverty_ratio",
    "WTMEC2YR": "survey_weight",
    "SDMVPSU": "psu",
    "SDMVSTRA": "stratum",
    "BMXBMI": "bmi",
    "BMXWT": "weight_kg",
    "BMXHT": "height_cm",
    "BMXWAIST": "waist_cm",
    "DR1TKCAL": "energy_kcal",
    "DR1TPROT": "protein_g",
    "DR1TCARB": "carbohydrate_g",
    "DR1TSUGR": "sugar_g",
    "DR1TFIBE": "fiber_g",
    "DR1TTFAT": "total_fat_g",
    "DR1TSODI": "sodium_mg",
    "DR1TCALC": "calcium_mg",
    "LBXTC": "cholesterol_mgdl",
    "LBXGH": "hba1c_percent",
}

SEX_LABELS = {1: "Male", 2: "Female"}

RACE_LABELS = {
    1: "Mexican American",
    2: "Other Hispanic",
    3: "Non-Hispanic White",
    4: "Non-Hispanic Black",
    6: "Non-Hispanic Asian",
    7: "Other or Multiracial",
}

# Blood pressure is recorded as up to four replicate readings. A reading of
# zero denotes a failed measurement rather than a real value.
SYSTOLIC_COLUMNS = ["BPXSY1", "BPXSY2", "BPXSY3", "BPXSY4"]
DIASTOLIC_COLUMNS = ["BPXDI1", "BPXDI2", "BPXDI3", "BPXDI4"]

MINIMUM_AGE = 18
SIZE_LIMIT_MB = 50

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(__file__).resolve().parent / ".cache"
OUTPUT_DIRECTORIES = (
    ROOT / "source" / "viz" / "r" / "data",
    ROOT / "source" / "viz" / "python" / "data",
)


def download(component, cycle):
    """Return a cached local path to one NHANES transport file."""
    name = f"{component}_{cycle}"
    destination = CACHE / f"{name}.xpt"
    if destination.exists():
        print(f"  cached   {name}")
        return destination

    url = URL_TEMPLATE.format(year=CYCLES[cycle], file=name)
    print(f"  download {name}")
    CACHE.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            destination.write_bytes(response.read())
    except urllib.error.HTTPError as error:
        raise SystemExit(f"Could not download {url} ({error.code}).") from error
    return destination


def read_component(component, cycle):
    """Read one transport file and keep only the columns that are used."""
    frame = pd.read_sas(download(component, cycle), format="xport")
    if component == "BPX":
        keep = ["SEQN"] + SYSTOLIC_COLUMNS + DIASTOLIC_COLUMNS
    else:
        keep = [column for column in frame.columns if column in RENAMES]
    return frame[[column for column in keep if column in frame.columns]]


def average_blood_pressure(frame):
    """Collapse the replicate blood pressure readings into two columns."""
    systolic = frame[[c for c in SYSTOLIC_COLUMNS if c in frame.columns]]
    diastolic = frame[[c for c in DIASTOLIC_COLUMNS if c in frame.columns]]
    frame["systolic_mmhg"] = systolic.replace(0, pd.NA).mean(axis=1).round(1)
    frame["diastolic_mmhg"] = diastolic.replace(0, pd.NA).mean(axis=1).round(1)
    return frame.drop(columns=systolic.columns.tolist() + diastolic.columns.tolist())


def build_cycle(cycle, components):
    """Join every component for one cycle into a single adult-only frame."""
    print(f"cycle {cycle} ({CYCLES[cycle]}-{CYCLES[cycle] + 1})")
    merged = None
    for component in components:
        frame = read_component(component, cycle)
        merged = frame if merged is None else merged.merge(frame, on="SEQN", how="left")

    if "BPXSY1" in merged.columns:
        merged = average_blood_pressure(merged)

    merged = merged.rename(columns=RENAMES)
    merged = merged[merged["age_years"] >= MINIMUM_AGE].copy()
    merged["sex"] = merged["sex"].map(SEX_LABELS)
    merged["race_ethnicity"] = merged["race_ethnicity"].map(RACE_LABELS)
    merged["seqn"] = merged["seqn"].astype("int64")
    merged.insert(1, "cycle", f"{CYCLES[cycle]}-{CYCLES[cycle] + 1}")
    print(f"  {len(merged):,} adults aged {MINIMUM_AGE} and over")
    return merged


def write(frame, filename):
    """Write one CSV into every tutorial data directory."""
    for directory in OUTPUT_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        frame.to_csv(path, index=False)
        size_mb = path.stat().st_size / 1024**2
        relative = path.relative_to(ROOT)
        if size_mb > SIZE_LIMIT_MB:
            sys.exit(f"{relative} is {size_mb:.1f} MB, over the {SIZE_LIMIT_MB} MB limit.")
        print(f"  wrote {relative} ({size_mb:.1f} MB)")


def main():
    latest = build_cycle(LATEST_CYCLE, LATEST_COMPONENTS)
    write(latest.drop(columns="cycle"), "nhanes-2017-2018.csv")

    frames = [build_cycle(cycle, TREND_COMPONENTS) for cycle in CYCLES]
    combined = pd.concat(frames, ignore_index=True)

    # Combining cycles requires dividing each two-year weight by the number of
    # cycles pooled. Omitting this step inflates every population estimate.
    combined["survey_weight"] = combined["survey_weight"] / len(CYCLES)

    write(combined, "nhanes-cycles.csv")
    print("\nDone. The xpt cache is git-ignored and may be deleted.")


if __name__ == "__main__":
    main()
