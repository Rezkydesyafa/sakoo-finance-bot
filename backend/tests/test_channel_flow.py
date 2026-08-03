from app.modules.bot.channel_flow import run_channel_flow


def test_channel_flow_stops_after_first_handled_step() -> None:
    calls: list[str] = []

    def step(name: str, result: str | None = None):
        def run() -> str | None:
            calls.append(name)
            return result

        return run

    result = run_channel_flow(
        voice=step("voice"),
        receipts=(step("receipt-image"), step("receipt-text", "receipt")),
        report_pdf=step("pdf", "pdf"),
        transaction=step("transaction", "transaction"),
    )

    assert calls == ["voice", "receipt-image", "receipt-text"]
    assert result.receipt == "receipt"
    assert result.report_pdf is None
    assert result.transaction is None
