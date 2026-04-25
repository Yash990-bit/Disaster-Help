"""
City Graph — Agent 2 (Dispatcher) — SONIPAT EDITION
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()
ORS_API_KEY = os.getenv("ORS_API_KEY")

# ═══════════════════════════════════════════════════════════════════════════════
# Sonipat Coordinates (lon, lat)
# ═══════════════════════════════════════════════════════════════════════════════

COORDINATES = {
    "city_mall":        [77.0264, 28.9958], # Sonipat City Mall area
    "oak_avenue":       [77.0190, 28.9850],
    "sonipat_bus_stand":[77.0141, 28.9897],
    "atlas_chowk":      [77.0260, 28.9940],
    "fire_hq":          [77.0210, 28.9920],
    "hospital_north":   [77.0180, 29.0020],
    "police_hq":        [77.0150, 28.9980],
    "hazmat_depot":     [77.0300, 28.9800],
    "utility_yard":     [77.0050, 28.9850],
    "station_east":     [77.0400, 28.9900],
    "station_west":     [76.9900, 28.9900],
    "station_north":    [77.0200, 29.0100],
    "patrol_east":      [77.0450, 28.9950],
}

def calculate_travel_time(from_node: str, to_node: str) -> int:
    """
    Calculate real travel time in minutes using OpenRouteService API for Sonipat.
    Falls back to Haversine-based estimate if API fails or key is missing.
    """
    coords_from = COORDINATES.get(from_node)
    coords_to = COORDINATES.get(to_node)
    
    if not coords_from or not coords_to:
        return 15 # Default
    
    if from_node == to_node:
        return 0

    if ORS_API_KEY:
        try:
            url = f"https://api.openrouteservice.org/v2/directions/driving-car?api_key={ORS_API_KEY}&start={coords_from[0]},{coords_from[1]}&end={coords_to[0]},{coords_to[1]}"
            res = requests.get(url, timeout=5)
            data = res.json()
            # duration is in seconds
            seconds = data['features'][0]['properties']['summary']['duration']
            return max(1, int(seconds / 60))
        except Exception:
            pass # Fallback to estimate

    # Fallback: Simple distance-based estimate for Sonipat (~30km/h avg speed)
    import math
    lat1, lon1 = coords_from[1], coords_from[0]
    lat2, lon2 = coords_to[1], coords_to[0]
    dist = math.sqrt((lat2-lat1)**2 + (lon2-lon1)**2) * 111 # rough km
    time_mins = (dist / 30) * 60
    return max(2, int(time_mins))

def location_to_node(location_str: str) -> str:
    text = location_str.lower()
    if "bus stand" in text: return "sonipat_bus_stand"
    if "atlas chowk" in text: return "atlas_chowk"
    if "mall" in text: return "city_mall"
    if "oak" in text: return "oak_avenue"
    return "city_mall"
