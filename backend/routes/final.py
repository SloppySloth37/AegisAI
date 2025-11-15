from flask import Blueprint, request, jsonify
from utils.risk import compute_risk
from utils.logger import add_log

final_bp = Blueprint('final', __name__, url_prefix='/api')


@final_bp.post('/final')
def final_route():
    """Aggregate final output and compute/confirm final risk score.
    Input: { input: str, sanitized: str, filtered: str, context?: {category, confidence}, entities?: [] }
    Output: { result: str, risk: int }
    """
    data = request.get_json(silent=True) or {}
    input_text = data.get('input') or ''
    sanitized = data.get('sanitized') or ''
    filtered = data.get('filtered') or ''
    entities = data.get('entities') or []
    context = data.get('context') or {}
    category = (context.get('category') or 'general').lower()

    # If entities not passed, we cannot recompute precisely; fallback to heuristic using compute_risk
    risk = compute_risk(entities, category)

    # Prefer filtered output if present, otherwise sanitized
    result = filtered or sanitized or ''

    add_log({
        'stage': 'final',
        'result': result,
        'risk': risk,
        'context': context,
    })

    return jsonify({
        'result': result,
        'risk': risk,
    })
