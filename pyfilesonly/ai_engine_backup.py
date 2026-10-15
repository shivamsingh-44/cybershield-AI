"""
CyberShield AI - local NLP spam/scam text classifier.

This module uses a pretrained transformer model locally after its first download.
It is an additional AI signal, not a fact-checker and not a guarantee that a
message is fraudulent. Keep the existing rule-based detector as a second signal.
"""

from functools import lru_cache
from typing import Any, Dict

MODEL_NAME = "mrm8488/bert-tiny-finetuned-sms-spam-detection"


@lru_cache(maxsize=1)
def _load_classifier():
    """Load once per Python process; first run needs internet to download model."""
    from transformers import pipeline

    return pipeline(
        task="text-classification",
        model=MODEL_NAME,
        tokenizer=MODEL_NAME,
        truncation=True,
    )


def analyze_with_ai(message: str) -> Dict[str, Any]:
    """
    Return a conservative, normalized AI prediction.

    `label` is AI_SUSPICIOUS or AI_LIKELY_SAFE.
    `confidence` is the model's confidence for its predicted class, not the
    probability that the message is actually a scam.
    """
    if not isinstance(message, str) or not message.strip():
        return {
            "available": False,
            "label": "AI_UNAVAILABLE",
            "confidence": None,
            "explanation": "No message text was provided.",
            "model": MODEL_NAME,
        }

    try:
        prediction = _load_classifier()(message.strip()[:4000])[0]
        raw_label = str(prediction.get("label", "")).strip().lower()
        confidence = float(prediction.get("score", 0.0))

        # This model is trained for SMS spam/ham, not misinformation.
        # Map the model's spam class to suspicious; do not call it proof of fraud.
        suspicious = raw_label in {"spam", "label_1", "1"}
        label = "AI_SUSPICIOUS" if suspicious else "AI_LIKELY_SAFE"

        return {
            "available": True,
            "label": label,
            "confidence": round(confidence, 4),
            "explanation": (
                "The pretrained SMS model classified this text as spam-like."
                if suspicious
                else "The pretrained SMS model did not classify this text as spam-like."
            ),
            "model": MODEL_NAME,
            "raw_label": raw_label,
            "scope_note": (
                "This model detects SMS-spam-like patterns. It is not a general "
                "fake-news detector, and a safe prediction does not prove safety."
            ),
        }
    except Exception as exc:
        return {
            "available": False,
            "label": "AI_UNAVAILABLE",
            "confidence": None,
            "explanation": (
                "AI model could not load. Check that transformers and torch are "
                "installed and that the model can be downloaded. Existing rules "
                "can continue to run."
            ),
            "error": str(exc),
            "model": MODEL_NAME,
        }
