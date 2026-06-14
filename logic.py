"""
logic.py — SIMSLogic
Handles NLP preprocessing and ML classification.

Loading strategy (in order):
  1. models/sims_pipeline.pkl         — full sklearn Pipeline (tfidf + classifier)
  2. models/sims_tfidf_vectorizer.pkl + models/sims_classifier.pkl — separate files
  3. Built-in keyword classifier (fallback — no .pkl needed, always works)

NLTK corpora used (downloaded safely at runtime):
  stopwords  — Bird et al. (2009)
  wordnet    — Miller (1995)
  punkt / punkt_tab — Kiss & Strunk (2006)
  omw-1.4    — Bond & Foster (2013)
"""

import re
import string
import os

import numpy as np

# ── joblib — for loading .pkl model files ──────────────────
try:
    import joblib
    _JOBLIB = True
except ImportError:
    _JOBLIB = False
    print("[SIMS] joblib not found — ML model loading disabled.")

# ── NLTK — all imports wrapped in try/except ───────────────
# This prevents a crash if NLTK is not installed or corpora
# are not yet downloaded. The keyword fallback (Mode C) works
# without NLTK so the app always starts.
try:
    import nltk as _nltk
    from nltk.corpus import stopwords as _nltk_stopwords
    from nltk.stem import WordNetLemmatizer as _WNLemmatizer
    from nltk.tokenize import word_tokenize as _word_tokenize
    _NLTK_OK = True
except ImportError:
    _NLTK_OK = False
    print("[SIMS] NLTK not found — using simple text cleaning fallback.")


def _safe_download_nltk():
    """
    Download required NLTK corpora only if not already present.
    Safe to call multiple times — skips already-downloaded resources.
    """
    if not _NLTK_OK:
        return
    _nltk_dir = os.path.expanduser("~/nltk_data")
    os.makedirs(_nltk_dir, exist_ok=True)
    _resources = {
        "stopwords":  "corpora",
        "wordnet":    "corpora",
        "omw-1.4":    "corpora",
        "punkt":      "tokenizers",
        "punkt_tab":  "tokenizers",
    }
    for resource, category in _resources.items():
        try:
            _nltk.data.find(f"{category}/{resource}")
        except LookupError:
            try:
                _nltk.download(resource, quiet=True,
                               download_dir=_nltk_dir)
                print(f"[SIMS] Downloaded NLTK corpus: {resource}")
            except Exception as e:
                print(f"[SIMS] Could not download {resource}: {e}")


# ── Model file paths ────────────────────────────────────────
_MODEL_PATHS = {
    "pipeline":   ["models/sims_pipeline.pkl",         "sims_pipeline.pkl"],
    "vectorizer": ["models/sims_tfidf_vectorizer.pkl",  "sims_tfidf_vectorizer.pkl"],
    "classifier": ["models/sims_classifier.pkl",        "sims_classifier.pkl"],
}


def _find(key: str):
    for path in _MODEL_PATHS[key]:
        if os.path.exists(path):
            return path
    return None


# ── Built-in keyword classifier (Mode C fallback) ──────────
_HIGH_RISK_WORDS = {
    "suicide", "suicidal", "kill", "killing", "die", "dying", "death",
    "end my life", "end it all", "want to die", "rather be dead",
    "no reason to live", "worthless", "hopeless", "self harm", "self-harm",
    "cutting", "overdose", "hang", "hanging", "jump off", "goodbye forever",
    "cant go on", "can't go on", "give up on life", "not worth living",
    "better off dead", "no point living", "tired of living",
}
_MODERATE_RISK_WORDS = {
    "depressed", "depression", "anxious", "anxiety", "empty", "numb",
    "lonely", "alone", "helpless", "miserable", "suffering",
    "pain", "hurt", "broken", "exhausted", "tired", "burden", "useless",
    "hate myself", "failure", "trapped", "stuck", "no one cares",
    "nobody cares", "give up", "cant cope", "can't cope", "mental health",
    "panic", "crying", "tears", "darkness", "dark thoughts", "disappear",
}


def _keyword_score(text: str):
    """
    Mode C — keyword-based risk scoring fallback.
    Returns (probs array [1,3], preds array [1]).
    Classes: 0=Low Risk, 1=Moderate Risk, 2=High Risk
    """
    text_lower = text.lower()
    high = sum(1 for w in _HIGH_RISK_WORDS     if w in text_lower)
    mod  = sum(1 for w in _MODERATE_RISK_WORDS if w in text_lower)

    if high >= 2:
        pred, p_high, p_mod, p_low = 2, 0.75 + min(high * 0.04, 0.20), 0.15, 0.10
    elif high == 1:
        pred, p_high, p_mod, p_low = 2, 0.60, 0.25, 0.15
    elif mod >= 3:
        pred, p_high, p_mod, p_low = 1, 0.15, 0.70, 0.15
    elif mod >= 1:
        pred, p_high, p_mod, p_low = 1, 0.10, 0.55 + mod * 0.03, 0.35
    else:
        pred, p_high, p_mod, p_low = 0, 0.05, 0.10, 0.85

    total = p_high + p_mod + p_low
    probs = np.array([[p_low / total, p_mod / total, p_high / total]])
    preds = np.array([pred])
    return probs, preds


def _simple_clean(text: str) -> str:
    """
    Simple text cleaner used when NLTK is unavailable.
    Lowercases, removes URLs, digits, punctuation, and short tokens.
    """
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"http\S+|www\S+|@\w+|\d+", "", text)
    text = text.translate(str.maketrans("", "", string.punctuation))
    tokens = text.split()
    return " ".join(w for w in tokens if len(w) > 2)


# ════════════════════════════════════════════════════════════
#  SIMSLogic — main class
# ════════════════════════════════════════════════════════════
class SIMSLogic:
    """
    Preprocessing (SIMS_05) + ML Classification (SIMS_06) backend.

    Mode A — sims_pipeline.pkl (full sklearn Pipeline)
    Mode B — sims_tfidf_vectorizer.pkl + sims_classifier.pkl (separate)
    Mode C — Built-in keyword classifier (always available)
    """

    def __init__(self):
        # ── Download NLTK corpora safely ────────────────────
        _safe_download_nltk()

        # ── Initialise NLP tools ────────────────────────────
        if _NLTK_OK:
            try:
                self.lemmatizer = _WNLemmatizer()
                self.stop_words = set(
                    _nltk_stopwords.words("english")
                )
                self._use_nltk = True
            except Exception as e:
                print(f"[SIMS] NLTK init error: {e} — using simple cleaner.")
                self.lemmatizer = None
                self.stop_words = set()
                self._use_nltk  = False
        else:
            self.lemmatizer = None
            self.stop_words = set()
            self._use_nltk  = False

        # ── Model slots ─────────────────────────────────────
        self.pipeline   = None
        self.vectorizer = None
        self.classifier = None
        self.mode       = None
        self._load_models()

    # ── Model loading ───────────────────────────────────────
    def _load_models(self):
        if _JOBLIB:
            # Mode A — full pipeline
            pp = _find("pipeline")
            if pp:
                try:
                    self.pipeline = joblib.load(pp)
                    self.mode = "pipeline"
                    print(f"[SIMS] Mode A — pipeline: {pp}")
                    return
                except Exception as e:
                    print(f"[SIMS] Pipeline load failed ({e}), trying Mode B…")

            # Mode B — separate vectoriser + classifier
            vp = _find("vectorizer")
            cp = _find("classifier")
            if vp and cp:
                try:
                    self.vectorizer = joblib.load(vp)
                    self.classifier = joblib.load(cp)
                    self.mode = "separate"
                    print(f"[SIMS] Mode B — vectorizer: {vp}, classifier: {cp}")
                    return
                except Exception as e:
                    print(f"[SIMS] Separate load failed ({e}), using fallback…")

        # Mode C — built-in keyword classifier
        self.mode = "keyword"
        print("[SIMS] Mode C — keyword classifier active.")

    @property
    def is_ready(self) -> bool:
        """Always True — Mode C ensures the app never blocks."""
        return True

    @property
    def using_fallback(self) -> bool:
        return self.mode == "keyword"

    # ── Text preprocessing (SIMS_05) ────────────────────────
    def clean_text(self, text: str) -> str:
        """
        SIMS_05 — Preprocess one text post.

        Pipeline (when NLTK available):
          lowercase → remove URLs/handles/digits → remove punctuation
          → word_tokenize → stopword removal → WordNetLemmatize

        Pipeline (NLTK fallback):
          lowercase → remove URLs/digits/punctuation → split → filter short words

        References:
          Bird et al. (2009) — NLTK stopwords corpus
          Miller (1995)      — WordNet lemmatiser
          Kiss & Strunk (2006) — punkt tokeniser
        """
        if not isinstance(text, str):
            return ""

        if not self._use_nltk:
            return _simple_clean(text)

        try:
            text = text.lower()
            text = re.sub(r"http\S+|www\S+|@\w+|\d+", "", text)
            text = text.translate(str.maketrans("", "", string.punctuation))
            tokens = _word_tokenize(text)
            processed = [
                self.lemmatizer.lemmatize(w)
                for w in tokens
                if w not in self.stop_words and len(w) > 1
            ]
            return " ".join(processed)
        except Exception:
            return _simple_clean(text)

    # ── Batch classification (SIMS_06) ──────────────────────
    def predict_proba_batch(self, cleaned_texts):
        """
        SIMS_06 — Classify a list of pre-cleaned texts.
        Returns (probabilities_array, predictions_array).

        probabilities_array columns:
          index 0 = p(Low Risk)
          index 1 = p(Moderate Risk)
          index 2 = p(High Risk)   ← used as danger score basis
        """
        try:
            if self.mode == "pipeline":
                probs = self.pipeline.predict_proba(cleaned_texts)
                preds = self.pipeline.predict(cleaned_texts)

            elif self.mode == "separate":
                features = self.vectorizer.transform(cleaned_texts)
                probs    = self.classifier.predict_proba(features)
                preds    = self.classifier.predict(features)

            else:  # Mode C — keyword
                all_probs, all_preds = [], []
                for text in cleaned_texts:
                    p, pred = _keyword_score(text)
                    all_probs.append(p[0])
                    all_preds.append(pred[0])
                probs = np.array(all_probs)
                preds = np.array(all_preds)

        except Exception as e:
            print(f"[SIMS] predict_proba_batch error: {e} — using keyword fallback.")
            all_probs, all_preds = [], []
            for text in cleaned_texts:
                p, pred = _keyword_score(text)
                all_probs.append(p[0])
                all_preds.append(pred[0])
            probs = np.array(all_probs)
            preds = np.array(all_preds)

        return probs, preds

    # ── Single post classification ───────────────────────────
    def predict(self, cleaned_text: str):
        """
        SIMS_06 — Classify a single pre-cleaned text.
        Returns (risk_score: float, risk_label: str).

        risk_score = p(High Risk) — the probability of the High Risk class.
        This gives a true 0–1 danger scale:
          0.0 → definitely safe
          1.0 → definitely high risk

        Reference: Breiman (2001); scikit-learn predict_proba documentation.
        """
        probs, preds = self.predict_proba_batch([cleaned_text])
        # Use p(High Risk) as the risk score — always 0=safe, 1=danger
        risk_score = float(probs[0][2])
        label = {0: "Low Risk", 1: "Moderate Risk", 2: "High Risk"}.get(
            int(preds[0]), "Unknown"
        )
        return risk_score, label