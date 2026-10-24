"""Accessibility reasoning on top of the barrier-free facilities table.

The MTR facility codes follow four categories (see
``barrier_free_facility_category.csv``):

* ``AJ*``  entrance/exit accessibility (same level, ramp, lifts, stair lift)
* ``MJ*``  mobility-impaired facilities (wide gates, accessible toilets, ...)
* ``VJ*``  visually-impaired facilities (tactile paths, braille, ...)
* ``HJ*``  hearing-impaired facilities (induction loops, info displays, ...)

The key product decision lives here: **when is a station "step-free
end-to-end"?**  We require

1. at least one street-to-concourse access point that is step-free
   (same level / ramp / lift / stair lift), and
2. a step-free link between concourse and platform (paid-area lift).

Both halves come straight from official MTR data, and the per-exit
``AJTextEn`` field lets us name *which* entrance/exit to use.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .datasets import Station, load_category_table

# Exit-side (street -> concourse, unpaid area) step-free access items.
STREET_TO_CONCOURSE = {"AJ1", "AJ2", "AJ3", "AJ4", "AJ5", "AJ7", "AJ9"}
# Concourse -> platform (paid area) step-free items.
CONCOURSE_TO_PLATFORM = {"AJ5", "AJ8", "AJ9"}

# Non-MTR-managed equipment: usable but worth flagging in the UI.
NON_MTR_MANAGED = {"AJ4", "AJ7"}

# Friendly labels for the access items used in route advice.
ITEM_LABELS = {
    "AJ1": "same-level entrance",
    "AJ2": "ramp",
    "AJ3": "lift (street to concourse)",
    "AJ4": "lift (non-MTR managed)",
    "AJ5": "stair lift",
    "AJ7": "stair lift (non-MTR managed)",
    "AJ8": "lift (concourse to platform)",
    "AJ9": "vertical lifting platform",
}


def step_free_exits(st: Station) -> List[dict]:
    """Exits/entrances of *st* with a step-free street-to-concourse link.

    Returns the per-exit records (item code, exit name) so the router can
    tell the user *which* door to head for, not just "it exists".
    """
    if not st.exit_facilities:            # no named exits -> no exit advice
        return []
    return [e for e in st.exit_facilities
            if e["item"] in STREET_TO_CONCOURSE]


def has_street_step_free(st: Station) -> bool:
    """Any step-free street-to-concourse access, even when the source
    data does not name the exit (a ramp with no exit label still means
    the station is reachable without stairs)."""
    return any(st.facilities.get(k) for k in STREET_TO_CONCOURSE)


def has_paid_area_lift(st: Station) -> bool:
    """Is there a step-free link between concourse and platform?"""
    return any(st.facilities.get(k) for k in CONCOURSE_TO_PLATFORM)


def is_step_free(st: Station) -> bool:
    """Step-free from street to platform: usable entrance AND paid-area lift."""
    return has_street_step_free(st) and has_paid_area_lift(st)


def step_free_evidence(st: Station) -> dict:
    """Human-readable evidence for the step-free verdict (UI + report)."""
    exits = step_free_exits(st)
    return {
        "step_free": is_step_free(st),
        "street_access": [
            {"exit": e["exit"], "how": ITEM_LABELS.get(e["item"], e["item"]),
             "managed_by_mtr": e["item"] not in NON_MTR_MANAGED}
            for e in exits
        ],
        "platform_access": [
            ITEM_LABELS.get(k, k)
            for k in CONCOURSE_TO_PLATFORM if st.facilities.get(k)
        ],
    }


def facility_vector(st: Station, item_codes: List[str]) -> List[float]:
    """0/1 feature vector over the ordered item codes (NumPy-ready input
    for the clustering analysis)."""
    return [1.0 if st.facilities.get(c) else 0.0 for c in item_codes]


def category_coverage(st: Station) -> Dict[str, float]:
    """Share of facilities present, per impairment category (AJ/MJ/VJ/HJ).

    A compact station accessibility profile used both for ranking and as
    clustering features.
    """
    cov: Dict[str, List[int]] = {}
    for code, present in st.facilities.items():
        cat = code[:2]
        cov.setdefault(cat, [0, 0])
        cov[cat][1] += 1
        if present:
            cov[cat][0] += 1
    return {cat: round(have / total, 3) if total else 0.0
            for cat, (have, total) in sorted(cov.items())}


def nearest_step_free(target: Station,
                      candidates: List[Station]) -> Optional[Tuple[Station, float]]:
    """Nearest fully step-free station to *target* (straight-line km,
    computed with NumPy haversine in :func:`accesshk.geo.haversine_km`).

    Powers the "no step-free route from here — nearest accessible
    station is ..." fallback in the product.
    """
    import numpy as np
    from .geo import haversine_km

    best, best_km = None, None
    for st in candidates:
        if st is target or st.coord is None or target.coord is None:
            continue
        if not is_step_free(st):
            continue
        km = float(haversine_km(np.array([target.coord]),
                                np.array([st.coord]))[0])
        if best_km is None or km < best_km:
            best, best_km = st, km
    return (best, best_km) if best else None
