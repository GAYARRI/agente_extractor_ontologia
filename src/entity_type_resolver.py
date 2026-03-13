import numpy as np
from sentence_transformers import SentenceTransformer


class EntityTypeResolver:

    def __init__(self, class_names):

        # si vienen como dict desde la ontología, convertir a lista
        if isinstance(class_names, dict):
            class_names = list(class_names.keys())

        # asegurar que todo es string
        
        class_names = [c.split("/")[-1] for c in class_names]

        self.class_names = class_names
            

        print("Cargando modelo de embeddings...")

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        # --------------------------------------------------
        # EMBEDDINGS DE CLASES
        # --------------------------------------------------

        print("Generando embeddings de clases ontológicas...")

        self.class_embeddings = self.model.encode(
            self.class_names,
            normalize_embeddings=True
        )
        # --------------------------------------------------
        # CACHE DE EMBEDDINGS DE BLOQUES
        # --------------------------------------------------

        self.block_cache = {}


        # --------------------------------------------------
        # CACHE DE BLOQUES
        # --------------------------------------------------

        self.block_cache = {}

        # --------------------------------------------------
        # CLASES PERMITIDAS (dominio turismo)
        # --------------------------------------------------

        self.allowed_classes = {
            "Place",
            "TourismDestination",
            "TouristAttractionSite",
            "Beach",
            "Cove",
            "Trail",
            "TrailMTB",
            "Valley",
            "Garden",
            "Route",
            "Event",
            "Square",
            "Palace",
            "Museum",
            "Hotel",
            "Restaurant",
            "YatchingPort",
            "PortPassengerTerminal",
            "Mountain",
            "Forest",
            "River",
            "Lake",
            "Monument",
            "Church",
            "Castle",
            "Park",
        }

    # --------------------------------------------------
    # SAFE TEXT
    # --------------------------------------------------

    def _safe_text(self, text):

        if not text:
            return ""

        return text.strip()

    # --------------------------------------------------
    # EMBEDDING
    # --------------------------------------------------

    def _embed(self, text):

        text = self._safe_text(text)

        if not text:
            return np.zeros(len(self.class_names))

        emb = self.model.encode(
            text,
            normalize_embeddings=True
        )

        return emb

    # --------------------------------------------------
    # RESOLVE
    # --------------------------------------------------

    def resolve(
        self,
        mention,
        context="",
        description="",
        url="",
        properties=None,
        block_text=""
    ):

        mention = self._safe_text(mention)
        context = self._safe_text(context)
        description = self._safe_text(description)
        block_text = self._safe_text(block_text)

        if properties is None:
            properties = {}

        # --------------------------------------------------
        # EMBEDDINGS
        # --------------------------------------------------

        mention_emb = self._embed(mention)
        context_emb = self._embed(context)
        description_emb = self._embed(description)



        # --------------------------------------------------
        # BLOCK EMBEDDING CON CACHE
        # --------------------------------------------------

        if block_text in self.block_cache:

            block_emb = self.block_cache[block_text]

        else:

            block_emb = self.model.encode(
                block_text,
                normalize_embeddings=True
            )

            self.block_cache[block_text] = block_emb

        # limitar tamaño de cache
        if len(self.block_cache) > 5000:
            self.block_cache.clear()

            

        # --------------------------------------------------
        # SIMILARIDADES
        # --------------------------------------------------

        mention_scores = np.dot(self.class_embeddings, mention_emb)

        context_scores = np.dot(self.class_embeddings, context_emb)

        description_scores = np.dot(self.class_embeddings, description_emb)

        block_scores = np.dot(self.class_embeddings, block_emb)

        # --------------------------------------------------
        # URL SIGNAL
        # --------------------------------------------------

        url_scores = np.zeros(len(self.class_names))

        url_lower = url.lower()

        for i, cname in enumerate(self.class_names):

            if cname.lower() in url_lower:
                url_scores[i] = 1.0

        # --------------------------------------------------
        # PROPERTY SIGNAL
        # --------------------------------------------------

        property_scores = np.zeros(len(self.class_names))

        if "telephone" in properties:
            for i, cname in enumerate(self.class_names):
                if cname in {"Hotel", "Restaurant"}:
                    property_scores[i] += 0.5

        if "openingHours" in properties:
            for i, cname in enumerate(self.class_names):
                if cname in {"Restaurant", "Museum"}:
                    property_scores[i] += 0.5

        if "latitude" in properties:
            for i, cname in enumerate(self.class_names):
                if cname in {"Place", "TouristAttractionSite"}:
                    property_scores[i] += 0.4

        # --------------------------------------------------
        # ONTOLOGY PRIOR
        # --------------------------------------------------

        ontology_scores = np.zeros(len(self.class_names))

        for i, cname in enumerate(self.class_names):

            if cname in {
                "Place",
                "TourismDestination",
                "TouristAttractionSite",
            }:
                ontology_scores[i] += 0.1

        # --------------------------------------------------
        # COMBINACIÓN FINAL
        # --------------------------------------------------

        final_scores = (
            0.15 * mention_scores +
            0.15 * context_scores +
            0.15 * description_scores +
            0.10 * url_scores +
            0.10 * property_scores +
            0.15 * ontology_scores +
            0.20 * block_scores
        )

        # --------------------------------------------------
        # FILTRAR CLASES NO TURÍSTICAS
        # --------------------------------------------------

        filtered_scores = np.full(len(final_scores), -1e9)

        for i, cname in enumerate(self.class_names):

            if cname in self.allowed_classes:

                filtered_scores[i] = final_scores[i]

        final_scores = filtered_scores

        # --------------------------------------------------
        # MEJOR CLASE
        # --------------------------------------------------

        best_idx = int(np.argmax(final_scores))

        best_class = self.class_names[best_idx]

        best_score = float(final_scores[best_idx])

        # fallback si score bajo

        if best_score < 0.30:
            best_class = "Place"

        # --------------------------------------------------
        # TOP CANDIDATES
        # --------------------------------------------------

        top_indices = np.argsort(final_scores)[::-1][:5]

        top_candidates = [
            (self.class_names[i], float(final_scores[i]))
            for i in top_indices
        ]

        score_map = {
            self.class_names[i]: float(final_scores[i])
            for i in range(len(self.class_names))
        }

        return {
            "class": best_class,
            "confidence": best_score,
            "scores": score_map,
            "top_candidates": top_candidates,
        }