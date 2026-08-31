def extract_inflections(entry, expected_pos):
    inflections = {}

    if expected_pos == "adjective":
        for form in entry.get("forms", []):
            tags = form.get("tags", [])

            if (
                "plural" in tags
                and "positive" in tags
                and "indefinite" in tags
                and "masculine" not in tags
                and "archaic" not in tags
            ):
                inflections["plural"] = form["word"]

            elif (
                "comparative" in tags
                and "indefinite" in tags
                and "masculine" not in tags
                and "archaic" not in tags
            ):
                inflections["comparative"] = form["word"]

            elif (
                "superlative" in tags
                and "indefinite" in tags
                and "masculine" not in tags
                and "archaic" not in tags
            ):
                inflections["superlative"] = form["word"]

    elif expected_pos == "verb":
        for form in entry.get("forms", []):
            tags = form.get("tags", [])

            if (
                "present" in tags
                and "active" in tags
                and "indicative" in tags
                and "archaic" not in tags
                and "dated" not in tags
            ):
                inflections["present"] = form["word"]

            elif (
                "past" in tags
                and "active" in tags
                and "indicative" in tags
                and "archaic" not in tags
                and "dated" not in tags
            ):
                inflections["past"] = form["word"]

            elif (
                "supine" in tags
                and "active" in tags
            ):
                inflections["supine"] = form["word"]

            elif (
                "imperative" in tags
                and "active" in tags
                and "archaic" not in tags
            ):
                inflections["imperative"] = form["word"]

            elif (
                "participle" in tags
                and "present" in tags
                and "active" in tags
            ):
                inflections["participle"] = form["word"]

    elif expected_pos == "noun":
        for form in entry.get("forms", []):
            tags = form.get("tags", [])

            if (
                "indefinite" in tags
                and "nominative" in tags
                and "plural" in tags
            ):
                inflections["plural"] = form["word"]
                break

    return inflections