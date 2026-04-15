from __future__ import annotations
import re
import unicodedata
from typing import Dict, Optional


class TypeNormalizer:
    def __init__(self):
        self.valid_types = {
            "Thing",
            "Place",
            "Organization",
            "Service",
            "Concept",
            "Event",
            "TouristAttraction",
            "Monument",
            "Museum",
            "Castle",
            "Alcazar",
            "Basilica",
            "Cathedral",
            "Church",
            "Chapel",
            "ArcheologicalSite",
            "HistoricalOrCulturalResource",
            "Square",
            "TownHall",
            "BullRing",
            "SportsCenter",
            "CultureCenter",
            "ExhibitionHall",
            "EducationalCenter",
            "DestinationExperience",
            "RetailAndFashion",
            "TourismService",
            "Accommodation",
            "AccommodationEstablishment",
            "FoodEstablishment",
            "TransportInfrastructure",
            "EventOrganisationCompany",
            "EventAttendanceFacility",
            "PublicService",
            "Stadium",
        }

        self.alias_map: Dict[str, str] = {
            "hotel": "AccommodationEstablishment",
            "hostel": "AccommodationEstablishment",
            "hostal": "AccommodationEstablishment",
            "apartamento turistico": "AccommodationEstablishment",
            "apartments": "AccommodationEstablishment",
            "restaurant": "FoodEstablishment",
            "restaurante": "FoodEstablishment",
            "bar": "FoodEstablishment",
            "cafeteria": "FoodEstablishment",
            "mercado gastronomico": "FoodEstablishment",
            "museum": "Museum",
            "museo": "Museum",
            "monument": "Monument",
            "monumento": "Monument",
            "castle": "Castle",
            "castillo": "Castle",
            "alcazar": "Alcazar",
            "basilica": "Basilica",
            "cathedral": "Cathedral",
            "catedral": "Cathedral",
            "church": "Church",
            "iglesia": "Church",
            "chapel": "Chapel",
            "capilla": "Chapel",
            "square": "Square",
            "plaza": "Square",
            "townhall": "TownHall",
            "ayuntamiento": "TownHall",
            "bullring": "BullRing",
            "plaza de toros": "BullRing",
            "sports center": "SportsCenter",
            "polideportivo": "SportsCenter",
            "culture center": "CultureCenter",
            "centro cultural": "CultureCenter",
            "exhibition hall": "ExhibitionHall",
            "sala de exposiciones": "ExhibitionHall",
            "educational center": "EducationalCenter",
            "academia": "EducationalCenter",
            "school": "EducationalCenter",
            "festival": "Event",
            "concierto": "Event",
            "evento": "Event",
            "destination experience": "DestinationExperience",
            "tourism service": "TourismService",
            "servicio turistico": "TourismService",
            "retail": "RetailAndFashion",
            "fashion": "RetailAndFashion",
            "shopping": "RetailAndFashion",
            "taxi": "TransportInfrastructure",
            "bus": "TransportInfrastructure",
            "train station": "TransportInfrastructure",
            "estacion": "TransportInfrastructure",
            "airport": "TransportInfrastructure",
            "public service": "PublicService",
            "parking": "PublicService",
            "aparcamiento": "PublicService",
            "stadium": "Stadium",
            "estadio": "Stadium",
            "event organisation company": "EventOrganisationCompany",
            "event organization company": "EventOrganisationCompany",
            "organizador de eventos": "EventOrganisationCompany",
        }

        self.parent_fallback: Dict[str, str] = {
            "Museum": "TouristAttraction",
            "Monument": "TouristAttraction",
            "Castle": "TouristAttraction",
            "Alcazar": "TouristAttraction",
            "Basilica": "TouristAttraction",
            "Cathedral": "TouristAttraction",
            "Church": "TouristAttraction",
            "Chapel": "TouristAttraction",
            "ArcheologicalSite": "TouristAttraction",
            "HistoricalOrCulturalResource": "TouristAttraction",
            "Square": "Place",
            "TownHall": "Place",
            "BullRing": "Place",
            "SportsCenter": "Place",
            "CultureCenter": "Place",
            "ExhibitionHall": "Place",
            "EducationalCenter": "Organization",
            "EventOrganisationCompany": "Organization",
            "AccommodationEstablishment": "Accommodation",
            "FoodEstablishment": "Service",
            "TourismService": "Service",
            "TransportInfrastructure": "Place",
            "PublicService": "Service",
            "Stadium": "Place",
        }

    def normalize(
        self,
        raw_type: Optional[str],
        *,
        allow_parent_fallback: bool = False,
        default: str = "Thing",
    ) -> str:
        if not raw_type:
            return default

        raw_type = raw_type.strip()
        if raw_type in self.valid_types:
            return raw_type

        key = self._normalize_text(raw_type)

        if key in self.alias_map:
            return self.alias_map[key]

        inferred = self._infer_from_text(key)
        if inferred:
            return inferred

        candidate = self._canonicalize_token(raw_type)
        if candidate in self.valid_types:
            return candidate

        if allow_parent_fallback and candidate in self.parent_fallback:
            return self.parent_fallback[candidate]

        return default

    def to_parent(self, cls: str) -> str:
        return self.parent_fallback.get(cls, cls)

    def is_specific(self, cls: str) -> bool:
        return cls not in {"Thing", "Place", "Organization", "Service", "Concept", "Accommodation"}

    def normalize_with_context(
        self,
        raw_type: Optional[str],
        entity_name: Optional[str] = None,
        page_text: Optional[str] = None,
        default: str = "Thing",
    ) -> str:
        t = self.normalize(raw_type, allow_parent_fallback=False, default=default)
        if t != "Thing":
            return t

        context = " ".join([
            entity_name or "",
            page_text or "",
        ])
        ctx = self._normalize_text(context)

        contextual_rules = [
            (r"\btaxi\b", "TransportInfrastructure"),
            (r"\bbus turistico\b", "TransportInfrastructure"),
            (r"\bautobus turistico\b", "TransportInfrastructure"),
            (r"\bfestival\b", "Event"),
            (r"\bconcierto\b", "Event"),
            (r"\bseminario\b", "Event"),
            (r"\bcongreso\b", "Event"),
            (r"\bhotel\b", "AccommodationEstablishment"),
            (r"\bhostal\b", "AccommodationEstablishment"),
            (r"\bapartamento\b", "AccommodationEstablishment"),
            (r"\brestaurante\b", "FoodEstablishment"),
            (r"\bcafeteria\b", "FoodEstablishment"),
            (r"\bmercado\b", "FoodEstablishment"),
            (r"\bacademia\b", "EducationalCenter"),
            (r"\bcolegio\b", "EducationalCenter"),
            (r"\bcentro cultural\b", "CultureCenter"),
            (r"\bsala de exposiciones\b", "ExhibitionHall"),
            (r"\bmuseo\b", "Museum"),
            (r"\bcastillo\b", "Castle"),
            (r"\balcazar\b", "Alcazar"),
            (r"\bcapilla\b", "Chapel"),
            (r"\bcatedral\b", "Cathedral"),
            (r"\biglesia\b", "Church"),
            (r"\bbasilica\b", "Basilica"),
            (r"\bplaza de toros\b", "BullRing"),
            (r"\baparcamiento\b", "PublicService"),
            (r"\bparking\b", "PublicService"),
            (r"\bestadio\b", "Stadium"),
        ]

        for pattern, cls in contextual_rules:
            if re.search(pattern, ctx):
                return cls

        return default

    def _infer_from_text(self, key: str) -> Optional[str]:
        ordered_keywords = [
            ("plaza de toros", "BullRing"),
            ("centro cultural", "CultureCenter"),
            ("sala de exposiciones", "ExhibitionHall"),
            ("bus turistico", "TransportInfrastructure"),
            ("autobus turistico", "TransportInfrastructure"),
            ("aparcamiento", "PublicService"),
            ("parking", "PublicService"),
            ("festival", "Event"),
            ("concierto", "Event"),
            ("evento", "Event"),
            ("hotel", "AccommodationEstablishment"),
            ("hostal", "AccommodationEstablishment"),
            ("restaurante", "FoodEstablishment"),
            ("cafeteria", "FoodEstablishment"),
            ("academia", "EducationalCenter"),
            ("museo", "Museum"),
            ("monumento", "Monument"),
            ("castillo", "Castle"),
            ("alcazar", "Alcazar"),
            ("basilica", "Basilica"),
            ("catedral", "Cathedral"),
            ("iglesia", "Church"),
            ("capilla", "Chapel"),
            ("plaza", "Square"),
            ("ayuntamiento", "TownHall"),
            ("taxi", "TransportInfrastructure"),
            ("estadio", "Stadium"),
        ]

        for kw, cls in ordered_keywords:
            if kw in key:
                return cls
        return None

    def _normalize_text(self, text: str) -> str:
        text = text.lower().strip()
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        text = re.sub(r"[_\-/]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _canonicalize_token(self, text: str) -> str:
        chunks = re.split(r"[_\-\s]+", text.strip())
        chunks = [c for c in chunks if c]
        return "".join(c[:1].upper() + c[1:] for c in chunks)


_DEFAULT_NORMALIZER = TypeNormalizer()

def normalize_type_name(
    raw_type: str | None,
    *,
    allow_parent_fallback: bool = False,
    default: str = "Thing",
) -> str:
    return _DEFAULT_NORMALIZER.normalize(
        raw_type,
        allow_parent_fallback=allow_parent_fallback,
        default=default,
    )