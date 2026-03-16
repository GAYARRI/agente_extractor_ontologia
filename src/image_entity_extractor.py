import re


class ImageEntityExtractor:

    def extract(self, image_url, alt_text=None):

        entities = []

        if alt_text:

            alt_text = alt_text.strip()

            # patrón simple de entidad turística
            words = alt_text.split()

            if len(words) >= 2:

                entities.append(alt_text)

        # intentar inferir entidad desde el nombre de la imagen
        if image_url:

            filename = image_url.split("/")[-1]

            filename = filename.replace(".jpg", "")
            filename = filename.replace(".png", "")
            filename = filename.replace("-", " ")
            filename = filename.replace("_", " ")

            words = filename.split()

            if len(words) >= 2:

                candidate = " ".join(words)

                if not candidate.isnumeric():

                    entities.append(candidate)

        return list(set(entities))