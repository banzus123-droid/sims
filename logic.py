"""
logic.py — SIMSLogic
Handles NLP preprocessing and ML classification.

Loading strategy (in order):
  1. models/sims_pipeline.pkl         — full sklearn Pipeline (tfidf + classifier)
  2. models/sims_tfidf_vectorizer.pkl + models/sims_classifier.pkl — separate files
  3. Built-in keyword classifier (fallback — no .pkl needed, always works)
"""

import re
import string
import os
import random
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

try:
    import joblib
    _JOBLIB = True
except ImportError:
    _JOBLIB = False

import numpy as np

_MODEL_PATHS = {
    'pipeline':   ['models/sims_pipeline.pkl',        'sims_pipeline.pkl'],
    'vectorizer': ['models/sims_tfidf_vectorizer.pkl', 'sims_tfidf_vectorizer.pkl'],
    'classifier': ['models/sims_classifier.pkl',       'sims_classifier.pkl'],
}

def _find(key: str):
    for path in _MODEL_PATHS[key]:
        if os.path.exists(path):
            return path
    return None


# ── Keyword lists for built-in fallback classifier ─────────────────────────
_HIGH_RISK_WORDS = {
    'suicide', 'suicidal', 'kill', 'killing', 'die', 'dying', 'death',
    'end my life', 'end it all', 'want to die', 'rather be dead',
    'no reason to live', 'worthless', 'hopeless', 'self harm', 'self-harm',
    'cutting', 'overdose', 'hang', 'hanging', 'jump off', 'goodbye forever',
    'cant go on', "can't go on", 'give up on life', 'not worth living',
    'better off dead', 'no point living', 'tired of living', 'wrist',
}
_MODERATE_RISK_WORDS = {
    'depressed', 'depression', 'anxious', 'anxiety', 'empty', 'numb',
    'lonely', 'alone', 'hopeless', 'helpless', 'miserable', 'suffering',
    'pain', 'hurt', 'broken', 'exhausted', 'tired', 'burden', 'useless',
    'hate myself', 'failure', 'trapped', 'stuck', 'no one cares',
    'nobody cares', 'give up', 'cant cope', "can't cope", 'mental health',
    'panic', 'crying', 'tears', 'darkness', 'dark thoughts', 'disappear',
}


def _keyword_score(text: str):
    """
    Built-in fallback: keyword-based risk scoring.
    Returns (probs array shape [1,3], preds array shape [1]).
    Classes: 0=Low, 1=Moderate, 2=High
    """
    text_lower = text.lower()

    high  = sum(1 for w in _HIGH_RISK_WORDS     if w in text_lower)
    mod   = sum(1 for w in _MODERATE_RISK_WORDS if w in text_lower)

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

    # Normalise so they sum to 1
    total = p_high + p_mod + p_low
    probs = np.array([[p_low / total, p_mod / total, p_high / total]])
    preds = np.array([pred])
    return probs, preds


class SIMSLogic:
    """
    Preprocessing (SIMS_05) + ML Classification (SIMS_06) backend.

    Mode A — sims_pipeline.pkl (full sklearn Pipeline)
    Mode B — sims_tfidf_vectorizer.pkl + sims_classifier.pkl (separate)
    Mode C — Built-in keyword classifier (always available, no files needed)
    """

    def __init__(self):
        # ── Download NLTK corpora (one-time, cached locally) ───────────────
        # Each entry below is a named linguistic corpus/resource:
        #
        # 'stopwords'  — Corpus of common English function words to remove
        #                (e.g. "the", "is", "and"). Source: NLTK Corpus.
        #                Reference: Bird, S., Klein, E., & Loper, E. (2009).
        #                Natural Language Processing with Python. O'Reilly.
        #
        # 'wordnet'    — Princeton WordNet lexical database used by
        #                WordNetLemmatizer to reduce words to their base form
        #                (e.g. "running" → "run", "better" → "good").
        #                Reference: Miller, G.A. (1995). WordNet: A lexical
        #                database for English. Communications of the ACM,
        #                38(11), 39–41.
        #
        # 'punkt'      — Unsupervised punkt tokeniser corpus used by
        # 'punkt_tab'    word_tokenize() to split text into tokens.
        #                Reference: Kiss, T., & Strunk, J. (2006). Unsupervised
        #                multilingual sentence boundary detection. Computational
        #                Linguistics, 32(4), 485–525.
        #
        # 'omw-1.4'    — Open Multilingual WordNet, extends WordNet lemmatiser
        #                coverage for lemmatisation accuracy.
        for resource in ('stopwords', 'wordnet', 'punkt', 'punkt_tab', 'omw-1.4'):
            nltk.download(resource, quiet=True)

        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english'))

        # ── Model slots ────────────────────────────────────
        self.pipeline   = None
        self.vectorizer = None
        self.classifier = None
        self.mode       = None

        self._load_models()

    def _load_models(self):
        if _JOBLIB:
            # Mode A — full pipeline
            pp = _find('pipeline')
            if pp:
                try:
                    self.pipeline = joblib.load(pp)
                    self.mode = 'pipeline'
                    print(f"[SIMS] Mode A — pipeline: {pp}")
                    return
                except Exception as e:
                    print(f"[SIMS] Pipeline load failed ({e}), trying Mode B…")

            # Mode B — separate files
            vp = _find('vectorizer')
            cp = _find('classifier')
            if vp and cp:
                try:
                    self.vectorizer = joblib.load(vp)
                    self.classifier = joblib.load(cp)
                    self.mode = 'separate'
                    print(f"[SIMS] Mode B — vectorizer: {vp}, classifier: {cp}")
                    return
                except Exception as e:
                    print(f"[SIMS] Separate load failed ({e}), using fallback…")

        # Mode C — built-in keyword classifier (always works)
        self.mode = 'keyword'
        print("[SIMS] Mode C — keyword classifier active (no .pkl files needed)")

    @property
    def is_ready(self) -> bool:
        """Always True — Mode C ensures the app never blocks."""
        return True

    @property
    def using_fallback(self) -> bool:
        """True when running on the built-in keyword classifier."""
        return self.mode == 'keyword'

    def clean_text(self, text: str) -> str:
        """
        SIMS_05 — Preprocess one text post.
        lowercase → remove URLs/handles/digits → remove punctuation
        → tokenise → stopword removal → lemmatise
        """
        if not isinstance(text, str):
            return ""
        text = text.lower()
        text = re.sub(r'http\S+|www\S+|\@\w+|\d+', '', text)
        text = text.translate(str.maketrans('', '', string.punctuation))
        tokens = word_tokenize(text)
        processed = [
            self.lemmatizer.lemmatize(w)
            for w in tokens
            if w not in self.stop_words and len(w) > 1
        ]
        return " ".join(processed)

    def predict_proba_batch(self, cleaned_texts):
        """
        SIMS_06 — Classify a list of pre-cleaned texts.
        Returns (probabilities_array, predictions_array).
        """
        if self.mode == 'pipeline':
            probs = self.pipeline.predict_proba(cleaned_texts)
            preds = self.pipeline.predict(cleaned_texts)

        elif self.mode == 'separate':
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

        return probs, preds

    def predict(self, cleaned_text: str):
        """
        SIMS_06 — Classify a single pre-cleaned text.
        Returns (risk_score: float, risk_label: str).
        """
        probs, preds = self.predict_proba_batch([cleaned_text])
        score = float(probs[0][preds[0]])
        label = {0: 'Low Risk', 1: 'Moderate Risk', 2: 'High Risk'}.get(
            int(preds[0]), 'Unknown'
        )
        return score, label