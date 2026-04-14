def normalize_type_name(value: str) -> str:
    if not value:
        return ""

    value = value.strip()

    mapping = {
        "Accommodation": "AccommodationEstablishment",
        "RetailAndFashion": "RetailandFashion",
        "GastronomicResource": "FoodEstablishment",
    }

    return mapping.get(value, value)