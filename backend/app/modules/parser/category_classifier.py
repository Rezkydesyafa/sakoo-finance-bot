from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib


PARSER_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = PARSER_DIR / "models" / "category_classifier.joblib"


@dataclass(frozen=True)
class CategoryPrediction:
    category: str
    confidence: float
    source: str = "model"

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "confidence": round(self.confidence, 4),
            "source": self.source,
        }


@lru_cache(maxsize=1)
def load_category_model(model_path: str | Path = DEFAULT_MODEL_PATH) -> dict[str, Any] | None:
    path = Path(model_path)
    if not path.exists():
        return None
    return joblib.load(path)


def predict_category(
    text: str | None,
    *,
    transaction_type: str | None = None,
) -> CategoryPrediction | None:
    if not text:
        return None

    bundle = load_category_model()
    if not bundle:
        return None

    pipeline = bundle["pipeline"]
    category_types: dict[str, str] = bundle.get("category_types", {})
    probabilities = pipeline.predict_proba([text])[0]
    classes = list(pipeline.classes_)
    ranked = sorted(
        zip(classes, probabilities, strict=True),
        key=lambda item: item[1],
        reverse=True,
    )

    for category, probability in ranked:
        if transaction_type and category_types.get(category) not in {None, transaction_type}:
            continue
        return CategoryPrediction(
            category=str(category),
            confidence=float(probability),
        )

    return None
