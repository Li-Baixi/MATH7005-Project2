"""Fare tables: rail (incl. Airport Express) and MTR feeder bus.

All tables are keyed by canonical station id pairs (the same id space
as the routing graph), so a route's origin/destination sids look the
fare up directly.  Concession columns matter for the product's
audience: elderly (長者) and PWD (殘疾人士) Octopus fares are the $2
flat rate under the government concession schemes.

The Airport Express table is published separately with its own id
space and *no* elderly/PWD columns (that product has its own
concessions) — rows are joined by station name and flagged
``"note": "airport_express"``.
"""
from __future__ import annotations

import csv
import os
from typing import Dict, Optional, Tuple

from .datasets import StationRegistry

# mtr_lines_fares.csv columns we keep (Octopus + single, adult/concession)
RAIL_COLUMNS = {
    "OCT_ADT_FARE": "octopus_adult",
    "OCT_CON_ELDERLY_FARE": "octopus_elderly",
    "OCT_CON_PWD_FARE": "octopus_pwd",
    "SINGLE_ADT_FARE": "single_adult",
}
# airport_express_fares.csv columns (no elderly/PWD columns exist)
AEL_COLUMNS = {
    "OCT_ADT_FARE": "octopus_adult",
    "OCT_CHD_FARE": "octopus_child",
    "SINGLE_ADT_FARE": "single_adult",
    "SINGLE_CHD_FARE": "single_child",
}
# name normalisation for the AEL file ("HongKong" -> registry name)
AEL_NAME_MAP = {
    "HongKong": "Hong Kong",
    "TsingYi": "Tsing Yi",
    "AsiaWorldExpo": "AsiaWorld-Expo",
}


def load_rail_fares(path: str) -> Dict[Tuple[str, str], dict]:
    """{(src_sid, dst_sid): {fare kind: dollars}} — symmetric, both
    directions are present in the source; conflicts resolve to min."""
    table: Dict[Tuple[str, str], dict] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            key = (r["SRC_STATION_ID"], r["DEST_STATION_ID"])
            fares = {out: float(r[col])
                     for col, out in RAIL_COLUMNS.items()}
            if key in table:               # keep the cheaper duplicate
                fares = {k: min(v, table[key][k])
                         for k, v in fares.items()}
            table[key] = fares
            table[(key[1], key[0])] = fares
    return table


def load_ael_fares(path: str, registry: StationRegistry
                   ) -> Dict[Tuple[str, str], dict]:
    """Airport Express rows re-keyed onto canonical station ids via the
    registry (its own id space 44/45/46/47/56 collides with the rail
    ids, so ids there are unusable — names are the reliable join)."""
    table: Dict[Tuple[str, str], dict] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            a = registry.search(AEL_NAME_MAP.get(r["ST_FROM"], r["ST_FROM"]))
            b = registry.search(AEL_NAME_MAP.get(r["ST_TO"], r["ST_TO"]))
            if a is None or b is None:
                continue
            fares = {out: float(r[col])
                     for col, out in AEL_COLUMNS.items()}
            fares["note"] = "airport_express"
            table[(a.sid, b.sid)] = fares
            table[(b.sid, a.sid)] = fares
    return table


def load_bus_fares(path: str) -> Dict[str, dict]:
    """route -> {octopus_adult, octopus_elderly, octopus_pwd, ...};
    '-' (no such ticket type) becomes None."""
    out: Dict[str, dict] = {}
    cols = {"FARE_OCTO_ADULT": "octopus_adult",
            "FARE_OCTO_ELDERLY": "octopus_elderly",
            "FARE_OCTO_PWD": "octopus_pwd",
            "FARE_SINGLE_ADULT": "single_adult"}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out[r["ROUTE_ID"]] = {
                name: (float(r[col]) if r[col] not in ("-", "", None)
                       else None)
                for col, name in cols.items()}
    return out


def load_fare_tables(raw_dir: str, registry: StationRegistry
                     ) -> Dict[str, dict]:
    """Everything ``app/main.py`` needs in one call."""
    rail = load_rail_fares(os.path.join(raw_dir, "mtr_lines_fares.csv"))
    rail.update(load_ael_fares(
        os.path.join(raw_dir, "airport_express_fares.csv"), registry))
    return {
        "rail": rail,
        "bus": load_bus_fares(os.path.join(raw_dir, "mtr_bus_fares.csv")),
    }


def rail_fare(tables: dict, a_sid: str, b_sid: str) -> Optional[dict]:
    """Fare for one rail trip between stations (AEL rows override the
    general table where they exist; None when the pair is unknown)."""
    return tables["rail"].get((a_sid, b_sid))
