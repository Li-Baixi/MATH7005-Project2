"""Fetch MTR station coordinates (supplementary data).

The official MTR open-data release has an ``Exit_Coordinate_X_Y`` column
that is empty for every row (verified 2026-10), so station positions come
from Wikipedia instead.  This is *supplementary* data as allowed by the
assignment; fetched once, cached as JSON, committed so the project runs
offline.

Three stages, each a plain batched MediaWiki API query:

1. English Wikipedia — articles linked from 'List of MTR stations'
2. Chinese Wikipedia — ``<中文名>站`` (+ disambiguated variants)
3. MANUAL_OVERRIDES — approximate positions for the last few stragglers
   (±100 m precision, ample for edge-weight estimation)

Usage:  python -I scripts/fetch_coords.py data/raw data/supplementary
"""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

RAW, OUT_DIR = sys.argv[1], sys.argv[2]

API_EN = "https://en.wikipedia.org/w/api.php"
API_ZH = "https://zh.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "AccessHK/0.1 (course project)"}
BATCH = 50  # titles per API request (MediaWiki limit for anonymous users)

# ±100 m approximate public positions; the routing graph only needs
# enough precision to estimate inter-station travel time.
MANUAL_OVERRIDES = {
    "Kowloon": [22.3037, 114.1599],
    "Hong Kong": [22.2843, 114.1577],
}


def api_get(endpoint, params, retries=5):
    """GET with exponential backoff — Wikipedia rate-limits (HTTP 429)
    aggressive callers, so be patient instead of failing the run."""
    url = endpoint + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503) and attempt < retries - 1:
                wait = 2 ** (attempt + 2)       # 4s, 8s, 16s, 32s
                print(f"  HTTP {exc.code}, backing off {wait}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("unreachable")


def coords_from_titles(endpoint, title_map):
    """Query coordinates for ``title -> our station name`` in batches.

    ``coprimary=all`` also returns secondary coordinates — many MTR
    station articles only carry those.  When several are present we
    prefer the primary-marked one, else the first listed."""
    coords = {}
    todo = list(title_map)
    for i in range(0, len(todo), BATCH):
        data = api_get(endpoint, {"action": "query", "prop": "coordinates",
                                  "coprimary": "all", "format": "json",
                                  "redirects": 1,
                                  "titles": "|".join(todo[i:i + BATCH])})
        redir = {r["to"]: r["from"]
                 for r in data.get("query", {}).get("redirects", [])}
        for page in data.get("query", {}).get("pages", {}).values():
            if "coordinates" not in page:
                continue
            title = page.get("title", "")
            src = title if title in title_map else redir.get(title, title)
            name = title_map.get(src) or title_map.get(title)
            if name is not None:
                clist = page["coordinates"]
                c = next((c for c in clist if c.get("primary") != ""),
                         clist[0])
                coords[name] = [c["lat"], c["lon"]]
        time.sleep(1)                              # be polite to the API
    return coords


def normalize(title):
    """'Central station (MTR)' -> 'central'; en-dash aware."""
    t = title.lower().replace("–", "-").replace("—", "-")
    if "(" in t:
        t = t.split("(")[0].strip()
    if t.endswith(" station"):
        t = t[: -len(" station")].strip()
    return t


def stage_english(wanted):
    """Stage 1: coordinate-bearing articles on English Wikipedia."""
    titles, cont = [], None
    while True:                                     # follow pagination
        params = {"action": "query", "titles": "List of MTR stations",
                  "prop": "links", "pllimit": 500, "plnamespace": 0,
                  "format": "json"}
        if cont:
            params["plcontinue"] = cont
        data = api_get(API_EN, params)
        for page in data["query"]["pages"].values():
            titles += [l["title"] for l in page.get("links", [])]
        cont = data.get("continue", {}).get("plcontinue")
        if not cont:
            break

    norm_to_name = {normalize(n): n for n in wanted}
    title_map = {t: norm_to_name[normalize(t)]
                 for t in titles if normalize(t) in norm_to_name}
    return coords_from_titles(API_EN, title_map)


def stage_chinese(missing, name_zh):
    """Stage 2: Chinese Wikipedia by Chinese station name.

    Titles tried in order: ``<名>站``, ``<名>站 (港鐵)`` — several MTR
    station articles are disambiguated (e.g. 九龍站 (港鐵))."""
    coords = {}
    for suffix in ("站", "站 (港鐵)", "站 (香港)"):
        still = [n for n in missing if n not in coords]
        if not still:
            break
        title_map = {f"{name_zh[n]}{suffix}": n
                     for n in still if name_zh.get(n)}
        coords.update(coords_from_titles(API_ZH, title_map))
    return coords


def main():
    with open(os.path.join(RAW, "mtr_lines_and_stations.csv"),
              encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["English Name"].strip()]
    wanted = {r["English Name"].strip() for r in rows}
    name_zh = {r["English Name"].strip(): r["Chinese Name"].strip()
               for r in rows}

    # resumable: start from any coordinates cached by earlier runs, so
    # rate-limit interruptions never lose progress
    out_path = os.path.join(OUT_DIR, "station_coords.json")
    matched = {}
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            matched = json.load(f)

    missing = [n for n in sorted(wanted) if n not in matched]
    if missing:
        matched.update(stage_english(set(missing)))
        print(f"stage 1 (en.wikipedia): {len(matched)} stations total")

    missing = [n for n in sorted(wanted) if n not in matched]
    if missing:
        before = len(matched)
        matched.update(stage_chinese(missing, name_zh))
        print(f"stage 2 (zh.wikipedia): +{len(matched) - before} stations")

    still = [n for n in sorted(wanted) if n not in matched]
    for n in still:
        if n in MANUAL_OVERRIDES:
            matched[n] = MANUAL_OVERRIDES[n]
    still = [n for n in sorted(wanted) if n not in matched]

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(matched, f, ensure_ascii=False, indent=1)
    print(f"total matched {len(matched)}/{len(wanted)} -> {out_path}")
    if still:
        print("unmatched (fallback edge weights will be used):",
              ", ".join(still))


if __name__ == "__main__":
    main()
