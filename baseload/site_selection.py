"""Site selection utilities."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class Site:
    """Simple container for a candidate site."""

    name: str
    latitude: float
    longitude: float

    def as_dict(self) -> dict:
        return {"name": self.name, "latitude": self.latitude, "longitude": self.longitude}


# Curated list of land-based coordinates spanning the globe
CANDIDATE_COORDINATES = [
    ("Anchorage, USA", 61.2181, -149.9003),
    ("Honolulu, USA", 21.3069, -157.8583),
    ("San Francisco, USA", 37.7749, -122.4194),
    ("Los Angeles, USA", 34.0522, -118.2437),
    ("Mexico City, Mexico", 19.4326, -99.1332),
    ("Bogotá, Colombia", 4.7110, -74.0721),
    ("Lima, Peru", -12.0464, -77.0428),
    ("Santiago, Chile", -33.4489, -70.6693),
    ("Buenos Aires, Argentina", -34.6037, -58.3816),
    ("São Paulo, Brazil", -23.5505, -46.6333),
    ("Recife, Brazil", -8.0476, -34.8770),
    ("New York, USA", 40.7128, -74.0060),
    ("Miami, USA", 25.7617, -80.1918),
    ("Reykjavík, Iceland", 64.1466, -21.9426),
    ("Dublin, Ireland", 53.3498, -6.2603),
    ("London, United Kingdom", 51.5074, -0.1278),
    ("Madrid, Spain", 40.4168, -3.7038),
    ("Paris, France", 48.8566, 2.3522),
    ("Berlin, Germany", 52.5200, 13.4050),
    ("Rome, Italy", 41.9028, 12.4964),
    ("Athens, Greece", 37.9838, 23.7275),
    ("Helsinki, Finland", 60.1699, 24.9384),
    ("Moscow, Russia", 55.7558, 37.6173),
    ("Cairo, Egypt", 30.0444, 31.2357),
    ("Casablanca, Morocco", 33.5731, -7.5898),
    ("Lagos, Nigeria", 6.5244, 3.3792),
    ("Accra, Ghana", 5.6037, -0.1870),
    ("Nairobi, Kenya", -1.2921, 36.8219),
    ("Addis Ababa, Ethiopia", 8.9806, 38.7578),
    ("Johannesburg, South Africa", -26.2041, 28.0473),
    ("Cape Town, South Africa", -33.9249, 18.4241),
    ("Riyadh, Saudi Arabia", 24.7136, 46.6753),
    ("Dubai, UAE", 25.2048, 55.2708),
    ("Tehran, Iran", 35.6892, 51.3890),
    ("Karachi, Pakistan", 24.8607, 67.0011),
    ("Delhi, India", 28.7041, 77.1025),
    ("Mumbai, India", 19.0760, 72.8777),
    ("Bengaluru, India", 12.9716, 77.5946),
    ("Bangkok, Thailand", 13.7563, 100.5018),
    ("Hanoi, Vietnam", 21.0278, 105.8342),
    ("Singapore", 1.3521, 103.8198),
    ("Jakarta, Indonesia", -6.2088, 106.8456),
    ("Manila, Philippines", 14.5995, 120.9842),
    ("Beijing, China", 39.9042, 116.4074),
    ("Shanghai, China", 31.2304, 121.4737),
    ("Seoul, South Korea", 37.5665, 126.9780),
    ("Tokyo, Japan", 35.6762, 139.6503),
    ("Osaka, Japan", 34.6937, 135.5023),
    ("Sydney, Australia", -33.8688, 151.2093),
    ("Melbourne, Australia", -37.8136, 144.9631),
    ("Perth, Australia", -31.9505, 115.8605),
    ("Darwin, Australia", -12.4634, 130.8456),
    ("Auckland, New Zealand", -36.8485, 174.7633),
    ("Christchurch, New Zealand", -43.5321, 172.6362),
]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometers."""

    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def generate_candidate_sites(seed: int | None = None) -> List[Site]:
    """Return a shuffled list of curated land-based sites."""

    rng = random.Random(seed)
    candidates = [Site(name=name, latitude=lat, longitude=lon) for name, lat, lon in CANDIDATE_COORDINATES]
    rng.shuffle(candidates)
    return candidates


def select_sites(sites: Iterable[Site], n: int) -> List[Site]:
    """Select *n* sites that are maximally spread out using greedy farthest-point sampling."""

    pool = list(sites)
    if len(pool) < n:
        raise ValueError("Candidate pool smaller than requested number of sites")
    selected: List[Site] = [pool[0]]
    remaining = pool[1:]
    while len(selected) < n:
        max_site = None
        max_distance = -1.0
        for candidate in remaining:
            min_distance = min(
                haversine_distance(candidate.latitude, candidate.longitude, s.latitude, s.longitude)
                for s in selected
            )
            if min_distance > max_distance:
                max_distance = min_distance
                max_site = candidate
        if max_site is None:
            break
        selected.append(max_site)
        remaining.remove(max_site)
    normalized = []
    for i, s in enumerate(selected):
        safe_name = s.name.replace(" ", "_").replace(",", "")
        normalized.append(Site(name=f"site_{i+1}_{safe_name}", latitude=s.latitude, longitude=s.longitude))
    return normalized


def generate_sites(n: int, seed: int | None = None) -> List[Site]:
    candidates = generate_candidate_sites(seed=seed)
    return select_sites(candidates, n)

