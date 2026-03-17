def is_valid_entity(entity):

    if not entity:
        return False

    e = entity.lower()
    words = entity.split()

    if len(words) > 6 or len(entity) < 4:
        return False

    if len(words) == 1 and e not in ["atlántico", "gran canaria"]:
        return False

    if any(x in e for x in [
        "wenn", "sie", "und", "les", "des",
        "comment", "arriver"
    ]):
        return False

    return True