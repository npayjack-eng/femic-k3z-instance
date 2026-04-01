from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = REPO_ROOT / "models" / "k3z_patchworks_model"
SOURCE_TRACKS = MODEL_ROOT / "tracks_pct_heavy"
TARGET_TRACKS = MODEL_ROOT / "tracks_pct_heavy_zones"
GROUPS_SOURCE = SOURCE_TRACKS / "groups_zones.csv"
LOG_GRADE_VALUE_RE = re.compile(
    r"^product\.Logs_Grade_Value_[A-Z]+\.managed\.(?P<au>[^.]+)\.(?P<species>[^.]+)\.(?P<event>[^.]+)$"
)


def append_revenue_rollups(accounts_path: Path, products_path: Path) -> None:
    with products_path.open("r", encoding="utf-8", newline="") as handle:
        product_rows = list(csv.DictReader(handle))

    rollup_sources: dict[tuple[str, str], list[str]] = {}
    for row in product_rows:
        label = row["LABEL"]
        match = LOG_GRADE_VALUE_RE.match(label)
        if not match:
            continue
        key = (match.group("species"), match.group("event"))
        rollup_sources.setdefault(key, []).append(label)

    if not rollup_sources:
        return

    with accounts_path.open("r", encoding="utf-8", newline="") as handle:
        account_rows = list(csv.DictReader(handle))
        fieldnames = handle.readline()

    existing = {
        (row["GROUP"], row["ATTRIBUTE"], row["ACCOUNT"], row["SUM"]) for row in account_rows
    }

    additions: list[dict[str, str]] = []
    for (species, event), labels in sorted(rollup_sources.items()):
        species_account = f"product.Logs_Grade_Value_Total.managed.{species}.{event}"
        total_account = f"product.Logs_Grade_Value_Total.managed.Total.{event}"
        for label in sorted(labels):
            species_row = {
                "GROUP": "_MANAGED_",
                "ATTRIBUTE": label,
                "ACCOUNT": species_account,
                "SUM": "1",
            }
            total_row = {
                "GROUP": "_MANAGED_",
                "ATTRIBUTE": label,
                "ACCOUNT": total_account,
                "SUM": "1",
            }
            for row in (species_row, total_row):
                key = (row["GROUP"], row["ATTRIBUTE"], row["ACCOUNT"], row["SUM"])
                if key not in existing:
                    additions.append(row)
                    existing.add(key)

    if not additions:
        return

    with accounts_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["GROUP", "ATTRIBUTE", "ACCOUNT", "SUM"])
        writer.writeheader()
        writer.writerows(account_rows + additions)


def main() -> None:
    if not SOURCE_TRACKS.is_dir():
        raise FileNotFoundError(f"Missing source tracks directory: {SOURCE_TRACKS}")
    if not GROUPS_SOURCE.is_file():
        raise FileNotFoundError(f"Missing zoned groups source: {GROUPS_SOURCE}")

    if TARGET_TRACKS.exists():
        shutil.rmtree(TARGET_TRACKS)
    shutil.copytree(SOURCE_TRACKS, TARGET_TRACKS)
    shutil.copy2(GROUPS_SOURCE, TARGET_TRACKS / "groups.csv")
    products_path = TARGET_TRACKS / "products.csv"
    append_revenue_rollups(TARGET_TRACKS / "accounts.csv", products_path)
    append_revenue_rollups(TARGET_TRACKS / "accounts.default.csv", products_path)
    print(f"Refreshed {TARGET_TRACKS} from {SOURCE_TRACKS} with {GROUPS_SOURCE.name}")


if __name__ == "__main__":
    main()
