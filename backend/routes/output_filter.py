from flask import Blueprint, request, jsonify
from utils.logger import add_log
import re

output_filter_bp = Blueprint('output_filter', __name__, url_prefix='/api')

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.I)
PHONE_RE = re.compile(r"(\+?\d[\d\s\-]{7,}\d)")
ID_RE = re.compile(r"\b(\d{4}[-\s]?){3,}\d{4}\b")


@output_filter_bp.post('/output-filter')
def output_filter_route():
    """Post-process the LLM response to ensure privacy safety.
    Input: { original: str, sanitized: str }
    Output: { original: str, filtered: str }
    """
    data = request.get_json(silent=True) or {}
    original = data.get('original') or ''
    sanitized = data.get('sanitized') or ''

    # Basic filtering: remove any accidental PII patterns from original
    filtered = original
    filtered = EMAIL_RE.sub('[EMAIL_MASKED]', filtered)
    filtered = PHONE_RE.sub('[PHONE_MASKED]', filtered)
    filtered = ID_RE.sub('[ID_MASKED]', filtered)

    # Also avoid echoing raw brackets repeatedly; collapse multiple masks
    filtered = re.sub(r"\[(\w+)_MASKED\]+", r"[\1_MASKED]", filtered)

    add_log({
        'stage': 'output_filter',
        'original': original,
        'filtered': filtered,
    })

    return jsonify({
        'original': original,
        'filtered': filtered,
    })
