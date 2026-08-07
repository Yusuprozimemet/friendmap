"""Static NL gazetteer.

A local table beats a geocoding API here: no key, no rate limit, no network in
the hot path, and identical results every run. ~130 places covers this
subreddit comfortably — it's people naming where they live, not arbitrary
addresses.

Province centroids are copied verbatim from the design so province-level pins
land exactly where the mockup put them.
"""
from __future__ import annotations

import re
import unicodedata

PROVINCE_CENTROIDS: dict[str, tuple[float, float]] = {
    "Noord-Holland": (52.60, 4.80),
    "Zuid-Holland": (52.00, 4.50),
    "Utrecht": (52.10, 5.15),
    "Noord-Brabant": (51.55, 5.20),
    "Gelderland": (52.05, 5.90),
    "Overijssel": (52.45, 6.40),
    "Limburg": (51.25, 5.90),
    "Groningen": (53.25, 6.70),
    "Friesland": (53.10, 5.80),
    "Drenthe": (52.85, 6.60),
    "Flevoland": (52.50, 5.60),
    "Zeeland": (51.45, 3.85),
}

PROVINCE_ALIASES: dict[str, str] = {
    "nh": "Noord-Holland", "n-h": "Noord-Holland", "noord holland": "Noord-Holland",
    "north holland": "Noord-Holland",
    "zh": "Zuid-Holland", "z-h": "Zuid-Holland", "zuid holland": "Zuid-Holland",
    "south holland": "Zuid-Holland",
    "nb": "Noord-Brabant", "brabant": "Noord-Brabant", "noord brabant": "Noord-Brabant",
    "north brabant": "Noord-Brabant", "north-brabant": "Noord-Brabant",
    # English hyphenated forms turn up often in the English-language posts. The
    # unhyphenated spellings are already covered — above, and by the
    # hyphen-flattened variant `_keys` indexes for every entry.
    "north-holland": "Noord-Holland", "south-holland": "Zuid-Holland",
    "fryslan": "Friesland", "frysland": "Friesland", "friesland": "Friesland",
    "gelderland": "Gelderland", "gelre": "Gelderland",
    "overijsel": "Overijssel",
    "zeeuws-vlaanderen": "Zeeland",
    "twente": "Overijssel",
    "achterhoek": "Gelderland",
    "veluwe": "Gelderland",
    "kempen": "Noord-Brabant",
}

# name -> (lat, lon, province)
CITIES: dict[str, tuple[float, float, str]] = {
    # Noord-Holland
    "Amsterdam": (52.3676, 4.9041, "Noord-Holland"),
    "Haarlem": (52.3874, 4.6462, "Noord-Holland"),
    "Zaandam": (52.4389, 4.8267, "Noord-Holland"),
    "Zaanstad": (52.4440, 4.8290, "Noord-Holland"),
    "Alkmaar": (52.6324, 4.7534, "Noord-Holland"),
    "Hoorn": (52.6425, 5.0597, "Noord-Holland"),
    "Purmerend": (52.5050, 4.9592, "Noord-Holland"),
    "Hilversum": (52.2292, 5.1669, "Noord-Holland"),
    "Amstelveen": (52.3114, 4.8701, "Noord-Holland"),
    "Haarlemmermeer": (52.3008, 4.6906, "Noord-Holland"),
    "Hoofddorp": (52.3061, 4.6907, "Noord-Holland"),
    "Den Helder": (52.9563, 4.7601, "Noord-Holland"),
    "Heerhugowaard": (52.6700, 4.8300, "Noord-Holland"),
    "Beverwijk": (52.4839, 4.6567, "Noord-Holland"),
    "Velsen": (52.4600, 4.6600, "Noord-Holland"),
    "IJmuiden": (52.4580, 4.6100, "Noord-Holland"),
    "Bussum": (52.2800, 5.1600, "Noord-Holland"),
    "Weesp": (52.3080, 5.0420, "Noord-Holland"),
    "Castricum": (52.5470, 4.6690, "Noord-Holland"),
    "Texel": (53.0550, 4.7970, "Noord-Holland"),
    "Laren": (52.2570, 5.2260, "Noord-Holland"),
    "Schagen": (52.7880, 4.7970, "Noord-Holland"),
    "Hoorn NH": (52.6425, 5.0597, "Noord-Holland"),
    "Huizen": (52.2990, 5.2410, "Noord-Holland"),
    "Wormerveer": (52.4920, 4.7920, "Noord-Holland"),
    "Volendam": (52.4940, 5.0700, "Noord-Holland"),
    # Zuid-Holland
    "Rotterdam": (51.9244, 4.4777, "Zuid-Holland"),
    "Den Haag": (52.0705, 4.3007, "Zuid-Holland"),
    "Leiden": (52.1601, 4.4970, "Zuid-Holland"),
    "Delft": (52.0116, 4.3571, "Zuid-Holland"),
    "Dordrecht": (51.8133, 4.6901, "Zuid-Holland"),
    "Zoetermeer": (52.0574, 4.4940, "Zuid-Holland"),
    "Gouda": (52.0116, 4.7105, "Zuid-Holland"),
    "Schiedam": (51.9190, 4.3880, "Zuid-Holland"),
    "Vlaardingen": (51.9120, 4.3410, "Zuid-Holland"),
    "Spijkenisse": (51.8450, 4.3290, "Zuid-Holland"),
    "Capelle aan den IJssel": (51.9300, 4.5770, "Zuid-Holland"),
    "Alphen aan den Rijn": (52.1290, 4.6570, "Zuid-Holland"),
    "Katwijk": (52.2030, 4.3990, "Zuid-Holland"),
    "Rijswijk": (52.0360, 4.3250, "Zuid-Holland"),
    "Leidschendam": (52.0900, 4.3930, "Zuid-Holland"),
    "Naaldwijk": (51.9930, 4.2100, "Zuid-Holland"),
    "Ridderkerk": (51.8720, 4.6020, "Zuid-Holland"),
    "Barendrecht": (51.8560, 4.5350, "Zuid-Holland"),
    "Gorinchem": (51.8370, 4.9750, "Zuid-Holland"),
    "Zwijndrecht": (51.8180, 4.6390, "Zuid-Holland"),
    # Utrecht
    "Utrecht": (52.0907, 5.1214, "Utrecht"),
    "Amersfoort": (52.1561, 5.3878, "Utrecht"),
    "Veenendaal": (52.0290, 5.5540, "Utrecht"),
    "Nieuwegein": (52.0290, 5.0800, "Utrecht"),
    "Zeist": (52.0900, 5.2330, "Utrecht"),
    "Houten": (52.0290, 5.1680, "Utrecht"),
    "Woerden": (52.0850, 4.8830, "Utrecht"),
    "Soest": (52.1740, 5.2920, "Utrecht"),
    # Noord-Brabant
    "Eindhoven": (51.4416, 5.4697, "Noord-Brabant"),
    "Tilburg": (51.5555, 5.0913, "Noord-Brabant"),
    "Breda": (51.5719, 4.7683, "Noord-Brabant"),
    "'s-Hertogenbosch": (51.6978, 5.3037, "Noord-Brabant"),
    "Helmond": (51.4793, 5.6570, "Noord-Brabant"),
    "Roosendaal": (51.5308, 4.4653, "Noord-Brabant"),
    "Oss": (51.7650, 5.5180, "Noord-Brabant"),
    "Bergen op Zoom": (51.4940, 4.2870, "Noord-Brabant"),
    "Waalwijk": (51.6870, 5.0700, "Noord-Brabant"),
    "Oosterhout": (51.6450, 4.8600, "Noord-Brabant"),
    "Veldhoven": (51.4190, 5.4040, "Noord-Brabant"),
    "Uden": (51.6600, 5.6180, "Noord-Brabant"),
    "Etten-Leur": (51.5710, 4.6370, "Noord-Brabant"),
    "Best": (51.5070, 5.3900, "Noord-Brabant"),
    "Valkenswaard": (51.3500, 5.4600, "Noord-Brabant"),
    "Tiel": (51.8870, 5.4290, "Gelderland"),
    # Gelderland
    "Nijmegen": (51.8426, 5.8528, "Gelderland"),
    "Arnhem": (51.9851, 5.8987, "Gelderland"),
    "Apeldoorn": (52.2112, 5.9699, "Gelderland"),
    "Ede": (52.0400, 5.6660, "Gelderland"),
    "Doetinchem": (51.9650, 6.2880, "Gelderland"),
    "Harderwijk": (52.3410, 5.6210, "Gelderland"),
    "Zutphen": (52.1400, 6.2010, "Gelderland"),
    "Wageningen": (51.9640, 5.6650, "Gelderland"),
    "Barneveld": (52.1400, 5.5840, "Gelderland"),
    "Culemborg": (51.9550, 5.2280, "Gelderland"),
    "Winterswijk": (51.9720, 6.7190, "Gelderland"),
    # Overijssel
    "Enschede": (52.2215, 6.8937, "Overijssel"),
    "Zwolle": (52.5168, 6.0830, "Overijssel"),
    "Deventer": (52.2551, 6.1639, "Overijssel"),
    "Hengelo": (52.2653, 6.7930, "Overijssel"),
    "Almelo": (52.3570, 6.6620, "Overijssel"),
    "Kampen": (52.5550, 5.9110, "Overijssel"),
    "Oldenzaal": (52.3130, 6.9280, "Overijssel"),
    # Limburg
    "Maastricht": (50.8514, 5.6910, "Limburg"),
    "Venlo": (51.3704, 6.1724, "Limburg"),
    "Sittard": (50.9980, 5.8690, "Limburg"),
    "Heerlen": (50.8880, 5.9795, "Limburg"),
    "Roermond": (51.1942, 5.9870, "Limburg"),
    "Geleen": (50.9720, 5.8290, "Limburg"),
    "Weert": (51.2510, 5.7060, "Limburg"),
    "Kerkrade": (50.8660, 6.0620, "Limburg"),
    # Groningen
    "Groningen": (53.2194, 6.5665, "Groningen"),
    "Delfzijl": (53.3300, 6.9200, "Groningen"),
    "Veendam": (53.1060, 6.8760, "Groningen"),
    "Hoogezand": (53.1620, 6.7580, "Groningen"),
    "Winschoten": (53.1440, 7.0350, "Groningen"),
    # Friesland
    "Leeuwarden": (53.2012, 5.7999, "Friesland"),
    "Drachten": (53.1120, 6.0990, "Friesland"),
    "Sneek": (53.0330, 5.6580, "Friesland"),
    "Heerenveen": (52.9600, 5.9190, "Friesland"),
    "Harlingen": (53.1740, 5.4210, "Friesland"),
    "Dokkum": (53.3250, 5.9970, "Friesland"),
    # Drenthe
    "Assen": (52.9925, 6.5649, "Drenthe"),
    "Emmen": (52.7850, 6.8970, "Drenthe"),
    "Hoogeveen": (52.7220, 6.4770, "Drenthe"),
    "Meppel": (52.6960, 6.1940, "Drenthe"),
    "Coevorden": (52.6620, 6.7420, "Drenthe"),
    # Flevoland
    "Almere": (52.3708, 5.2158, "Flevoland"),
    "Lelystad": (52.5185, 5.4714, "Flevoland"),
    "Emmeloord": (52.7100, 5.7480, "Flevoland"),
    "Dronten": (52.5250, 5.7180, "Flevoland"),
    # Zeeland
    "Middelburg": (51.4988, 3.6136, "Zeeland"),
    "Vlissingen": (51.4426, 3.5736, "Zeeland"),
    "Goes": (51.5040, 3.8880, "Zeeland"),
    "Terneuzen": (51.3350, 3.8280, "Zeeland"),
    "Zierikzee": (51.6500, 3.9190, "Zeeland"),
    # Added after auditing unresolved location strings from the full backfill.
    "Wassenaar": (52.1450, 4.4020, "Zuid-Holland"),
    "Landgraaf": (50.9010, 6.0200, "Limburg"),
    "Heythuysen": (51.2500, 5.9200, "Limburg"),
    "Appingedam": (53.3210, 6.8590, "Groningen"),
    "Noordoostpolder": (52.7100, 5.7480, "Flevoland"),
    "Oldambt": (53.1440, 7.0350, "Groningen"),
    "De Kwakel": (52.2400, 4.7700, "Noord-Holland"),
    "Uithoorn": (52.2390, 4.8250, "Noord-Holland"),
}

# Common alternate spellings people actually use in posts.
CITY_ALIASES: dict[str, str] = {
    "den bosch": "'s-Hertogenbosch",
    "s-hertogenbosch": "'s-Hertogenbosch",
    "shertogenbosch": "'s-Hertogenbosch",
    "den haag": "Den Haag",
    "the hague": "Den Haag",
    "s-gravenhage": "Den Haag",
    "gravenhage": "Den Haag",
    "adam": "Amsterdam",
    "rdam": "Rotterdam",
    "mokum": "Amsterdam",
    "010": "Rotterdam",
    "020": "Amsterdam",
    "070": "Den Haag",
    "040": "Eindhoven",
    "013": "Tilburg",
    "ijburg": "Amsterdam",
    "zeeburgereiland": "Amsterdam",
    "amsterdam zuidoost": "Amsterdam",
    "zaanstreek": "Zaandam",
    "eindhoven region": "Eindhoven",
    "regio eindhoven": "Eindhoven",
    "leiderdorp": "Leiden",
    "maastricht region": "Maastricht",
    "brainport": "Eindhoven",
}


def normalize(text: str) -> str:
    """Casefold + strip accents/punctuation so lookups are forgiving.

    Unwanted characters become spaces rather than vanishing, so "Sittard/Maastricht"
    doesn't collapse into one nonsense token. Apostrophes and hyphens survive
    because 's-Hertogenbosch and Noord-Holland need them.
    """
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9' -]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


# Splits a raw location into candidate place names: punctuation and the Dutch/
# English filler words people put between them ("ergens in Friesland").
_SPLIT = re.compile(
    r"[,/()|]|\b(?:in|near|omgeving|rondom|regio|region|uit|bij|around|of)\b",
    re.IGNORECASE,
)


def _keys(name: str) -> list[str]:
    """Lookup keys for a place, including a hyphen-insensitive variant.

    People write "Bergen-op-Zoom" as often as "Bergen op Zoom", and
    "Noord-Holland" as "Noord Holland" — indexing both spellings is cheaper
    than guessing at match time.
    """
    key = normalize(name)
    variants = [key]
    if "-" in key:
        variants.append(re.sub(r"\s+", " ", key.replace("-", " ")).strip())
    return variants


def _build_index(source: dict[str, str]) -> dict[str, str]:
    index: dict[str, str] = {}
    for raw, canonical in source.items():
        for key in _keys(raw):
            index.setdefault(key, canonical)
    return index


_CITY_INDEX = _build_index({name: name for name in CITIES})
_CITY_INDEX.update(_build_index(CITY_ALIASES))
_PROVINCE_INDEX = _build_index({name: name for name in PROVINCE_CENTROIDS})
_PROVINCE_INDEX.update(_build_index(PROVINCE_ALIASES))


def _match(key: str, index: dict[str, str]) -> str | None:
    """Index lookup that also tries the hyphen-flattened spelling of the query.

    Indexing both spellings of stored names isn't enough on its own — the query
    can carry hyphens the canonical name doesn't ("Bergen-op-Zoom").
    """
    if key in index:
        return index[key]
    flat = re.sub(r"\s+", " ", key.replace("-", " ")).strip()
    return index.get(flat)


def lookup(raw: str | None) -> tuple[str, str | None, str | None]:
    """Resolve a free-text location to (precision, city, province).

    precision is one of city / province / country / none. Anything we can't
    place stays 'none' rather than being guessed at — an unplaced person shows
    in the unplaced tray, which is honest, instead of on a wrong pin.
    """
    if not raw:
        return "none", None, None

    key = normalize(raw)
    if not key:
        return "none", None, None

    city = _match(key, _CITY_INDEX)
    if city:
        return "city", city, CITIES[city][2]
    province = _match(key, _PROVINCE_INDEX)
    if province:
        return "province", None, province
    if key in {"netherlands", "nederland", "nl", "holland", "the netherlands"}:
        return "country", None, None

    # "Zaandam, Noord-Holland" / "Sittard/Maastricht" — try each fragment.
    # Split the raw text, not the normalized key, so separators still exist.
    parts = [normalize(p) for p in _SPLIT.split(raw) if p and p.strip()]
    parts = [p for p in parts if p]
    for part in parts:
        city = _match(part, _CITY_INDEX)
        if city:
            return "city", city, CITIES[city][2]
    for part in parts:
        province = _match(part, _PROVINCE_INDEX)
        if province:
            return "province", None, province

    # Last resort: a known place name appearing anywhere in the string.
    for name, canonical in _CITY_INDEX.items():
        if len(name) > 4 and re.search(rf"\b{re.escape(name)}\b", key):
            return "city", canonical, CITIES[canonical][2]
    for name, canonical in _PROVINCE_INDEX.items():
        if len(name) > 4 and re.search(rf"\b{re.escape(name)}\b", key):
            return "province", None, canonical

    return "none", None, None


def coords(city: str | None, province: str | None) -> tuple[float, float] | None:
    if city and city in CITIES:
        lat, lon, _ = CITIES[city]
        return lat, lon
    if province and province in PROVINCE_CENTROIDS:
        return PROVINCE_CENTROIDS[province]
    return None


def all_places() -> list[dict]:
    """Rows for seeding the `places` table."""
    rows = [
        {"name": name, "kind": "city", "province": prov, "lat": lat, "lon": lon}
        for name, (lat, lon, prov) in CITIES.items()
    ]
    rows += [
        {"name": name, "kind": "province", "province": name, "lat": lat, "lon": lon}
        for name, (lat, lon) in PROVINCE_CENTROIDS.items()
    ]
    return rows
