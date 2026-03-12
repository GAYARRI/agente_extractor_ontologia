import re
import numpy as np
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer


class EntityTypeResolver:
    def __init__(self, ontology_classes):
        """
        ontology_classes:
        {
            "Beach": {
                "label": "Beach",
                "description": "...",
                "aliases": [...]
            },
            ...
        }
        """
        self.ontology_classes = ontology_classes
        self.class_names = list(ontology_classes.keys())
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self.class_profiles = []
        for cname in self.class_names:
            data = ontology_classes[cname]
            parts = [data.get("label", cname)]

            if data.get("description"):
                parts.append(data["description"])

            if data.get("aliases"):
                parts.extend(data["aliases"])

            profile = " ".join([p for p in parts if p])
            self.class_profiles.append(profile)

        self.class_embeddings = self.model.encode(self.class_profiles)

        # pistas simples por URL / texto / propiedades
        self.url_keyword_map = {
            "playa": ["Beach", "Cove"],
            "playas": ["Beach", "Cove"],
            "museo": ["Museum"],
            "museos": ["Museum"],
            "hotel": ["Hotel"],
            "hoteles": ["Hotel"],
            "restaurante": ["Restaurant"],
            "restaurantes": ["Restaurant"],
            "puerto": ["YatchingPort", "PortPassengerTerminal"],
            "puertos": ["YatchingPort", "PortPassengerTerminal"],
            "golf": ["GolfCourse"],
            "dunas": ["TouristAttractionSite", "Place"],
            "palacio": ["Palace"],
            "parque": ["AmusementPark", "Garden", "Place"],
            "naturaleza": ["TouristAttractionSite", "Place"],
            "rutas": ["Route", "Trail"],
            "senderos": ["Trail"],
            "playground": ["Playground"],
        }

        self.property_hint_map = {
            "telephone": ["LocalBusiness", "TourismEntity", "TourismService", "Place"],
            "openingHours": ["LocalBusiness", "Museum", "Restaurant", "Hotel", "TourismService"],
            "latitude": ["Place", "TourismDestination", "TouristAttractionSite", "Beach", "Cove"],
            "longitude": ["Place", "TourismDestination", "TouristAttractionSite", "Beach", "Cove"],
            "image": ["TourismEntity", "TouristAttractionSite", "Place"],
            "address": ["Hotel", "Restaurant", "Museum", "LocalBusiness", "Place"],
        }

    def _safe_text(self, text):
        if not text:
            return ""
        return " ".join(str(text).strip().split())

    def _cosine_scores(self, text):
        text = self._safe_text(text)
        if not text:
            return np.zeros(len(self.class_names))

        emb = self.model.encode([text])[0]
        scores = np.dot(self.class_embeddings, emb)
        return scores

    def _mention_scores(self, mention):
        mention = self._safe_text(mention)
        semantic = self._cosine_scores(mention)

        lexical = []
        for cname in self.class_names:
            lexical.append(
                fuzz.token_set_ratio(mention.lower(), cname.lower()) / 100.0
            )
        lexical = np.array(lexical)

        return 0.75 * semantic + 0.25 * lexical

    def _context_scores(self, context):
        return self._cosine_scores(context)

    def _description_scores(self, description):
        return self._cosine_scores(description)

    def _url_scores(self, url):
        url = self._safe_text(url).lower()
        scores = np.zeros(len(self.class_names))

        if not url:
            return scores

        for keyword, candidate_classes in self.url_keyword_map.items():
            if keyword in url:
                for c in candidate_classes:
                    if c in self.class_names:
                        idx = self.class_names.index(c)
                        scores[idx] += 1.0

        if scores.max() > 0:
            scores = scores / scores.max()

        return scores

    def _property_scores(self, properties):
        scores = np.zeros(len(self.class_names))

        if not properties:
            return scores

        for prop_name, prop_value in properties.items():
            if prop_value in [None, ""]:
                continue

            hinted_classes = self.property_hint_map.get(prop_name, [])
            for c in hinted_classes:
                if c in self.class_names:
                    idx = self.class_names.index(c)
                    scores[idx] += 1.0

        if scores.max() > 0:
            scores = scores / scores.max()

        return scores

    def _ontology_prior_scores(self, mention, description, url):
        """
        Regla ligera para empujar clases plausibles según palabras fuertes.
        """
        text = f"{self._safe_text(mention)} {self._safe_text(description)} {self._safe_text(url)}".lower()
        scores = np.zeros(len(self.class_names))

        keyword_rules = {
            "playa": ["Beach", "Cove"],
            "arena": ["Beach", "Cove"],
            "baño": ["Beach"],
            "oleaje": ["Beach", "Cove"],
            "museo": ["Museum"],
            "exposición": ["Museum", "ArtGallery"],
            "colección": ["Museum"],
            "hotel": ["Hotel"],
            "alojamiento": ["Hotel", "Hostel", "Resort"],
            "habitación": ["Hotel", "Hostel", "Resort"],
            "restaurante": ["Restaurant"],
            "gastronom": ["Restaurant", "FoodEstablishment"],
            "carta": ["Restaurant"],
            "puerto": ["YatchingPort", "PortPassengerTerminal"],
            "deportivo": ["YatchingPort"],
            "sendero": ["Trail", "Route"],
            "ruta": ["Route", "Trail"],
            "dunas": ["TouristAttractionSite", "Place"],
            "faro": ["Tower", "TouristAttractionSite"],
            "palacio": ["Palace"],
            "jardín": ["Garden"],
            "parque": ["Garden", "AmusementPark", "Place"],
        }

        for kw, candidate_classes in keyword_rules.items():
            if kw in text:
                for c in candidate_classes:
                    if c in self.class_names:
                        idx = self.class_names.index(c)
                        scores[idx] += 1.0

        if scores.max() > 0:
            scores = scores / scores.max()

        return scores

    def resolve(self, mention, context="", description="", url="", properties=None, top_k=5):
        properties = properties or {}

        mention_scores = self._mention_scores(mention)
        context_scores = self._context_scores(context)
        description_scores = self._description_scores(description)
        url_scores = self._url_scores(url)
        property_scores = self._property_scores(properties)
        ontology_scores = self._ontology_prior_scores(mention, description, url)

        final_scores = (
            0.20 * mention_scores +
            0.20 * context_scores +
            0.20 * description_scores +
            0.15 * url_scores +
            0.10 * property_scores +
            0.15 * ontology_scores
        )

        best_idx = int(np.argmax(final_scores))
        best_class = self.class_names[best_idx]
        best_score = float(final_scores[best_idx])

        ranked_idx = np.argsort(final_scores)[::-1][:top_k]
        top_candidates = [
            {
                "class": self.class_names[i],
                "score": float(final_scores[i]),
            }
            for i in ranked_idx
        ]

        return {
            "class": best_class,
            "confidence": best_score,
            "scores": {
                "mention": float(mention_scores[best_idx]),
                "context": float(context_scores[best_idx]),
                "description": float(description_scores[best_idx]),
                "url": float(url_scores[best_idx]),
                "properties": float(property_scores[best_idx]),
                "ontology_prior": float(ontology_scores[best_idx]),
            },
            "top_candidates": top_candidates,
        }