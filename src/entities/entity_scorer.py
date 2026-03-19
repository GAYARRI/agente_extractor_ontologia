class EntityScorer:

    def compute_importance(self, entity, text, global_counts):

        name = entity["entity"].lower()

        score = entity.get("score", 0.5)

        # 🔥 frecuencia local
        local_freq = text.lower().count(name)
        score += min(local_freq * 0.1, 0.3)

        # 🔥 frecuencia global
        global_freq = global_counts.get(name, 0)
        score += min(global_freq * 0.05, 0.3)

        # 🔥 tiene imagen
        if entity.get("properties", {}).get("image"):
            score += 0.1

        # 🔥 longitud óptima
        words = name.split()
        if 2 <= len(words) <= 4:
            score += 0.1

        # 🔥 penalización ruido
        if any(x in name for x in ["click", "info", "home"]):
            score -= 0.3

        return max(0, min(1, score))