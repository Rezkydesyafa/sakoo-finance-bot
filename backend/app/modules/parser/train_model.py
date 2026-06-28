from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion
from sklearn.pipeline import Pipeline

try:
    from app.modules.parser.normalization import normalize_category_text
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from app.modules.parser.normalization import normalize_category_text


PARSER_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET_PATH = PARSER_DIR / "data" / "category_dataset.csv"
DEFAULT_MODEL_PATH = PARSER_DIR / "models" / "category_classifier.joblib"
DEFAULT_METRICS_PATH = PARSER_DIR / "models" / "category_metrics.json"
RANDOM_STATE = 42
SMOKE_EVALUATION_CASES: tuple[tuple[str, str], ...] = (
    ("makan ramen 45rb", "Makanan"),
    ("ojol ke stasiun 20rb", "Transportasi"),
    ("pln prabayar 100rb", "Tagihan"),
    ("beli hoodie online", "Belanja"),
    ("tiket dufan", "Hiburan"),
    ("cabut gigi dokter", "Kesehatan"),
    ("spp anak bulan ini", "Pendidikan"),
    ("salary remote job", "Gaji"),
    ("dividen bca", "Tabungan"),
    ("uang kas komplek", "Lainnya"),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train TF-IDF + Logistic Regression category classifier.",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--model-out", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--metrics-out", type=Path, default=DEFAULT_METRICS_PATH)
    args = parser.parse_args()

    metrics = train_and_save(
        dataset_path=args.dataset,
        model_path=args.model_out,
        metrics_path=args.metrics_out,
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


def train_and_save(
    *,
    dataset_path: Path = DEFAULT_DATASET_PATH,
    model_path: Path = DEFAULT_MODEL_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
) -> dict[str, Any]:
    raw_rows = _load_dataset(dataset_path)
    rows = _augment_rows(raw_rows)
    texts = [row["text"] for row in rows]
    labels = [row["category"] for row in rows]
    category_types = _category_types(raw_rows)

    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=0.25,
        random_state=RANDOM_STATE,
        stratify=labels,
    )

    evaluation_pipeline = _build_pipeline()
    evaluation_pipeline.fit(x_train, y_train)
    predictions = evaluation_pipeline.predict(x_test)

    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": _display_path(dataset_path),
        "model_path": _display_path(model_path),
        "dataset_rows": len(raw_rows),
        "training_rows": len(rows),
        "train_rows": len(x_train),
        "test_rows": len(x_test),
        "labels": sorted(set(labels)),
        "label_distribution": dict(sorted(Counter(labels).items())),
        "baseline_accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "classification_report": classification_report(
            y_test,
            predictions,
            output_dict=True,
            zero_division=0,
        ),
    }

    final_pipeline = _build_pipeline()
    final_pipeline.fit(texts, labels)
    metrics.update(_evaluate_smoke_cases(final_pipeline))
    model_bundle = {
        "pipeline": final_pipeline,
        "category_types": category_types,
        "metrics": metrics,
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_bundle, model_path)

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metrics


def _load_dataset(dataset_path: Path) -> list[dict[str, str]]:
    with dataset_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    required_columns = {"text", "category", "type"}
    if not rows:
        raise ValueError("Dataset is empty.")
    if set(rows[0]) != required_columns:
        raise ValueError(f"Dataset columns must be exactly: {sorted(required_columns)}")

    for row in rows:
        if not row["text"] or not row["category"] or row["type"] not in {"income", "expense"}:
            raise ValueError(f"Invalid dataset row: {row}")

    return rows


def _augment_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    variants: dict[tuple[str, str], dict[str, str]] = {}
    suffixes = (
        "",
        " 20 ribu",
        " 35rb",
        " rp50.000",
        " kemarin",
        " hari ini",
        " bulan ini",
    )
    prefixes = ("", "catat ", "bayar ", "beli ", "pengeluaran ")

    for row in rows:
        text = row["text"].strip()
        category = row["category"]
        transaction_type = row["type"]
        source_texts = [text]

        if transaction_type == "income":
            source_texts.extend([f"terima {text}", f"pemasukan {text}", f"masuk {text}"])
            active_prefixes = ("", "catat ", "terima ")
        else:
            source_texts.extend([f"biaya {text}", f"pengeluaran {text}"])
            active_prefixes = prefixes

        for source_text in source_texts:
            for prefix in active_prefixes:
                for suffix in suffixes:
                    candidate = f"{prefix}{source_text}{suffix}".strip()
                    normalized_candidate = normalize_category_text(candidate)
                    key = (normalized_candidate, category)
                    variants[key] = {
                        "text": candidate,
                        "category": category,
                        "type": transaction_type,
                    }

    return list(variants.values())


def _category_types(rows: list[dict[str, str]]) -> dict[str, str]:
    category_types: dict[str, str] = {}
    for row in rows:
        existing = category_types.setdefault(row["category"], row["type"])
        if existing != row["type"]:
            raise ValueError(f"Category {row['category']} has mixed transaction types.")
    return category_types


def _build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            (
                "features",
                FeatureUnion(
                    transformer_list=[
                        (
                            "word_tfidf",
                            TfidfVectorizer(
                                lowercase=False,
                                preprocessor=normalize_category_text,
                                analyzer="word",
                                ngram_range=(1, 3),
                                min_df=1,
                                sublinear_tf=True,
                            ),
                        ),
                        (
                            "char_tfidf",
                            TfidfVectorizer(
                                lowercase=False,
                                preprocessor=normalize_category_text,
                                analyzer="char_wb",
                                ngram_range=(3, 5),
                                min_df=1,
                                sublinear_tf=True,
                            ),
                        ),
                    ]
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def _evaluate_smoke_cases(pipeline: Pipeline) -> dict[str, Any]:
    predictions = pipeline.predict([text for text, _label in SMOKE_EVALUATION_CASES])
    cases = []
    correct_count = 0
    for (text, expected), predicted in zip(
        SMOKE_EVALUATION_CASES,
        predictions,
        strict=True,
    ):
        is_correct = predicted == expected
        correct_count += int(is_correct)
        cases.append(
            {
                "text": text,
                "expected": expected,
                "predicted": str(predicted),
                "correct": is_correct,
            }
        )

    return {
        "keyword_smoke_accuracy": round(
            correct_count / len(SMOKE_EVALUATION_CASES),
            4,
        ),
        "keyword_smoke_cases": cases,
    }


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PARSER_DIR).as_posix()
    except ValueError:
        return resolved.as_posix()


if __name__ == "__main__":
    main()
