import json
import re
from bs4 import BeautifulSoup


class GeoExtractor:

    def extract(self, html):

        soup = BeautifulSoup(html, "html.parser")

        coords = []

        # --------------------------------
        # 1 JSON-LD (schema.org)
        # --------------------------------

        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:

            try:

                data = json.loads(script.string)

                if isinstance(data, dict):

                    geo = data.get("geo")

                    if geo:
                        lat = geo.get("latitude")
                        lon = geo.get("longitude")

                        if lat and lon:

                            coords.append({
                                "lat": float(lat),
                                "lon": float(lon)
                            })

            except:
                pass

        # --------------------------------
        # 2 meta tags
        # --------------------------------

        lat_meta = soup.find("meta", {"property": "place:location:latitude"})
        lon_meta = soup.find("meta", {"property": "place:location:longitude"})

        if lat_meta and lon_meta:

            coords.append({
                "lat": float(lat_meta["content"]),
                "lon": float(lon_meta["content"])
            })

        # --------------------------------
        # 3 Google Maps links
        # --------------------------------

        text = soup.get_text()

        matches = re.findall(r'(-?\d+\.\d+),\s*(-?\d+\.\d+)', text)

        for m in matches:

            lat = float(m[0])
            lon = float(m[1])

            if -90 <= lat <= 90 and -180 <= lon <= 180:

                coords.append({
                    "lat": lat,
                    "lon": lon
                })

        return coords