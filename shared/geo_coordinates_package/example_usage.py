from geo_utils import EntityGeoLocator


def main():
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "TouristAttraction",
          "name": "Museo Casa Botines",
          "geo": {
            "@type": "GeoCoordinates",
            "latitude": 42.59812,
            "longitude": -5.56709
          }
        }
        </script>
      </head>
      <body>
        <h1>Museo Casa Botines</h1>
      </body>
    </html>
    """

    locator = EntityGeoLocator(default_city="Leon")
    result = locator.locate(
        entity={
            "name": "Museo Casa Botines",
            "class": "Museum",
        },
        html=html,
        text="Museo Casa Botines",
        url="https://www.ejemplo.es/recurso/museo-casa-botines",
    )

    print(result)


if __name__ == "__main__":
    main()
