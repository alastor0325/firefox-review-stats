"""Author name canonicalization.

Multiple git author strings can map to the same person (full name + Phab
handle + alternate spelling). Add entries here as you spot dupes.
"""

AUTHOR_ALIASES: dict[str, str] = {
    "alastor0325": "Alastor Wu",
    "alwu": "Alastor Wu",
    "az": "azebrowski",
}


def canonicalize_author(name: str) -> str:
    return AUTHOR_ALIASES.get(name, name)
