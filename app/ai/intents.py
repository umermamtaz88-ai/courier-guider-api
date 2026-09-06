import re
from enum import Enum


class Intent(str, Enum):
    COMPARE_PROVIDERS = "compare_providers"
    GET_SHIPPING_QUOTE = "get_shipping_quote"
    PLAN_SHIPMENT = "plan_shipment"
    REQUIRED_DOCUMENTS = "required_documents"
    TRACK_SHIPMENT = "track_shipment"
    SHIPMENT_STATUS = "shipment_status"
    SHIPMENT_DELAY = "shipment_delay"
    DELIVERY_FAILURE = "delivery_failure"
    RETURN = "return"
    REFUND = "refund"
    COD_SETTLEMENT = "cod_settlement"
    CLAIM = "claim"
    PROVIDER_POLICY = "provider_policy"
    ANALYZE_DOCUMENTS = "analyze_documents"
    EXPLAIN_ISSUE = "explain_issue"
    DRAFT_MESSAGE = "draft_message"
    GREETING = "greeting"
    OTHER = "other"


CURRENT_DATA_INTENTS = {
    Intent.TRACK_SHIPMENT,
    Intent.SHIPMENT_STATUS,
    Intent.GET_SHIPPING_QUOTE,
    Intent.SHIPMENT_DELAY,
}

RAG_INTENTS = {
    Intent.REQUIRED_DOCUMENTS,
    Intent.PROVIDER_POLICY,
    Intent.RETURN,
    Intent.REFUND,
    Intent.CLAIM,
    Intent.COD_SETTLEMENT,
    Intent.COMPARE_PROVIDERS,
}

INTENT_PATTERNS: list[tuple[Intent, re.Pattern[str]]] = [
    (
        Intent.GREETING,
        re.compile(
            r"^\s*(hi|hello|hey|hola|salam|assalamualaikum|good\s+(morning|afternoon|evening)|thanks|thank you|thx|bye|goodbye)[\s!.?]*$",
            re.I,
        ),
    ),
    (Intent.TRACK_SHIPMENT, re.compile(r"\b(where is|track|tracking|parcel location)\b", re.I)),
    (Intent.COMPARE_PROVIDERS, re.compile(r"\b(which courier|best courier|compare provider|cheapest|fastest)\b", re.I)),
    (Intent.GET_SHIPPING_QUOTE, re.compile(r"\b(how much|cost|quote|price)\b", re.I)),
    (Intent.REQUIRED_DOCUMENTS, re.compile(r"\b(documents?|paperwork|invoice|packing list|certificate)\b", re.I)),
    (Intent.RETURN, re.compile(r"\b(return|refused delivery|customer refused)\b", re.I)),
    (Intent.REFUND, re.compile(r"\b(refund)\b", re.I)),
    (Intent.CLAIM, re.compile(r"\b(claim|lost|damaged|missing contents)\b", re.I)),
    (Intent.COD_SETTLEMENT, re.compile(r"\b(cod|cash on delivery|settlement)\b", re.I)),
    (Intent.SHIPMENT_DELAY, re.compile(r"\b(delay|delayed|late)\b", re.I)),
    (Intent.DELIVERY_FAILURE, re.compile(r"\b(delivery failed|failed delivery)\b", re.I)),
    (Intent.PROVIDER_POLICY, re.compile(r"\b(policy|terms|procedure)\b", re.I)),
    (Intent.PLAN_SHIPMENT, re.compile(r"\b(ship|send|export|import)\b", re.I)),
]


class IntentDetector:
    def detect(self, message: str) -> Intent:
        for intent, pattern in INTENT_PATTERNS:
            if pattern.search(message):
                return intent
        return Intent.OTHER

    def needs_live_data(self, intent: Intent) -> bool:
        return intent in CURRENT_DATA_INTENTS

    def needs_rag(self, intent: Intent) -> bool:
        return intent in RAG_INTENTS or intent == Intent.OTHER
