from app.ai.intents import Intent, IntentDetector


def test_refund_intent():
    detector = IntentDetector()
    assert detector.detect("How do I refund the customer?") == Intent.REFUND
    assert detector.needs_rag(Intent.REFUND)


def test_document_intent():
    detector = IntentDetector()
    assert detector.detect("What documents do I need for customs?") == Intent.REQUIRED_DOCUMENTS
