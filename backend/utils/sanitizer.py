import re
from typing import List, Tuple, Dict
from utils.logger import add_log

try:
    import spacy
    try:
        # Try the transformer model first
        _NLP = spacy.load("en_core_web_trf")
    except Exception:
        # Fallback to small model if transformer not available
        _NLP = spacy.load("en_core_web_sm")
except Exception:
    _NLP = None

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.I)
PHONE_RE = re.compile(r"(\+?\d[\d\s\-]{7,}\d)")
ID_RE = re.compile(r"\b(\d{4}[-\s]?){3,}\d{4}\b")

CATEGORY_KEYWORDS = {
    "medical": ["diagnosis", "patient", "hospital", "medication", "doctor", "symptom", "clinic"],
    "financial": ["credit", "debit", "bank", "account", "loan", "salary", "invoice", "card"],
    "personal": ["address", "phone", "email", "ssn", "passport", "license", "birthday"],
}

LABEL_MAP = {
    "PERSON": "PERSON",
    "ORG": "ORG",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "NORP": "GROUP",
    "FAC": "LOCATION",
    "DATE": "DATE",
    "TIME": "TIME",
    "MONEY": "MONEY",
    "CARDINAL": "NUMBER",
    "QUANTITY": "NUMBER",
    "ORDINAL": "NUMBER",
}


def _ensure_spacy():
    global _NLP
    if _NLP is None:
        try:
            import spacy  # type: ignore
            try:
                _NLP = spacy.load("en_core_web_trf")
            except Exception:
                _NLP = spacy.load("en_core_web_sm")
        except Exception:
            _NLP = None


def _simple_context_classify(text: str) -> Tuple[str, float]:
    t = (text or "").lower()
    scores = {k: 0 for k in CATEGORY_KEYWORDS.keys()}
    for cat, words in CATEGORY_KEYWORDS.items():
        for w in words:
            if w in t:
                scores[cat] += 1
    if not any(scores.values()):
        return "general", 0.5
    best = max(scores, key=scores.get)
    total = sum(scores.values()) or 1
    conf = min(0.95, max(0.55, scores[best] / total))
    return best, conf


def _context_classify_multi(text: str) -> Tuple[str, float, List[str]]:
    t = (text or "").lower()
    scores = {k: 0 for k in CATEGORY_KEYWORDS.keys()}
    for cat, words in CATEGORY_KEYWORDS.items():
        for w in words:
            if w in t:
                scores[cat] += 1
    if not any(scores.values()):
        return "general", 0.5, ["general"]
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    ordered = [c for c, s in ordered if s > 0]
    combined = "-".join(ordered[:2]) if len(ordered) > 1 else ordered[0]
    best = ordered[0]
    total = sum(scores.values()) or 1
    best_score = scores[best] / total
    conf = min(0.95, max(0.55, best_score))
    return combined, conf, ordered

def sanitize_text(text: str, ner: str = None) -> Tuple[str, List[Dict], str, float]:
    """
    Returns: sanitized_text, entities, context(str), confidence(float)
    entities = [{"entity": original_text, "label": label}]
    """
    entities: List[Dict] = []
    spans: List[Tuple[int, int, str]] = []  # (start, end, label)

    # Force spaCy-only behavior regardless of ner parameter
    backend = "spacy"
    _ensure_spacy()
    use_spacy = _NLP is not None

    did_any = False
    spacy_count = 0
    if use_spacy:
        doc = _NLP(text)
        for ent in doc.ents:
            label = LABEL_MAP.get(ent.label_, ent.label_)
            spans.append((ent.start_char, ent.end_char, label))
            entities.append({"entity": ent.text, "label": label})
            spacy_count += 1
        did_any = True
    if not did_any:
        # Regex-based fallback for key PII
        for m in EMAIL_RE.finditer(text):
            spans.append((m.start(), m.end(), "EMAIL"))
            entities.append({"entity": m.group(0), "label": "EMAIL"})
        for m in PHONE_RE.finditer(text):
            spans.append((m.start(), m.end(), "PHONE"))
            entities.append({"entity": m.group(0), "label": "PHONE"})
        for m in ID_RE.finditer(text):
            spans.append((m.start(), m.end(), "ID"))
            entities.append({"entity": m.group(0), "label": "ID"})

    # Always add regex for email/phone on top of spaCy to be safe
    for m in EMAIL_RE.finditer(text):
        spans.append((m.start(), m.end(), "EMAIL"))
        entities.append({"entity": m.group(0), "label": "EMAIL"})
    for m in PHONE_RE.finditer(text):
        spans.append((m.start(), m.end(), "PHONE"))
        entities.append({"entity": m.group(0), "label": "PHONE"})

    # Merge overlapping spans prefer longer
    spans = sorted(spans, key=lambda s: (s[0], -(s[1]-s[0])))
    merged = []
    for s in spans:
        if not merged or s[0] > merged[-1][1]:
            merged.append(list(s))
        else:
            # overlap
            if s[1] > merged[-1][1]:
                merged[-1][1] = s[1]
            # keep first label
    spans = [(a, b, c) for a, b, c in merged]

    # Build sanitized text
    out = []
    last = 0
    for start, end, label in spans:
        if start < last:
            continue
        out.append(text[last:start])
        out.append(f"[{label}_MASKED]")
        last = end
    out.append(text[last:])
    sanitized = "".join(out)

    # Context classification
    context, conf, _ = _context_classify_multi(text)

    seen = set()
    dedup = []
    for e in entities:
        key = (e.get("entity"), e.get("label"))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(e)

    try:
        add_log({
            'stage': 'sanitize_debug',
            'backend': backend,
            'use_spacy': bool(use_spacy),
            'spacy_entities': spacy_count,
            'total_entities': len(dedup),
        })
    except Exception:
        pass

    return sanitized, dedup, context, float(conf)
