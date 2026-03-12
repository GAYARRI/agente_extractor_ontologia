import re
from bs4 import BeautifulSoup


class TourismPropertyExtractor:

    def __init__(self, class_properties):

        self.class_properties = class_properties

    # -----------------------------------

    def extract(self, html, text, url, entity):

        properties = {}

        entity_class = entity["class"]

        if entity_class not in self.class_properties:
            return properties

        soup = BeautifulSoup(html, "html.parser")

        # -------- imágenes --------

        images = soup.find_all("img")

        if images:

            properties["image"] = images[0].get("src")

        # -------- coordenadas --------

        lat = re.search(r'lat["\': ]+([0-9.\-]+)', html)
        lon = re.search(r'lon["\': ]+([0-9.\-]+)', html)

        if lat and lon:

            properties["geoLat"] = lat.group(1)
            properties["geoLong"] = lon.group(1)

        # -------- horarios --------

        hours = re.search(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})', text)

        if hours:

            properties["openingHours"] = hours.group(0)

        # -------- precio --------

        price = re.search(r'(\d+)\s?€', text)

        if price:

            properties["price"] = price.group(0)

        # -------- dirección --------

        address = re.search(r'Calle\s+[A-Za-z\s]+', text)

        if address:

            properties["address"] = address.group(0)

        # -------- rating --------

        rating = re.search(r'([0-5]\.?[0-9]?)\s?/5', text)

        if rating:

            properties["rating"] = rating.group(1)

        return properties