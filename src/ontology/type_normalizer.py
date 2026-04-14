import re
import unicodedata


def normalize_text(value: str) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )
    text = re.sub(r"[^a-z0-9\s\-_#/.:]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_uri(type_value: str) -> str:
    text = normalize_text(type_value)
    if not text:
        return ""

    if "#" in text:
        text = text.split("#")[-1]
    elif "/" in text:
        text = text.rstrip("/").split("/")[-1]

    return text


TYPE_EQUIVALENCES = {
    "accomodationestablishment": "accommodationestablishment",
    "culturecentre": "culturecenter",
    "exibitionhall": "exhibitionhall",
    "eductionalcenter": "educationalcenter",
    "foodestablisment": "foodestablishment",
    "townh": "townhall",

    "tourismentity": "place",
    "thing": "place",
    "location": "place",
    "concept": "place",

    "touristattractionsite": "touristattraction",
    "historicalorculturalresource": "touristattraction",
    "culturalheritage": "touristattraction",
    "tourismresource": "touristattraction",

    "tourismorrelatedfacility": "tourismservice",
    "eventattendancefacility": "event",
    "partyandentertainmentfacility": "event",

    "localbusiness": "organization",

    "passengertransportcompany": "transportinfrastructure",
    "publictransportstop": "transportinfrastructure",
    "vehiclerentalcompany": "transportinfrastructure",
    "privatehirecompany": "transportinfrastructure",

    "aparthotel": "accommodationestablishment",
    "hostel": "accommodationestablishment",
    "hotel": "accommodationestablishment",
    "residence": "accommodationestablishment",

    "restaurant": "foodestablishment",
}


def normalize_type(type_value: str) -> str:
    raw = strip_uri(type_value)
    if not raw:
        return ""

    mapped = TYPE_EQUIVALENCES.get(raw, raw)
    return mapped


def normalize_types(values) -> list[str]:
    if values is None:
        return []

    if not isinstance(values, list):
        values = [values]

    result = []
    seen = set()

    for value in values:
        t = normalize_type(value)
        if t and t not in seen:
            seen.add(t)
            result.append(t)

    return result