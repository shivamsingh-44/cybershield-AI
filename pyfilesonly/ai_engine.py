"""
CyberShield AI local message-risk classifier.

Uses a free pretrained model focused on scam/spam messages with Indian patterns.
The model runs locally after its first download. No paid inference API is used.
Predictions are signals for human review, not proof of fraud or safety.
"""

from functools import lru_cache
from typing import Any, Dict

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_NAME = "anmolshrivastav/distilbert-scam-detector-india"
MAX_CHARS = 4000


@lru_cache(maxsize=1)
def _load_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()
    return tokenizer, model


def analyze_with_ai(message: str) -> Dict[str, Any]:
    """Return local model label and confidence for scam/spam vs legitimate text."""
    if not isinstance(message, str) or not message.strip():
        return {
            "available": False,
            "label": "AI_UNAVAILABLE",
            "confidence": None,
            "explanation": "No message text was provided.",
            "model": MODEL_NAME,
        }

    try:
        tokenizer, model = _load_model()
        inputs = tokenizer(
            message.strip()[:MAX_CHARS],
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        with torch.no_grad():
            logits = model(**inputs).logits
            probabilities = torch.softmax(logits, dim=-1)[0]

        predicted_id = int(torch.argmax(probabilities).item())
        confidence = float(probabilities[predicted_id].item())
        id2label = getattr(model.config, "id2label", {}) or {}
        raw_label = str(id2label.get(predicted_id, f"LABEL_{predicted_id}")).lower()
        label_text = raw_label.replace("_", " ").replace("-", " ")

        # The model card documents class 0 as ham and class 1 as spam.
        # Also support descriptive labels if the checkpoint exposes them.
        if any(term in label_text for term in ("spam", "scam", "fraud", "phish", "malicious")):
            suspicious = True
        elif any(term in label_text for term in ("ham", "legitimate", "legit", "safe", "normal")):
            suspicious = False
        elif predicted_id == 1:
            suspicious = True
        else:
            suspicious = False

        label = "AI_SUSPICIOUS" if suspicious else "AI_LIKELY_SAFE"
        explanation = (
            "The local model classified this text as scam/spam-like."
            if suspicious
            else "The local model classified this text as more like legitimate messages."
        )

        return {
            "available": True,
            "label": label,
            "confidence": round(confidence, 4),
            "explanation": explanation,
            "model": MODEL_NAME,
            "raw_label": raw_label,
            "scope_note": (
                "Focused on scam/spam messages, including Indian-pattern examples. "
                "It is not a general misinformation fact-checker; a prediction can be wrong."
            ),
        }
    except Exception as exc:
        return {
            "available": False,
            "label": "AI_UNAVAILABLE",
            "confidence": None,
            "explanation": (
                "Local AI model could not load. Check the internet connection for the "
                "first download and confirm transformers and torch are installed. "
                "The rule-based detector can still run."
            ),
            "error": str(exc),
            "model": MODEL_NAME,
        }
