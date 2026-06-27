"""Hierarchical ISIC Rev. 5 classifier (two levels: section + division).

The classifier is a transparent, keyword-scoring heuristic:

* The official ISIC Rev. 5 structure is loaded from ``isic5_structure.csv``
  (downloaded from the UN Statistics Division), giving the authoritative
  section letters, division codes and *full class names* used as histogram bin
  labels in the report.
* Each division carries a curated set of domain keywords (tuned for the kind of
  qualitative / social-science research data found in the assigned
  repositories). A project's pooled text (title + description + keywords) is
  scored against every division; the two highest-scoring divisions become the
  primary and secondary classes.
* When no keyword matches, the classifier falls back to word overlap with the
  division titles and, as a last resort, to division ``72`` ("Scientific
  research and development") so that genuine research projects are never left
  unclassified.
"""

import csv
import os
import re

_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "isic5_structure.csv")

# Default division for research data that carries no recognizable domain signal.
DEFAULT_DIVISION = "72"


# ---------------------------------------------------------------------------
# Load the official structure
# ---------------------------------------------------------------------------
def _load_structure():
    sections = {}        # "A" -> title
    divisions = {}       # "01" -> {"name": ..., "section": "A"}
    division_order = []  # preserve file order
    current_section = None

    with open(_CSV_PATH, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader, None)  # header
        for row in reader:
            if not row or not row[0]:
                continue
            code = row[0].strip()
            title = row[1].strip() if len(row) > 1 else ""
            if len(code) == 1 and code.isalpha():
                current_section = code
                sections[code] = title
            elif len(code) == 2 and code.isdigit():
                divisions[code] = {"name": title, "section": current_section}
                division_order.append(code)
    return sections, divisions, division_order


SECTIONS, DIVISIONS, DIVISION_ORDER = _load_structure()


def division_name(code):
    """Full ISIC Rev. 5 division title for *code* (e.g. ``"85"`` -> Education)."""
    info = DIVISIONS.get(code)
    return info["name"] if info else ""


def section_of(code):
    """Section letter that owns division *code*."""
    info = DIVISIONS.get(code)
    return info["section"] if info else None


def section_name(letter):
    return SECTIONS.get(letter, "")


# ---------------------------------------------------------------------------
# Curated keyword -> division mapping
# ---------------------------------------------------------------------------
# Keywords are matched as lowercase substrings against the pooled project text.
# The mapping focuses on the divisions that realistically occur in social
# science / qualitative research collections; it does not need to be exhaustive
# across all 87 divisions.
DIVISION_KEYWORDS = {
    "01": ["agricultur", "farming", "farmer", "crop", "livestock", "harvest",
           "cattle", "maize", "rice paddy", "smallholder", "rural household",
           "irrigation", "horticultur", "agronom", "pastoral"],
    "02": ["forestry", "forest ", "logging", "timber", "deforestation",
           "reforestation", "woodland"],
    "03": ["fishery", "fisheries", "fishing", "aquaculture", "fisher ", "fishers",
           "marine catch", "fish stock"],
    "05": ["coal mining", "lignite"],
    "06": ["crude petroleum", "natural gas extraction", "oil extraction",
           "oil and gas"],
    "07": ["metal ore", "metal mining", "gold mining", "copper mining"],
    "08": ["quarry", "quarrying", "sand and gravel", "salt mining"],
    "10": ["food manufactur", "food processing", "food product"],
    "11": ["beverage manufactur", "brewing", "winery"],
    "13": ["textile manufactur", "weaving", "spinning mill"],
    "20": ["chemical manufactur", "chemical product"],
    "21": ["pharmaceutical manufactur", "drug manufactur"],
    "26": ["electronics manufactur", "semiconductor"],
    "35": ["electricity supply", "power generation", "electric grid",
           "energy supply", "renewable energy", "solar power", "wind power",
           "electrification"],
    "36": ["water supply", "drinking water", "water collection", "water treatment"],
    "37": ["sewerage", "sewage", "wastewater"],
    "38": ["waste collection", "waste management", "solid waste", "recycling",
           "garbage", "refuse"],
    "39": ["remediation", "site clean-up", "environmental remediation"],
    "41": ["building construction", "residential construction", "housing construction"],
    "42": ["civil engineering", "road construction", "infrastructure construction"],
    "43": ["construction work", "plumbing", "electrical installation"],
    "46": ["wholesale trade", "wholesaler"],
    "47": ["retail trade", "retailer", "retail store", "shopkeeper", "market vendor"],
    "49": ["land transport", "road transport", "railway", "trucking", "bus service",
           "commuting", "traffic", "mobility"],
    "50": ["water transport", "shipping", "maritime transport", "ferry"],
    "51": ["air transport", "aviation", "airline"],
    "52": ["warehousing", "logistics", "freight"],
    "53": ["postal", "courier"],
    "55": ["accommodation", "hotel", "lodging", "guesthouse"],
    "56": ["restaurant", "food service", "catering", "food and beverage service"],
    "58": ["publishing", "book publishing", "newspaper publishing", "journal publishing"],
    "59": ["film production", "motion picture", "video production", "music recording",
           "documentary film"],
    "60": ["broadcasting", "television programme", "radio programme", "news agency"],
    "61": ["telecommunication", "mobile phone", "telecom", "internet access",
           "broadband", "cellular network"],
    "62": ["software development", "computer programming", "software engineering",
           "open source software", "application development", "it consultancy"],
    "63": ["data processing", "data hosting", "web portal", "search engine",
           "computing infrastructure", "cloud computing"],
    "64": ["banking", "bank ", "credit union", "microfinance", "lending",
           "financial service", "savings"],
    "65": ["insurance", "reinsurance", "pension fund"],
    "66": ["financial auxiliary", "fund management"],
    "68": ["real estate", "property market", "land tenure", "housing market",
           "land ownership", "land rights"],
    "69": ["legal service", "law firm", "accounting service", "auditing",
           "judiciary", "courts of law"],
    "70": ["management consultancy", "head office", "business administration"],
    "71": ["architectural service", "engineering service", "technical testing",
           "land surveying"],
    "72": ["scientific research", "research and development", "experimental development",
           "biotechnology research", "social science research", "research project",
           "research data", "laboratory study"],
    "73": ["advertising", "market research", "public relations", "opinion poll"],
    "74": ["design service", "photography", "translation service"],
    "75": ["veterinary"],
    "77": ["rental service", "leasing", "equipment rental"],
    "78": ["employment agency", "labour market", "labor market", "unemployment",
           "job search", "workforce", "employment", "labour force", "labor force",
           "occupation", "wages", "working conditions"],
    "79": ["travel agency", "tour operator", "tourism"],
    "80": ["security service", "private security", "investigation service"],
    "81": ["building services", "cleaning service", "landscaping"],
    "82": ["call centre", "office support", "business support service"],
    "84": ["public administration", "government", "governance", "public policy",
           "public sector", "defence", "defense", "military", "armed forces",
           "election", "voting", "voter", "political party", "parliament",
           "civic", "citizenship", "taxation", "social security", "census",
           "municipal", "local government", "public service delivery"],
    "85": ["education", "school", "student", "teacher", "teaching", "learning",
           "literacy", "numeracy", "university", "college", "pupil", "classroom",
           "curriculum", "academic", "higher education", "early childhood education",
           "vocational training", "educational attainment", "enrolment", "enrollment"],
    "86": ["health", "medical", "disease", "hospital", "patient", "clinical",
           "mental health", "hiv", "aids", "malaria", "tuberculosis", "nutrition",
           "mortality", "morbidity", "epidemiolog", "healthcare", "health care",
           "vaccination", "immunization", "fertility", "reproductive health",
           "maternal health", "child health", "diabetes", "cancer", "covid",
           "mental illness", "wellbeing", "physician", "nursing", "medicine",
           "public health", "disability"],
    "87": ["residential care", "nursing home", "elderly care home"],
    "88": ["social work", "social services", "welfare", "social protection",
           "poverty", "vulnerable", "child protection", "social assistance",
           "humanitarian", "refugee", "migration", "migrant", "displacement",
           "food security", "social inclusion", "caregiving"],
    "90": ["performing arts", "theatre", "visual arts", "creative arts", "artist"],
    "91": ["library", "archive", "museum", "cultural heritage", "heritage site"],
    "92": ["gambling", "betting", "lottery"],
    "93": ["sports", "athletics", "recreation", "leisure activit", "physical activity"],
    "94": ["membership organization", "trade union", "religious organization",
           "civil society", "non-governmental", "ngo", "association of",
           "faith-based", "community organization", "advocacy group"],
    "95": ["repair of computers", "repair of household goods"],
    "96": ["hairdressing", "personal service", "funeral", "wellness service"],
    "97": ["domestic personnel", "domestic worker", "household employer"],
    "98": ["subsistence", "own-use production", "household own use"],
    "99": ["extraterritorial", "united nations", "international organization",
           "diplomatic"],
}

# ---------------------------------------------------------------------------
# Decisive title rules
# ---------------------------------------------------------------------------
# Some titles unambiguously identify the *subject* of a dataset and should
# dominate incidental keywords found in the description. Each rule grants a
# strong score to a division when its ``pattern`` matches the (lowercased)
# title and its optional ``exclude`` pattern does not.
TITLE_RULES = [
    # A general population / housing census (and IPUMS census subsets) is a
    # government statistical activity -> Public administration (84). Excluded
    # when the title points to a sector-specific census (e.g. agriculture or
    # an economic / business census), which is handled by keyword scoring.
    {
        "pattern": re.compile(
            r"\b(census|ipums|population and housing|housing and population|"
            r"population and dwelling|demographic census)\b"
        ),
        "exclude": re.compile(
            r"\b(agricultur|economic census|business census|enterprise census|"
            r"establishment census|industrial census)\b"
        ),
        "division": "84",
        "weight": 60,
    },
]


# Build a quick lookup from section letter -> representative division so we can
# fall back to a division when only a broad section can be inferred.
_SECTION_FALLBACK_DIVISION = {
    "A": "01", "B": "08", "C": "10", "D": "35", "E": "36", "F": "41",
    "G": "47", "H": "49", "I": "55", "J": "58", "K": "62", "L": "64",
    "M": "68", "N": "72", "O": "82", "P": "84", "Q": "85", "R": "86",
    "S": "93", "T": "96", "U": "97", "V": "99",
}


def _normalize(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text).lower())


def _title_overlap_scores(text):
    """Fallback: score divisions by word overlap with their official titles."""
    words = set(re.findall(r"[a-z]{4,}", text))
    if not words:
        return {}
    stop = {"and", "other", "activities", "service", "services", "related",
            "except", "products", "product", "manufacture", "n.e.c"}
    scores = {}
    for code, info in DIVISIONS.items():
        title_words = set(re.findall(r"[a-z]{4,}", info["name"].lower())) - stop
        overlap = len(words & title_words)
        if overlap:
            scores[code] = overlap
    return scores


def score_divisions(text, title=None):
    """Return a sorted ``[(division_code, score), ...]`` for *text* (best first).

    When *title* is supplied, keyword hits in the title are weighted more
    heavily than hits in the body text (the title is a stronger subject
    signal), and the decisive :data:`TITLE_RULES` are applied.
    """
    text = _normalize(text)
    title_n = _normalize(title) if title else ""
    if not text and not title_n:
        return []
    scores = {}
    for code, keywords in DIVISION_KEYWORDS.items():
        body_hits = 0
        title_hits = 0
        for kw in keywords:
            if kw in text:
                body_hits += 1
            if title_n and kw in title_n:
                title_hits += 1
        score = body_hits * 10 + title_hits * 20   # title signal weighted higher
        if score:
            scores[code] = score

    # Decisive title rules (strong, unambiguous subject indicators).
    if title_n:
        for rule in TITLE_RULES:
            if rule["pattern"].search(title_n) and not (
                rule.get("exclude") and rule["exclude"].search(title_n)
            ):
                code = rule["division"]
                scores[code] = scores.get(code, 0) + rule["weight"]

    # Blend in (lightly weighted) title-overlap signal.
    overlap_text = (text + " " + title_n).strip()
    for code, overlap in _title_overlap_scores(overlap_text).items():
        scores[code] = scores.get(code, 0) + overlap

    return sorted(scores.items(), key=lambda kv: (-kv[1], DIVISION_ORDER.index(kv[0])))


def classify_text(text, title=None):
    """Classify pooled text into primary / secondary ISIC divisions.

    *title*, when given, is scored more heavily than the body text and drives
    the decisive :data:`TITLE_RULES`. Returns a dict with ``primary_division``,
    ``primary_class`` (full name), ``primary_section``, ``secondary_division``,
    ``secondary_class``, ``secondary_section`` and ``score`` (primary score).
    Secondary fields are ``None`` when no clear second class exists.
    """
    ranked = score_divisions(text, title=title)

    if not ranked:
        primary = DEFAULT_DIVISION
        primary_score = 0
        secondary = None
    else:
        primary, primary_score = ranked[0]
        secondary = ranked[1][0] if len(ranked) > 1 else None

    result = {
        "primary_division": primary,
        "primary_class": division_name(primary),
        "primary_section": section_of(primary),
        "secondary_division": secondary,
        "secondary_class": division_name(secondary) if secondary else None,
        "secondary_section": section_of(secondary) if secondary else None,
        "score": primary_score,
    }
    return result
