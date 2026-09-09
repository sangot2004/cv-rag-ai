SKILL_SYNONYMS: dict[str, list[str]] = {
    "postgresql": ["postgres", "postgre", "psql"],
    "javascript": ["js"],
    "typescript": ["ts"],
    "kubernetes": ["k8s"],
    "python": ["py"],
    "amazon web services": ["aws"],
    "google cloud platform": ["gcp"],
    "microsoft azure": ["azure"],
    "continuous integration": ["ci/cd", "ci cd", "cicd"],
    "machine learning": ["ml"],
    "artificial intelligence": ["ai"],
    "natural language processing": ["nlp"],
    "restful api": ["rest api", "rest"],
}

_ALIAS_TO_GROUP: dict[str, str] = {}
for canonical, aliases in SKILL_SYNONYMS.items():
    _ALIAS_TO_GROUP[canonical] = canonical
    for alias in aliases:
        _ALIAS_TO_GROUP[alias] = canonical


def expand_search_terms(term: str) -> list[str]:
    normalized = term.strip().lower()
    group = _ALIAS_TO_GROUP.get(normalized)
    if group is None:
        return [term]

    all_terms = {group, *SKILL_SYNONYMS[group]}
    return sorted(all_terms)
