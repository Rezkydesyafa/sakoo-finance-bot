"""Channel-neutral ordering for inbound bot message handlers."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar

VoiceResult = TypeVar("VoiceResult")
ReceiptResult = TypeVar("ReceiptResult")
ReportResult = TypeVar("ReportResult")
TransactionResult = TypeVar("TransactionResult")


@dataclass(frozen=True)
class ChannelFlowResult(
    Generic[VoiceResult, ReceiptResult, ReportResult, TransactionResult]
):
    voice: VoiceResult | None = None
    receipt: ReceiptResult | None = None
    report_pdf: ReportResult | None = None
    transaction: TransactionResult | None = None


def run_channel_flow(
    *,
    voice: Callable[[], VoiceResult | None],
    receipts: Iterable[Callable[[], ReceiptResult | None]],
    report_pdf: Callable[[], ReportResult | None],
    transaction: Callable[[], TransactionResult | None],
) -> ChannelFlowResult[VoiceResult, ReceiptResult, ReportResult, TransactionResult]:
    voice_result = voice()
    if voice_result is not None:
        return ChannelFlowResult(voice=voice_result)

    receipt_result = _first_handled(receipts)
    if receipt_result is not None:
        return ChannelFlowResult(receipt=receipt_result)

    report_result = report_pdf()
    if report_result is not None:
        return ChannelFlowResult(report_pdf=report_result)

    return ChannelFlowResult(transaction=transaction())


def _first_handled(
    steps: Iterable[Callable[[], ReceiptResult | None]],
) -> ReceiptResult | None:
    for step in steps:
        result = step()
        if result is not None:
            return result
    return None
