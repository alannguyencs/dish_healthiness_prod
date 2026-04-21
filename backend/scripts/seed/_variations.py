"""
Synonym + variation maps used by the nutrition-DB seed script.

DO NOT EDIT WITHOUT RE-SEEDING + RE-RUNNING STAGE 9 BENCHMARK.
These maps are tuned against the reference project's 846-query NDCG eval
set (`/Volumes/wd/projects/dish_healthiness/data/nutrition_db/retrieval_eval_dataset.csv`)
which measured NDCG@10 = 0.7744 with the corpus they produce. Tweaking
the synonyms changes the corpus vocabulary and shifts the benchmark.
"""

import re
from typing import List


_SYNONYM_MAP = {
    "mee": ["noodles", "mi", "mie"],
    "noodles": ["mee", "mi"],
    "nasi": ["rice"],
    "rice": ["nasi", "bhat", "chawal"],
    "kuih": ["kueh", "cake"],
    "roti": ["bread", "chapati", "paratha"],
    "laksa": ["soup noodles", "noodle soup"],
    "goreng": ["fried"],
    "fried": ["goreng", "tali"],
    "lemak": ["coconut", "coconut milk"],
    "curry": ["kari", "masala", "gravy"],
    "soup": ["laksa", "shorba"],
    "chicken": ["ayam", "murgh", "kozhi"],
    "beef": ["daging", "gosht"],
    "fish": ["ikan", "machli"],
    "prawn": ["udang", "jhinga"],
    "egg": ["telur", "anda"],
    "kaathi": ["kathi", "kati"],
    "kathi": ["kaathi", "kati"],
    "roll": ["rolls", "wrap"],
    "rolls": ["roll", "wraps"],
    "paratha": ["parantha", "parotha"],
    "parantha": ["paratha", "parotha"],
    "masala": ["spice", "seasoning"],
    "paneer": ["cottage cheese", "cheese"],
    "dal": ["lentil", "lentils", "dhal"],
    "biryani": ["biriyani", "birani", "pilaf"],
}


_MYFCD_FOOD_KEYWORDS = (
    "rice",
    "noodles",
    "bread",
    "cake",
    "kuih",
    "curry",
    "soup",
    "chicken",
    "beef",
    "fish",
    "prawn",
    "egg",
    "vegetable",
    "fried",
    "steamed",
    "boiled",
    "grilled",
)


_MYFCD_MALAYSIAN_TERMS = (
    "nasi",
    "mee",
    "laksa",
    "roti",
    "kuih",
    "lemak",
    "goreng",
    "rendang",
    "satay",
    "char",
    "wan tan",
)


_INDIAN_TERMS = (
    "masala",
    "curry",
    "dal",
    "rice",
    "roti",
    "chapati",
    "naan",
    "biryani",
    "pulao",
    "samosa",
    "dosa",
    "idli",
    "vada",
    "pakora",
    "paneer",
    "chicken",
    "mutton",
    "fish",
    "vegetable",
    "lentil",
    "garam",
    "tandoori",
    "korma",
    "vindaloo",
    "saag",
    "bhaji",
    "kaathi",
    "kathi",
    "roll",
    "rolls",
    "paratha",
    "parantha",
    "kheer",
    "cutlet",
    "patties",
    "sandwich",
)


_INDIAN_SPELLING_VARIATIONS = {
    "kaathi": ["kathi", "kati"],
    "kathi": ["kaathi", "kati"],
    "paratha": ["parantha", "parotha"],
    "parantha": ["paratha", "parotha"],
    "biryani": ["biriyani", "birani"],
    "masala": ["massala"],
    "pulao": ["pilaf", "pilau", "pulav"],
}


_PLURAL_MAP = {
    "roll": ["rolls"],
    "rolls": ["roll"],
    "cutlet": ["cutlets"],
    "cutlets": ["cutlet"],
    "samosa": ["samosas"],
    "samosas": ["samosa"],
    "pakora": ["pakoras"],
    "pakoras": ["pakora"],
}


_STOP_WORD_RE = re.compile(r"\b(and|with|&)\b")


def generate_food_variations(food_name: str) -> List[str]:
    """Return synonym-expanded variations of `food_name`."""
    if not food_name:
        return []

    variations: List[str] = []
    name_lower = food_name.lower()
    words = name_lower.split()

    for word in words:
        for synonym in _SYNONYM_MAP.get(word, ()):
            variation = name_lower.replace(word, synonym)
            if variation != name_lower:
                variations.append(variation)
                variations.append(synonym)

    simplified = _STOP_WORD_RE.sub(" ", name_lower)
    simplified = re.sub(r"\s+", " ", simplified).strip()
    if simplified and simplified != name_lower:
        variations.append(simplified)

    return variations


def extract_clean_terms_from_myfcd(myfcd_name: str) -> List[str]:
    """Mine cleanable terms from a MyFCD-style food name."""
    if not myfcd_name:
        return []

    clean_terms: List[str] = []

    paren_matches = re.findall(r"\(([^)]+)\)", myfcd_name)
    clean_terms.extend(paren_matches)

    name_lower = myfcd_name.lower()
    for keyword in _MYFCD_FOOD_KEYWORDS:
        if keyword in name_lower:
            clean_terms.append(keyword)

    for term in _MYFCD_MALAYSIAN_TERMS:
        if term in name_lower:
            clean_terms.append(term)

    return clean_terms


def generate_indian_food_variations(food_name: str) -> List[str]:
    """Spelling + plural variations for Indian food names."""
    variations: List[str] = []
    for original, variants in _INDIAN_SPELLING_VARIATIONS.items():
        if original in food_name:
            variations.extend(variants)

    for word in food_name.split():
        if word in _PLURAL_MAP:
            variations.extend(_PLURAL_MAP[word])

    return variations


def extract_clean_terms_from_anuvaad(anuvaad_name: str) -> List[str]:
    """Mine cleanable terms from an Anuvaad food name."""
    if not anuvaad_name:
        return []

    clean_terms: List[str] = []
    name_lower = anuvaad_name.lower()

    for term in _INDIAN_TERMS:
        if term in name_lower:
            clean_terms.append(term)

    words = re.split(r"[\s,/().-]+", name_lower)
    clean_terms.extend(word.strip() for word in words if len(word) > 2)

    clean_terms.extend(generate_indian_food_variations(name_lower))

    seen = set()
    unique: List[str] = []
    for term in clean_terms:
        if term not in seen:
            seen.add(term)
            unique.append(term)
    return unique
