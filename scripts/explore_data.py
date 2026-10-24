# -*- coding: utf-8 -*-
"""Exploration of MTR open data CSVs (data.gov.hk).

Reads only; prints structure, ID-space relations and sample profiles so the
data model for AccessHK can be designed on facts, not guesses.
"""
import csv
import sys
from collections import Counter, defaultdict

RAW = sys.argv[1] if len(sys.argv) > 1 else "data/raw"


def load(name):
    with open(f"{RAW}/{name}", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


lines = load("mtr_lines_and_stations.csv")
fares = load("mtr_lines_fares.csv")
cats = load("barrier_free_facility_category.csv")
fac = load("barrier_free_facilities.csv")

print("== mtr_lines_and_stations ==")
per_line = Counter(r["Line Code"] for r in lines)
print("lines:", dict(per_line))
print("directions:", Counter(r["Direction"] for r in lines))
names = {r["English Name"] for r in lines}
codes = {r["Station Code"]: r["English Name"] for r in lines}
ids = {r["Station ID"]: r["English Name"] for r in lines}
print("unique stations by name:", len(names), "| by code:", len(codes), "| by id:", len(ids))

print("\n== mtr_lines_fares ==")
fare_ids = {r["SRC_STATION_ID"]: r["SRC_STATION_NAME"] for r in fares}
fare_names = {r["SRC_STATION_NAME"] for r in fares} | {r["DEST_STATION_NAME"] for r in fares}
print("unique stations:", len(fare_names))
print("names in fares but NOT in lines_and_stations:", sorted(fare_names - names))
print("names in lines but NOT in fares:", sorted(names - fare_names))
id_match = set(ids) & set(fare_ids)
print("Station ID (lines) == SRC_STATION_ID (fares)? overlapping ids:",
      len(id_match), "consistent names:",
      sum(1 for i in id_match if ids[i] == fare_ids[i]), "/", len(id_match))

print("\n== barrier_free_facilities ==")
stnos = sorted({int(r["Station_No"]) for r in fac})
print("unique Station_No:", len(stnos), "range:", stnos[0], "-", stnos[-1])
line_ids = {int(i) for i in ids if i.strip()}
print("Station_No overlap with lines Station ID:", len(set(stnos) & line_ids))
print("Station_No overlap with fares SRC_STATION_ID:", len(set(stnos) & {int(i) for i in fare_ids}))
item_by_code = {r["Item_Code"]: r["Facility_En"] for r in cats}
yj = Counter(r["Key"] for r in fac if r["Value"] == "Y")
print("Y-count per AJ item:")
for k in sorted(yj):
    if k.startswith("AJ") or k.startswith("HIn"):
        print(f"  {k:5s} {item_by_code.get(k, '?'):55s} {yj[k]}")
coords = [r for r in fac if r["Exit_Coordinate_X_Y"].strip()]
print("rows with exit coordinates:", len(coords), "of", len(fac))
for r in coords[:5]:
    print("  sample:", r["Station_No"], r["Key"], r["AJTextEn"], "->", r["Exit_Coordinate_X_Y"])

print("\n== station 117 profile (joined with category names) ==")
for r in fac:
    if r["Station_No"] == "117" and r["Value"] == "Y" and r["Key"] in item_by_code:
        tag = r["AJTextEn"] or "-"
        print(f"  {r['Key']:5s} {item_by_code[r['Key']]:50s} {tag}")

print("\n== light rail ==")
lr = load("light_rail_routes_and_stops.csv")
print("lines:", sorted({r["Line Code"] for r in lr}), "stops:", len({r["Stop Code"] for r in lr}))

print("\n== mtr bus ==")
br = load("mtr_bus_routes.csv")
bs = load("mtr_bus_stops.csv")
print("routes:", len({r["ROUTE_ID"] for r in br}), "stops:", len({r["STATION_ID"] for r in bs}))
