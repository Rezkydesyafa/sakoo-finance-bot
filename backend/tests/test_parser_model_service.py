from datetime import date

from app.modules.parser.category_classifier import load_category_model, predict_category
from app.modules.parser.service import parse_message


def test_category_model_can_be_loaded_and_predicts_main_categories() -> None:
    model_bundle = load_category_model()
    assert model_bundle is not None
    assert "pipeline" in model_bundle
    assert model_bundle["metrics"]["baseline_accuracy"] >= 0.9
    assert model_bundle["metrics"]["keyword_smoke_accuracy"] >= 0.9

    food_prediction = predict_category("beli nasi padang")
    assert food_prediction is not None
    assert food_prediction.category == "Makanan"
    assert food_prediction.confidence > 0

    income_prediction = predict_category("gaji masuk bulan ini", transaction_type="income")
    assert income_prediction is not None
    assert income_prediction.category == "Gaji"

    transport_prediction = predict_category("ojol ke stasiun 20rb")
    assert transport_prediction is not None
    assert transport_prediction.category == "Transportasi"

    bill_prediction = predict_category("pln prabayar 100rb")
    assert bill_prediction is not None
    assert bill_prediction.category == "Tagihan"


def test_parse_message_returns_prd_json_shape_for_transaction() -> None:
    result = parse_message(
        "beli makan 20 ribu",
        source="whatsapp_text",
        today=date(2026, 6, 27),
    )
    payload = result.to_dict()

    assert payload["intent"] == "add_transaction"
    assert payload["type"] == "expense"
    assert payload["amount"] == 20000
    assert payload["category"] == "Makanan"
    assert payload["description"] == "beli makan"
    assert payload["transaction_date"] == "2026-06-27"
    assert payload["source"] == "whatsapp_text"
    assert payload["confidence"] >= 0.85
    assert payload["need_confirmation"] is False


def test_parse_message_detects_command_without_transaction_fields() -> None:
    result = parse_message(
        "export laporan bulan ini",
        source="whatsapp_text",
        today=date(2026, 6, 27),
    )
    payload = result.to_dict()

    assert payload["intent"] == "export_pdf"
    assert payload["type"] is None
    assert payload["amount"] is None
    assert payload["category"] is None
    assert payload["period"] == "month"
    assert payload["need_confirmation"] is False


def test_parse_message_low_confidence_requires_confirmation() -> None:
    result = parse_message(
        "keluar 20 ribu",
        source="whatsapp_text",
        today=date(2026, 6, 27),
    )
    payload = result.to_dict()

    assert payload["intent"] == "add_transaction"
    assert payload["confidence"] < 0.85
    assert payload["need_confirmation"] is True
    assert "category_fallback" in payload["reasons"]
