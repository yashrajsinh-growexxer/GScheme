"""
Multilingual translation layer using IndicTrans2.

Provides language detection and bidirectional translation
(Indic → English, English → Indic) for the RAG pipeline.
Models are lazy-loaded on first non-English query to avoid startup cost.
"""
from __future__ import annotations

import re
import logging
from typing import Optional, Tuple

from rag_pipeline.config import (
    EN_INDIC_MODEL,
    INDIC_EN_MODEL,
    TRANSLATION_MAX_LENGTH,
)

logger = logging.getLogger(__name__)

# FLORES-200 language codes used by IndicTrans2
FLORES_LANG_MAP = {
    "hi": "hin_Deva",
    "bn": "ben_Beng",
    "gu": "guj_Gujr",
    "kn": "kan_Knda",
    "ml": "mal_Mlym",
    "mr": "mar_Deva",
    "or": "ory_Orya",
    "pa": "pan_Guru",
    "ta": "tam_Taml",
    "te": "tel_Telu",
    "ur": "urd_Arab",
    "as": "asm_Beng",
    "ne": "npi_Deva",
    "sa": "san_Deva",
    "en": "eng_Latn",
}

# Reverse map: flores code -> short code
FLORES_TO_SHORT = {v: k for k, v in FLORES_LANG_MAP.items()}

# Sarvam BCP-47 to FLORES-200 mapping (for STT language_code → translation)
BCP47_TO_FLORES = {
    "hi-IN": "hin_Deva",
    "bn-IN": "ben_Beng",
    "gu-IN": "guj_Gujr",
    "kn-IN": "kan_Knda",
    "ml-IN": "mal_Mlym",
    "mr-IN": "mar_Deva",
    "od-IN": "ory_Orya",
    "pa-IN": "pan_Guru",
    "ta-IN": "tam_Taml",
    "te-IN": "tel_Telu",
    "en-IN": "eng_Latn",
    "ur-IN": "urd_Arab",
    "as-IN": "asm_Beng",
    "ne-IN": "npi_Deva",
    "sa-IN": "san_Deva",
}

# Unicode script ranges for fast detection
_SCRIPT_RANGES = [
    ("hin_Deva", r"[\u0900-\u097F]"),  # Devanagari (Hindi, Marathi, Sanskrit, Nepali)
    ("ben_Beng", r"[\u0980-\u09FF]"),  # Bengali / Assamese
    ("guj_Gujr", r"[\u0A80-\u0AFF]"),  # Gujarati
    ("pan_Guru", r"[\u0A00-\u0A7F]"),  # Gurmukhi (Punjabi)
    ("ory_Orya", r"[\u0B00-\u0B7F]"),  # Odia
    ("tam_Taml", r"[\u0B80-\u0BFF]"),  # Tamil
    ("tel_Telu", r"[\u0C00-\u0C7F]"),  # Telugu
    ("kan_Knda", r"[\u0C80-\u0CFF]"),  # Kannada
    ("mal_Mlym", r"[\u0D00-\u0D7F]"),  # Malayalam
    ("urd_Arab", r"[\u0600-\u06FF]"),  # Arabic script (Urdu)
]


class IndicTranslator:
    """
    Lazy-loaded IndicTrans2 translation wrapper.
    
    Models are loaded only on the first non-English translation request
    to avoid ~30-60s startup delay and ~4-6 GB memory usage when not needed.
    """

    _instance: Optional["IndicTranslator"] = None
    
    def __init__(self):
        self._indic_en_model = None
        self._indic_en_tokenizer = None
        self._en_indic_model = None
        self._en_indic_tokenizer = None
        self._processor = None
        self._device = None
        self._indic_en_unavailable = False
        self._en_indic_unavailable = False
        self._processor_unavailable = False

    @classmethod
    def get_instance(cls) -> "IndicTranslator":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_indic_en(self):
        """Lazy-load the Indic → English model."""
        if self._indic_en_model is not None:
            return True
        if self._indic_en_unavailable:
            return False
        
        try:
            logger.info("Loading IndicTrans2 Indic→En model (first use)...")
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            model_name = INDIC_EN_MODEL

            self._indic_en_tokenizer = AutoTokenizer.from_pretrained(
                model_name, trust_remote_code=True
            )
            dtype = torch.float16 if self._device == "cuda" else torch.float32
            self._indic_en_model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name, trust_remote_code=True, torch_dtype=dtype
            ).to(self._device)

            if not self._ensure_processor():
                self._indic_en_unavailable = True
                return False

            logger.info("IndicTrans2 Indic→En model loaded.")
            return True
        except Exception as exc:
            self._indic_en_unavailable = True
            logger.warning("IndicTrans2 Indic→En unavailable, multilingual fallback will use original text: %s", exc)
            return False

    def _ensure_en_indic(self):
        """Lazy-load the English → Indic model."""
        if self._en_indic_model is not None:
            return True
        if self._en_indic_unavailable:
            return False

        try:
            logger.info("Loading IndicTrans2 En→Indic model (first use)...")
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            if self._device is None:
                self._device = "cuda" if torch.cuda.is_available() else "cpu"

            model_name = EN_INDIC_MODEL

            self._en_indic_tokenizer = AutoTokenizer.from_pretrained(
                model_name, trust_remote_code=True
            )
            dtype = torch.float16 if self._device == "cuda" else torch.float32
            self._en_indic_model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name, trust_remote_code=True, torch_dtype=dtype
            ).to(self._device)

            if not self._ensure_processor():
                self._en_indic_unavailable = True
                return False

            logger.info("IndicTrans2 En→Indic model loaded.")
            return True
        except Exception as exc:
            self._en_indic_unavailable = True
            logger.warning("IndicTrans2 En→Indic unavailable, multilingual fallback will keep responses in English: %s", exc)
            return False

    def _ensure_processor(self):
        """Load the IndicProcessor if not already loaded."""
        if self._processor is not None:
            return True
        if self._processor_unavailable:
            return False
        try:
            from IndicTransToolkit.processor import IndicProcessor
            self._processor = IndicProcessor(inference=True)
            return True
        except ImportError:
            self._processor_unavailable = True
            logger.warning(
                "IndicTransToolkit not installed. "
                "Install with: pip install indictranstoolkit"
            )
            self._processor = None
            return False

    def is_english(self, text: str) -> bool:
        """Quick check if text is primarily English/ASCII."""
        if not text or not text.strip():
            return True
        # Count non-ASCII characters (excluding common punctuation)
        non_ascii = sum(1 for c in text if ord(c) > 127)
        return non_ascii / max(len(text.strip()), 1) < 0.15

    def detect_language(self, text: str) -> str:
        """
        Detect language using Unicode script ranges, with langdetect as fallback.
        Returns a FLORES-200 language code (e.g., 'hin_Deva', 'eng_Latn').
        """
        if not text or not text.strip():
            return "eng_Latn"

        if self.is_english(text):
            return "eng_Latn"

        # Script-based detection
        script_counts: dict[str, int] = {}
        for flores_code, pattern in _SCRIPT_RANGES:
            count = len(re.findall(pattern, text))
            if count > 0:
                script_counts[flores_code] = count

        if script_counts:
            detected = max(script_counts, key=lambda k: script_counts[k])
            # Disambiguate Devanagari scripts (Hindi vs Marathi vs Sanskrit)
            if detected == "hin_Deva":
                detected = self._disambiguate_devanagari(text)
            return detected

        # Fallback: langdetect
        try:
            from langdetect import detect
            lang_code = detect(text)
            # langdetect returns ISO 639-1 codes
            if lang_code in FLORES_LANG_MAP:
                return FLORES_LANG_MAP[lang_code]
        except Exception:
            pass

        return "eng_Latn"

    def _disambiguate_devanagari(self, text: str) -> str:
        """
        Disambiguate between Hindi, Marathi, Sanskrit, and Nepali
        when Devanagari script is detected. Uses langdetect for this.
        """
        try:
            from langdetect import detect
            lang = detect(text)
            if lang == "mr":
                return "mar_Deva"
            elif lang == "ne":
                return "npi_Deva"
            elif lang == "sa":
                return "san_Deva"
        except Exception:
            pass
        return "hin_Deva"

    def translate_to_english(self, text: str, src_lang: str) -> str:
        """Translate Indic text to English using IndicTrans2."""
        if src_lang == "eng_Latn" or not text.strip():
            return text

        if not self._ensure_indic_en():
            logger.warning("Translation models not available, returning original text")
            return text

        try:
            import torch

            batch = self._processor.preprocess_batch(
                [text], src_lang=src_lang, tgt_lang="eng_Latn"
            )
            inputs = self._indic_en_tokenizer(
                batch, padding=True, truncation=True,
                max_length=TRANSLATION_MAX_LENGTH, return_tensors="pt"
            ).to(self._device)

            with torch.inference_mode():
                generated = self._indic_en_model.generate(
                    **inputs, use_cache=True,
                    min_length=0, max_length=TRANSLATION_MAX_LENGTH,
                    num_beams=5, num_return_sequences=1,
                )

            with self._indic_en_tokenizer.as_target_tokenizer():
                decoded = self._indic_en_tokenizer.batch_decode(
                    generated, skip_special_tokens=True,
                    clean_up_tokenization_spaces=True,
                )

            result = self._processor.postprocess_batch(decoded, lang="eng_Latn")
            return result[0] if result else text

        except Exception as e:
            logger.error(f"Translation to English failed: {e}")
            return text

    def translate_from_english(self, text: str, tgt_lang: str) -> str:
        """Translate English text to Indic language using IndicTrans2."""
        if tgt_lang == "eng_Latn" or not text.strip():
            return text

        if not self._ensure_en_indic():
            logger.warning("Translation models not available, returning original text")
            return text

        try:
            import torch

            batch = self._processor.preprocess_batch(
                [text], src_lang="eng_Latn", tgt_lang=tgt_lang
            )
            inputs = self._en_indic_tokenizer(
                batch, padding=True, truncation=True,
                max_length=TRANSLATION_MAX_LENGTH, return_tensors="pt"
            ).to(self._device)

            with torch.inference_mode():
                generated = self._en_indic_model.generate(
                    **inputs, use_cache=True,
                    min_length=0, max_length=TRANSLATION_MAX_LENGTH,
                    num_beams=5, num_return_sequences=1,
                )

            with self._en_indic_tokenizer.as_target_tokenizer():
                decoded = self._en_indic_tokenizer.batch_decode(
                    generated, skip_special_tokens=True,
                    clean_up_tokenization_spaces=True,
                )

            result = self._processor.postprocess_batch(decoded, lang=tgt_lang)
            return result[0] if result else text

        except Exception as e:
            logger.error(f"Translation from English failed: {e}")
            return text


def get_translator() -> IndicTranslator:
    """Get the singleton translator instance."""
    return IndicTranslator.get_instance()


def detect_and_translate_query(text: str) -> Tuple[str, str]:
    """
    Detect language of user query and translate to English if needed.
    
    Returns:
        (english_text, detected_flores_code)
    """
    translator = get_translator()
    detected = translator.detect_language(text)
    
    if detected == "eng_Latn":
        return text, detected
    
    english_text = translator.translate_to_english(text, detected)
    logger.info(f"Translated [{detected}] → [eng_Latn]: '{text[:50]}...' → '{english_text[:50]}...'")
    return english_text, detected


def translate_response(text: str, target_lang: str) -> str:
    """
    Translate an English response to the target language.
    
    Args:
        text: English response text
        target_lang: FLORES-200 code of the target language
    
    Returns:
        Translated text, or original if target is English
    """
    if target_lang == "eng_Latn":
        return text
    
    translator = get_translator()
    translated = translator.translate_from_english(text, target_lang)
    logger.info(f"Translated response [eng_Latn] → [{target_lang}]: {len(text)} chars → {len(translated)} chars")
    return translated
