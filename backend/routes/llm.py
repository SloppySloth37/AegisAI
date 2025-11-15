from flask import Blueprint, request, jsonify
from utils.logger import add_log
import google.generativeai as genai
import os
llm_bp = Blueprint('llm', __name__, url_prefix='/api')



@llm_bp.post('/llm')
def llm_route():
    """Generate a safe LLM-like response using sanitized text and context.
    Input: { sanitized: str, context: { category: str, confidence: number } }
    Output: { output: str }
    """
    data = request.get_json(silent=True) or {}
    sanitized = data.get('sanitized') or ''
    print(sanitized)
    context = data.get('context') or {}
    cat = (context.get('category') or 'general').lower()

    api_key = os.getenv('GEMINI_API_KEY')
    output = None
    provider = 'mock'

    # for m in client.models.list():
    #     if "generateContent" in m.supported_actions:
    #         print(m.name)


    if api_key and sanitized:
        try:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=api_key)
            model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
            model = genai.GenerativeModel(model_name)
            system = (
                "You are a privacy-safe assistant. Use ONLY the provided sanitized text. "
                "Never infer or reconstruct masked information. Produce a concise 1-3 sentence response, "
                "aligned to the provided context category: medical, financial, personal, or general."
            )
            prompt = (
                f"Context category: {cat}.\n"
                f"Sanitized input: {sanitized}\n\n"
                "Write a helpful, safety-focused answer without exposing any PII or guessing hidden content. "
                "Remove any currency or addresses."
            )
            resp = model.generate_content([system, prompt])
            text = getattr(resp, 'text', None) or (resp.candidates[0].content.parts[0].text if getattr(resp, 'candidates', None) else None)
            if text:
                output = text.strip()
                provider = 'gemini'
        except Exception as e:
            print(e)
            output = None

    if not output:
        preface_map = {
            'medical': 'Medical guidance (non-diagnostic):',
            'financial': 'Financial safety note:',
            'personal': 'Personal info awareness:',
            'general': 'Assistant response:',
        }
        pre = preface_map.get(cat, 'Assistant response:')
        output = f"{pre} Based on your sanitized input, here is a privacy-safe response: {sanitized}"

    add_log({
        'stage': 'llm',
        'context': context,
        'output': output,
        'provider': provider,
    })

    return jsonify({
        'output': output,
        'provider': provider,
    })
