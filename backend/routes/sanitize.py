from flask import Blueprint, request, jsonify
from utils.sanitizer import sanitize_text
from utils.risk import compute_risk
from utils.logger import add_log
import re

sanitize_bp = Blueprint('sanitize', __name__, url_prefix='/api')
def mask_currency(text):
    # Matches ₹1234, Rs. 5000, INR 999, $20, £30, etc.
    pattern = r"(₹\s?\d+|Rs\.?\s?\d+|INR\s?\d+|\$\s?\d+|£\s?\d+|€\s?\d+)"
    return re.sub(pattern, "[CURRENCY]", text, flags=re.IGNORECASE)


@sanitize_bp.post('/sanitize')
def sanitize_route():
    """PII sanitization + context + risk scoring.
    Input: { "input": "text" }
    Output: {
      sanitized: str,
      entities: [{entity, label}],
      context: str,
      confidence: float,
      risk_score: int
    }
    """
    data = request.get_json(silent=True) or {}
    text = data.get('input', '') or ''
    text =mask_currency(text)
    # Force spaCy-only backend regardless of request parameter
    ner = 'spacy'

    sanitized, entities, context, confidence = sanitize_text(text, ner=ner)
    risk_score = compute_risk(entities, context)

    # Log entry
    add_log({
        'stage': 'sanitize',
        'input': text,
        'sanitized': sanitized,
        'entities': entities,
        'context': context,
        'confidence': confidence,
        'risk': risk_score,
        'ner': ner or 'auto',
    })

    return jsonify({
        'sanitized': sanitized,
        'entities': entities,
        'context': context,
        'confidence': confidence,
        'risk_score': risk_score,
        'risk': risk_score,
        'ner': ner or 'auto',
    })
