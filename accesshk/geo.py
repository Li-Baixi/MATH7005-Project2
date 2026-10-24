"""Geographic helpers (NumPy-vectorised where it matters).

Station coordinates are *supplementary* data: the MTR open data set
publishes an ``Exit_Coordinate_X_Y`` column, but it is empty for every
row in the current release (verified: 0 of 3564 rows populated), so we
fetch station node positions from OpenStreetMap once
(``scripts/fetch_coords.py``) and cache them as a small JSON file.

Distances feed two things:

* edge-weight estimation for the routing graph (distance / line speed),
* the "nearest step-free station" fallback.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

EARTH_RADIUS_KM = 6371.0088


def haversine_km(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Great-circle distance in kilometres.

    ``a`` and ``b`` are arrays of shape ``(n, 2)`` holding ``(lat, lon)``
    in degrees; broadcasting works for pairwise and cross matrices alike
    (``a`` shape ``(n, 2)``, ``b`` shape ``(m, 2)`` -> ``(n, m)`` matrix).
    """
    lat1 = np.radians(a[..., 0])
    lon1 = np.radians(a[..., 1])
    lat2 = np.radians(b[..., 0])
    lon2 = np.radians(b[..., 1])

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (np.sin(dlat / 2.0) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2)
    return 2.0 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(h))


def coord_or_none(pair) -> Optional[Tuple[float, float]]:
    """Defensive parse of a cached coordinate pair."""
    if pair is None:
        return None
    lat, lon = float(pair[0]), float(pair[1])
    if not (20 < lat < 26 and 112 < lon < 117):    # sanity: inside Hong Kong
        return None
    return lat, lon
