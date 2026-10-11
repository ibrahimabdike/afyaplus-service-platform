import json
import logging
import math
from pathlib import Path
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("afyaplus.logistics")
mcp = FastMCP("afyaplus-logistics")
DATA_PATH = Path(__file__).with_name("clinics.json")
with DATA_PATH.open(encoding="utf-8") as f:
    CLINICS = json.load(f)["clinics"]
VALID_ITEMS = {"amoxicillin", "ors_sachets", "malaria_kits"}
CLINIC_IDS = {c["id"] for c in CLINICS}

def distance_km(a: dict, b: dict) -> float:
    dx = (a["lon"] - b["lon"]) * 111.32 * math.cos(math.radians((a["lat"] + b["lat"]) / 2))
    dy = (a["lat"] - b["lat"]) * 110.57
    return round(math.hypot(dx, dy), 1)

@mcp.tool()
def check_stock(item: str) -> str:
    """Return stock levels and reorder flags for a supported medical supply.
    Valid item values: amoxicillin, ors_sachets, malaria_kits. Reorder is flagged below 10 units."""
    log.info("tool=check_stock item=%s", item)
    if item not in VALID_ITEMS:
        return json.dumps({"error": f"Unknown item '{item}'.", "valid_items": sorted(VALID_ITEMS)})
    rows = [{"clinic_id": c["id"], "clinic": c["name"], "county": c["county"],
             "units": c["stock"][item], "reorder_needed": c["stock"][item] < 10}
            for c in CLINICS]
    return json.dumps({"item": item, "stock": rows})

@mcp.tool()
def plan_delivery_route(start_clinic_id: str) -> str:
    """Plan an approximate route visiting every clinic from a valid start clinic.
    Uses a nearest-neighbour heuristic; the result is not guaranteed to be the shortest road route."""
    log.info("tool=plan_delivery_route start_clinic_id=%s", start_clinic_id)
    start = next((c for c in CLINICS if c["id"] == start_clinic_id), None)
    if start is None:
        return json.dumps({"error": f"Unknown clinic id '{start_clinic_id}'.",
                           "valid_clinic_ids": sorted(CLINIC_IDS)})
    route, remaining, total = [start], [c for c in CLINICS if c["id"] != start_clinic_id], 0.0
    while remaining:
        here = route[-1]
        nxt = min(remaining, key=lambda c: distance_km(here, c))
        total += distance_km(here, nxt)
        route.append(nxt)
        remaining.remove(nxt)
    return json.dumps({"route": [{"id": c["id"], "name": c["name"]} for c in route],
                       "approx_total_km": round(total, 1),
                       "method": "nearest-neighbour straight-line distance heuristic"})

@mcp.tool()
def get_delivery_eta(from_clinic_id: str, to_clinic_id: str) -> str:
    """Estimate distance and travel time between two valid clinic IDs at an assumed 40 km/h.
    This is a rough estimate and does not use live road or traffic data."""
    log.info("tool=get_delivery_eta from=%s to=%s", from_clinic_id, to_clinic_id)
    a = next((c for c in CLINICS if c["id"] == from_clinic_id), None)
    b = next((c for c in CLINICS if c["id"] == to_clinic_id), None)
    if a is None or b is None:
        return json.dumps({"error": "Unknown clinic id.",
                           "valid_clinic_ids": sorted(CLINIC_IDS)})
    km = distance_km(a, b)
    return json.dumps({"from": a["name"], "to": b["name"], "approx_km": km,
                       "eta_minutes_at_40_kmh": round(km / 40 * 60)})
@mcp.resource("clinics://directory")
def clinic_directory() -> str:
    """Read-only directory of AfyaPlus partner clinics and their IDs, names, and counties."""
    log.info("resource=clinic_directory")
    return json.dumps([{"id": c["id"], "name": c["name"], "county": c["county"]} for c in CLINICS])

if __name__ == "__main__":
    mcp.run()
