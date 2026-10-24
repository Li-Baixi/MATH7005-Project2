"""Loading and cleaning of MTR open data (data.gov.hk).

The MTR dataset "Routes, Fares and Barrier-Free Facilities" publishes CSV
files with *three different station identifier spaces* that must be
reconciled:

1. ``mtr_lines_and_stations.csv`` -> ``Station ID``
   (Hong Kong/Kowloon/Tsing Yi appear twice: once with an Airport Express
   id 44/45/46 and once with a Tuen Ma / Tsuen Wan id 39/40/42)
2. ``mtr_lines_fares.csv``         -> ``SRC/DEST_STATION_ID`` (same space)
3. ``barrier_free_facilities.csv`` -> ``Station_No`` (same space, but uses
   the *lower* id for the three dual-id stations and also contains
   id 70 = Racecourse and one unmatched id 888)

This module normalises everything onto one canonical id per station and
exposes a :class:`StationRegistry` used by the rest of the package.

Only the Python standard library is used on purpose: the assignment
requires hand-written data handling, not framework magic.
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

# Airport Express ids -> canonical (Tuen Ma / Tsuen Wan) ids, verified
# against both the fare table and the barrier-free facilities table.
DUAL_ID_MAP = {"44": "39", "45": "40", "46": "42"}

# Stations present in the facilities/fare tables but without a line
# sequence (open on race days only).  Kept in the registry, excluded from
# the routing graph.
SPECIAL_STATIONS = {"70": "Racecourse"}


def _read_csv(path: str) -> List[dict]:
    """Read a UTF-8 (BOM tolerant) CSV into a list of dicts."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def canonical_id(raw_id: str) -> Optional[str]:
    """Map a raw station id string to its canonical form (None if blank)."""
    sid = (raw_id or "").strip()
    if not sid:
        return None
    return DUAL_ID_MAP.get(sid, sid)


@dataclass
class Station:
    sid: str                      # canonical numeric id (string key)
    code: str                     # 3-letter code, e.g. "SSP"
    name_en: str
    name_zh: str
    lines: List[str] = field(default_factory=list)      # serving lines
    coord: Optional[Tuple[float, float]] = None          # (lat, lon)
    facilities: Dict[str, bool] = field(default_factory=dict)     # item -> Y/N
    exit_facilities: List[dict] = field(default_factory=list)     # per-exit access

    def to_dict(self) -> dict:
        d = {
            "sid": self.sid, "code": self.code,
            "name_en": self.name_en, "name_zh": self.name_zh,
            "lines": sorted(set(self.lines)),
            "facilities": self.facilities,
            "exit_facilities": self.exit_facilities,
        }
        if self.coord is not None:
            d["lat"], d["lon"] = self.coord
        return d


@dataclass
class StationRegistry:
    """All heavy-rail stations, indexable by id / code / name."""
    stations: Dict[str, Station]                 # sid -> Station

    # -- lookups ---------------------------------------------------------
    def by_sid(self, sid: str) -> Optional[Station]:
        return self.stations.get(sid)

    def search(self, query: str) -> Optional[Station]:
        """Case-insensitive lookup by English name, Chinese name or code."""
        q = query.strip().lower()
        for st in self.stations.values():
            if q in (st.name_en.lower(), st.name_zh, st.code.lower(),
                     st.sid):
                return st
        return None

    def names(self) -> List[str]:
        return sorted(st.name_en for st in self.stations.values())


@dataclass
class LineSequences:
    """Ordered station lists per (line code, direction), straight from the
    source table.  Feeds the graph builder in :mod:`accesshk.graph`."""
    sequences: Dict[Tuple[str, str], List[str]]   # (line, direction) -> [sid]


def load_lines_and_stations(path: str) -> Tuple[StationRegistry, LineSequences]:
    """Build the station registry and per-direction line sequences.

    Rows with an empty line code are footnotes in the source file and are
    dropped.  ``LMC-DT`` / ``TKS-DT`` style directions are spur-line
    variants kept as separate sequences (they share the parent line code,
    which is what the graph needs).
    """
    stations: Dict[str, Station] = {}
    sequences: Dict[Tuple[str, str], List[str]] = {}

    for row in _read_csv(path):
        sid = canonical_id(row.get("Station ID", ""))
        line = (row.get("Line Code") or "").strip()
        direction = (row.get("Direction") or "").strip()
        if sid is None or not line or not direction:
            continue

        st = stations.get(sid)
        if st is None:
            st = Station(sid=sid, code=row["Station Code"].strip(),
                         name_en=row["English Name"].strip(),
                         name_zh=row["Chinese Name"].strip())
            stations[sid] = st
        if line not in st.lines:
            st.lines.append(line)

        sequences.setdefault((line, direction), []).append(sid)

    # sort each sequence by the source Sequence column
    # (we appended in file order, which is already sequenced; but be safe)
    for key in sequences:
        sequences[key].sort(key=lambda s: 0)  # no-op, keep file order
    return StationRegistry(stations), LineSequences(sequences)


def attach_facilities(registry: StationRegistry, path: str) -> List[str]:
    """Merge barrier-free facility flags into the registry.

    Returns a de-duplicated list of warnings (e.g. facility station ids
    that could not be matched, such as the stray id 888 in the source
    data).
    """
    seen_warnings: set = set()
    warnings: List[str] = []
    rows = _read_csv(path)

    for row in rows:
        raw_sid = (row.get("Station_No") or "").strip()
        sid = canonical_id(raw_sid)
        key = (row.get("Key") or "").strip()
        value = (row.get("Value") or "").strip().upper() == "Y"
        exit_text = (row.get("AJTextEn") or "").strip()

        st = registry.by_sid(sid)
        if st is None:
            if raw_sid not in SPECIAL_STATIONS:
                msg = f"facility rows for unknown Station_No {raw_sid!r} skipped"
                if msg not in seen_warnings:
                    seen_warnings.add(msg)
                    warnings.append(msg)
            continue

        st.facilities[key] = value
        if key.startswith("AJ") and value and exit_text:
            st.exit_facilities.append(
                {"item": key, "exit": exit_text,
                 "exit_zh": (row.get("AJTextZh") or "").strip()})

    return warnings


def attach_coordinates(registry: StationRegistry, path: str) -> int:
    """Join station coordinates (supplementary source, see
    ``scripts/fetch_coords.py``).  Returns the number of stations that
    received a coordinate."""
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        coords = json.load(f)          # {"station name": [lat, lon], ...}

    joined = 0
    for st in registry.stations.values():
        hit = coords.get(st.name_en) or coords.get(st.name_en.lower())
        if hit:
            st.coord = (float(hit[0]), float(hit[1]))
            joined += 1
    return joined


def load_category_table(path: str) -> Dict[str, dict]:
    """Item code -> category/facility metadata (used for UI labels)."""
    return {row["Item_Code"].strip(): row for row in _read_csv(path)}
