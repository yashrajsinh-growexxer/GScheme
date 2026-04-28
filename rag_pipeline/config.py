"""
Configuration constants for the knowledge-base pipeline.
"""
from pathlib import Path

# === PATHS ===
PROJECT_ROOT = Path(__file__).parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "schemes_data_json"
ENRICHED_DATA_DIR = PROJECT_ROOT / "data" / "schemes_enriched_json"
# Pipeline default reads enriched JSONs after extraction.
DATA_DIR = ENRICHED_DATA_DIR
CHUNKS_OUTPUT_DIR = PROJECT_ROOT / "data" / "chunks"
EMBEDDINGS_OUTPUT_DIR = PROJECT_ROOT / "data" / "prepared_embeddings"

# === CATEGORY MAPPING ===
CATEGORY_MAP = {
    1: "agriculture_rural_environment",
    2: "banking_financial_services_insurance",
    3: "business_entrepreneurship",
    4: "education_learning",
    5: "health_wellness",
    6: "housing_shelter",
    7: "public_safety_law_justice",
    8: "science_it_communications",
    9: "skills_employment",
    10: "social_welfare_empowerment",
    11: "sports_culture",
    12: "transport_infrastructure",
    13: "travel_tourism",
    14: "utility_sanitation",
    15: "women_child",
}

# Reverse mapping for lookup
CATEGORY_NAME_TO_ID = {v: k for k, v in CATEGORY_MAP.items()}

# === LOCATION NORMALIZATION ===
CENTRAL_GOVT_LABEL = "India"
LOCATION_TYPE_CENTRAL = "central"
LOCATION_TYPE_STATE = "state"
LOCATION_TYPE_UT = "union_territory"

# === CHUNKING CONFIG ===
CHUNK_CONFIG = {
    "details": {"max_tokens": 450, "overlap": 70},
    "benefits": {"max_tokens": 450, "overlap": 70},
    "eligibility": {"max_tokens": 450, "overlap": 70},
    "application_process": {"max_tokens": 450, "overlap": 70},
    "documents_required": {"max_tokens": 300, "overlap": 45},
    "sources_and_references": {"max_tokens": 200, "overlap": 0},
    "faq": {"max_tokens": 300, "overlap": 0},
}

# Approximate tokens per character (for estimation)
CHARS_PER_TOKEN = 4

# === EMBEDDING CONFIG ===
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIMENSION = 1024
SPARSE_VECTOR_NAME = "sparse"
DENSE_VECTOR_NAME = "dense"

# === QDRANT CONFIG ===
QDRANT_COLLECTION_NAME = "govt-scheme-hybrid"
QDRANT_DISTANCE = "cosine"
QDRANT_DEFAULT_LIMIT = 20

# === CHUNK TYPES ===
CHUNK_TYPES = [
    "details",
    "benefits", 
    "eligibility",
    "application_process",
    "documents_required",
    "sources_and_references",
    "faq",
]

# === METADATA KEYS ===
# These are the metadata fields stored in vector payloads.
METADATA_KEYS = [
    "scheme_id",
    "scheme_name",
    "scheme_url",
    "location_type",
    "location_name",
    "category_id",
    "category_name",
    "chunk_type",
    "chunk_index",
    "language",
    "scraped_at",
    "gender_tags",
    "caste_tags",
    "age_min",
    "age_max",
    "age_present",
    "age_min_effective",
    "age_max_effective",
    "age_confidence",
]

# === SUPPORTED LANGUAGES (for future multilingual support) ===
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "gu": "Gujarati",
    "ta": "Tamil",
    "bn": "Bengali",
    "te": "Telugu",
    "mr": "Marathi",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
}

DEFAULT_LANGUAGE = "en"

# === ELIGIBILITY METADATA VOCAB ===
GENDER_TAGS = ["female", "male", "transgender", "any", "unknown"]
CASTE_TAGS = ["sc", "st", "obc", "minority", "ews", "general", "any", "unknown"]

# =====================================================================
# GENERATOR PIPELINE CONFIG
# =====================================================================

# === GROQ CONFIG ===
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MAX_TOKENS = 2048
GROQ_TEMPERATURE = 0.3

# === RERANKER CONFIG ===
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
USE_RERANKER = False  # Set False to skip reranker and save ~20s on first load

# === DISCOVERY CONFIG ===
DISCOVERY_INITIAL_FETCH = 500   # chunks to pull from Qdrant
DISCOVERY_RERANK_CANDIDATES = 10  # unique schemes to rerank
DISCOVERY_TOP_K = 5             # final schemes to show
PROFESSION_BOOST = 1.25         # score multiplier for matching category

# === PROFESSION → CATEGORY MAPPING ===
PROFESSION_CATEGORY_MAP = {
    "Student": [4],                          # education_learning
    "Farmer": [1],                           # agriculture_rural_environment
    "Entrepreneur / Self-Employed": [3, 2],  # business, banking
    "Corporate Employee": [9, 2],            # skills_employment, banking
    "Government Employee": [9],              # skills_employment
    "Labourer / Worker": [9, 6],             # skills_employment, housing
    "Healthcare Worker": [5],                # health_wellness
    "Artisan / Craftsperson": [11, 3],       # sports_culture, business
    "Homemaker": [15, 10],                   # women_child, social_welfare
    "Retired": [10],                         # social_welfare_empowerment
    "Unemployed": [9, 10],                   # skills_employment, social_welfare
    "Other": [],
}

# === STREAMLIT UI OPTIONS ===
UI_GENDER_OPTIONS = ["Male", "Female", "Transgender"]

UI_STATE_OPTIONS = sorted([
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar",
    "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Delhi",
    "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
])

UI_AREA_OPTIONS = ["Urban", "Rural"]
UI_CASTE_OPTIONS = ["General", "OBC", "SC", "ST", "EWS", "Minority"]
UI_DISABILITY_OPTIONS = ["No", "Yes"]
UI_PROFESSION_OPTIONS = list(PROFESSION_CATEGORY_MAP.keys())

# === CHAT CONFIG ===
MAX_CHAT_HISTORY_TURNS = 10

# === TRANSLATION CONFIG ===
ENABLE_MULTILINGUAL = True
INDIC_EN_MODEL = "ai4bharat/indictrans2-indic-en-1B"
EN_INDIC_MODEL = "ai4bharat/indictrans2-en-indic-1B"
TRANSLATION_MAX_LENGTH = 512
