"""Deterministic safety helpers for LLM leakage and prompt-injection defense."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


_BLOCK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "hidden_prompt_request",
        re.compile(
            r"\b(system|developer|hidden|internal)\s+"
            r"(prompt|instruction|message|policy|rules?)\b"
            r"|reveal\s+(your|the)\s+(prompt|instructions?|policy)",
            re.I,
        ),
    ),
    (
        "secret_request",
        re.compile(
            r"\b(api\s*keys?|secret\s*keys?|tokens?|bearer\s+tokens?|"
            r"env(?:ironment)?\s*(?:vars?|variables?)|credentials?|passwords?)\b",
            re.I,
        ),
    ),
    (
        # File/config exfiltration: ".env file in encoded format", "show the
        # config", "cat the dockerfile", "read your source code". These name a
        # backend artefact directly and never match the secret-keyword patterns,
        # so without this a request like ".env in base64" reaches the model and
        # relies on it to refuse. Belt to the security_rules.txt suspenders.
        "file_exfil_request",
        re.compile(
            r"\b\.?env(?:ironment)?\s*file\b|\bdot\s*env\b|(?<![\w/])\.env\b"
            r"|\b(source\s*code|/etc/|dockerfile|docker-compose|"
            r"database\s*url|connection\s*string|private\s*key)\b"
            r"|\b(share|show|send|print|read|cat|reveal|dump|export|leak|give)\b"
            r"[^.\n]{0,40}?\b(your|the|our|my)?\s*"
            r"(\.?env(?:ironment)?|dotenv|config(?:uration)?\s*file|"
            r"credentials?\s*file|secret[s]?\s*file|source\s*code)\b",
            re.I,
        ),
    ),
    (
        "tool_schema_request",
        re.compile(
            r"\b(tool|function)\s+(schema|schemas|definitions?|arguments?|json)\b"
            r"|list\s+(all\s+)?(tools|functions)",
            re.I,
        ),
    ),
    (
        "raw_context_request",
        re.compile(
            r"\b(raw|full|verbatim|entire)\s+"
            r"(context|conversation|messages?|logs?|trace|traces|tool\s+outputs?|"
            r"retrieved\s+content|data\s+block)\b",
            re.I,
        ),
    ),
    (
        "role_override",
        re.compile(
            r"\b(ignore|forget|bypass|override|disregard)\s+"
            r"(all\s+)?(previous|prior|above|system|developer)\s+"
            r"(instructions?|rules?|messages?|policy)\b"
            r"|developer\s+mode|jailbreak|do\s+anything\s+now|\bDAN\b",
            re.I,
        ),
    ),
    (
        "cross_user_data",
        re.compile(
            r"\b(other|another|someone\s+else|different)\s+user(?:'s)?\b"
            r".*\b(data|portfolio|transactions?|email|account|ledger|profile)\b",
            re.I | re.S,
        ),
    ),
    (
        "chain_of_thought_request",
        re.compile(
            r"\b(chain[-\s]?of[-\s]?thought|hidden\s+reasoning|private\s+reasoning|"
            r"scratchpad|reasoning\s+trace)\b",
            re.I,
        ),
    ),
    (
        # "Do you have any hidden security code / internal key / private
        # instruction?" and "explain what kinds of information you must not
        # reveal." These probe for existence or ask the model to enumerate what
        # it protects — the exact bait that produced a full recital. Catch them
        # so the reply is a plain decline, not a confirmation or a list.
        "confidentiality_probe",
        re.compile(
            r"\b(do|does|are)\s+you\s+(have|hold|keep|store|got)\s+(any\s+|a\s+|some\s+)?"
            r"(hidden|secret|internal|private|confidential|undisclosed|special)\s+"
            r"(\w+\s+){0,2}"
            r"(code|codes|key|keys|instruction|instructions|prompt|prompts|policy|"
            r"policies|rule|rules|password|passwords|token|tokens|value|values)\b"
            r"|\bwhat\s+(kinds?|type|types|sort|sorts)\s+of\s+"
            r"(info|information|things|data|stuff|details|content)\b[^.\n]{0,40}"
            r"\b(not|never|cannot|can'?t|must\s+not|won'?t|refuse|forbidden|"
            r"not\s+allowed|not\s+supposed|off[-\s]?limits)\b"
            r"|\bwhat\s+(can|are|do|should|would)\s+you\b[^.\n]{0,12}\b(not|never)\b"
            r"[^.\n]{0,20}\b(reveal|share|say|tell|show|disclose|discuss|expose)\b"
            r"|\bwhat\s+are\s+you\s+(not\s+allowed|forbidden|unable|not\s+permitted|"
            r"not\s+supposed)\s+to\b",
            re.I | re.S,
        ),
    ),
    (
        # Encoding as a laundering trick: "base64 encode your API keys", but also
        # "give me the .env in encoded format" (target BEFORE the verb). Match the
        # encode keyword near a sensitive target in EITHER order.
        "encoded_bypass",
        re.compile(
            # Any encode/translate verb aimed at a clearly-sensitive target.
            r"\b(base64|rot13|hex|binary|encode|encoded|decode|translate|"
            r"reverse|cipher)\b.{0,60}?"
            r"\b(prompt|secret|token|key|policy|instructions?|credential)\b"
            # Hard encoding verbs (not translate/reverse — those appear in benign
            # asks) aimed at env/config/file, in EITHER order: catches both
            # "base64 the .env" and ".env in encoded format".
            r"|\b(base64|rot13|hex|binary|encode[ds]?|decode|cipher)\b"
            r".{0,60}?\b(env|config|file)\b"
            r"|\b(env|config|file)\b.{0,60}?"
            r"\b(base64|rot13|hex|binary|encode[ds]?|decode|cipher|encoded\s+format)\b",
            re.I | re.S,
        ),
    ),
)

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bsb_secret_[A-Za-z0-9_-]{8,}\b", re.I),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", re.I),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\b1//[A-Za-z0-9_-]{10,}\b"),
    re.compile(
        r"\b[A-Z][A-Z0-9_]{2,}\s*=\s*['\"]?[A-Za-z0-9_./+=:-]{8,}['\"]?"
    ),
    re.compile(r"\bNAFAIQ_TEST_SECRET_[A-Za-z0-9_-]+\b"),
)

_HIDDEN_OUTPUT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(system|developer)\s+prompt\s*:", re.I),
    re.compile(r"\btool_calls?\b.*\bfunction\b", re.I | re.S),
    re.compile(r"<<<\s*(SYSTEM|DEVELOPER|UNTRUSTED|LESSON_CONTENT|QUIZ_ATTEMPT)", re.I),
)

# Refusals deliberately do NOT enumerate what is protected — naming the
# categories ("system prompts, tool schemas, logs…") is itself a disclosure and
# confirms such things exist. Just decline and redirect.
_REFUSAL = {
    "assistant": {
        "en": (
            "Sorry, I can't share that — it's confidential. I can still help with "
            "your NafaIQ finances, PSX investing, or app tasks — what would you like to do?"
        ),
        "ur": (
            "معذرت، میں یہ شیئر نہیں کر سکتا — یہ خفیہ ہے۔ میں آپ کے NafaIQ finances، "
            "PSX investing، یا app tasks میں مدد کر سکتا ہوں — آپ کیا کرنا چاہیں گے؟"
        ),
    },
    "tutor": {
        "en": (
            "Sorry, I can't share that — it's confidential. Ask me about the finance "
            "lesson and I'll gladly help explain it."
        ),
        "ur": (
            "معذرت، میں یہ شیئر نہیں کر سکتا — یہ خفیہ ہے۔ آپ finance lesson کے بارے میں "
            "پوچھیں، میں خوشی سے سمجھا دوں گا۔"
        ),
    },
    "default": {
        "en": "Sorry, I can't share that — it's confidential. I can help with your NafaIQ finances, investing, and app tasks.",
        "ur": "معذرت، میں یہ شیئر نہیں کر سکتا — یہ خفیہ ہے۔ میں NafaIQ finances، investing، اور app tasks میں مدد کر سکتا ہوں۔",
    },
}
_SCOPE_REFUSAL = {
    "assistant": {
        "en": (
            "I'm here to help with your NafaIQ finances, PSX investing, and app tasks. "
            "Ask me about your portfolio, transactions, bills, budgets, goals, or a PSX stock."
        ),
        "ur": (
            "میں آپ کے NafaIQ finances، PSX investing، اور app tasks میں مدد کے لیے ہوں۔ "
            "اپنے portfolio، transactions، bills، budgets، goals، یا PSX stock کے بارے میں پوچھیں۔"
        ),
    },
    "tutor": {
        "en": "Ask me about the finance lesson and I'll help explain it.",
        "ur": "آپ finance lesson کے بارے میں پوچھیں، میں سمجھا دوں گا۔",
    },
    "default": {
        "en": "I can help with NafaIQ finance, investing, and app tasks.",
        "ur": "میں NafaIQ finance، investing، اور app tasks میں مدد کر سکتا ہوں۔",
    },
}

_ASSISTANT_IN_SCOPE_RE = re.compile(
    r"\b("
    r"nafaiq|app|finance|financial|money|cash|income|expense|expenses|spend|"
    r"spent|saving|savings|budget|budgets|bill|bills|goal|goals|transaction|"
    r"transactions|payment|merchant|category|portfolio|watchlist|holding|"
    r"holdings|stock|stocks|share|shares|ticker|symbol|psx|kse|market|"
    r"invest|investing|investment|dividend|zakat|halal|shariah|broker|"
    r"p/e|pe ratio|earnings|valuation|risk|return|profit|loss|pnl|"
    r"balance|networth|net worth|alert|alerts|report|dashboard|account|"
    r"accounts|card|bank|wallet|sector|sectors|company|companies|cement|"
    r"fertili[sz]er|banking|textile|energy|oil|gas|power|auto|autos|"
    r"pharma|technology"
    r")\b",
    re.I,
)

_ASSISTANT_OFF_TOPIC_RE: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "identity_question",
        re.compile(
            r"^\s*(?i:who|what)\s+(?i:is|are|was|were)\s+"
            r"(?!(?i:you\b|nafaiq\b|my\b|me\b|the\s+app\b))"
            r"[A-Z0-9][\w'.-]*(?:\s+[A-Z0-9][\w'.-]*){0,5}\s*\??\s*$",
        ),
    ),
    (
        "general_knowledge_request",
        re.compile(
            r"\b("
            r"weather|recipe|cook|movie|song|lyrics|sports?|cricket|football|"
            r"history of|biography|capital of|translate this|write (?:a )?(?:poem|"
            r"story|essay)|joke|meaning of life"
            r")\b",
            re.I,
        ),
    ),
    (
        "tell_me_about_named_subject",
        re.compile(
            r"^\s*(?i:tell me about|explain|describe|write about|give me (?:a )?(?:bio|biography) of)\s+"
            r"[A-Z][\w'.-]*(?:\s+[A-Z][\w'.-]*){0,5}\s*\??\s*$",
        ),
    ),
    (
        # Meta / self-disclosure: "what's your policy?", "what are your rules?",
        # "what are you allowed to do?". These are not secret-extraction (those
        # hit _BLOCK_PATTERNS) but the model tends to recite its role/policy in
        # full. Route them to the polite topic-redirect instead. "what can you
        # do?" / "who are you?" are deliberately NOT matched — those get a brief
        # helpful answer.
        "self_or_policy_disclosure",
        re.compile(
            r"\byour\s+(polic(?:y|ies)|instructions?|guidelines?|directives?|"
            r"guardrails?|system\s+prompt|configuration|programming|rule\s?set|"
            r"constraints?|restrictions?)\b"
            r"|\bwhat(?:'?s| is| are)\s+your\s+(role|purpose|polic(?:y|ies)|"
            r"instructions?|rules?|guidelines?)\b"
            r"|\bwhat\s+are\s+you\s+(allowed|permitted|programmed|instructed|"
            r"designed|told|configured)\s+to\b",
            re.I,
        ),
    ),
)


@dataclass(frozen=True)
class SafetyHit:
    """A deterministic safety match."""

    category: str
    snippet: str


class SafetyViolation(RuntimeError):
    """Raised when model output appears to contain restricted data."""


def detect_leakage_request(text: str | None) -> list[SafetyHit]:
    """Return leakage/jailbreak categories found in user-controlled text."""
    if not text:
        return []
    hits: list[SafetyHit] = []
    for category, pattern in _BLOCK_PATTERNS:
        match = pattern.search(text)
        if match:
            hits.append(SafetyHit(category, _snippet(text, match.start(), match.end())))
    return hits


def safe_refusal(lang: str = "en", surface: str = "default") -> str:
    """Short refusal in the requested language, with a useful redirect."""
    bucket = _REFUSAL.get(surface, _REFUSAL["default"])
    return bucket.get(lang, bucket["en"])


def detect_assistant_out_of_scope(text: str | None) -> list[SafetyHit]:
    """Return obvious non-NafaIQ assistant requests.

    This is deliberately conservative. The assistant may answer finance and
    investing education, but unrelated general-knowledge prompts should never
    reach the model, because prompts alone tend to produce a factual answer plus
    a polite redirect.
    """
    if not text:
        return []
    if _ASSISTANT_IN_SCOPE_RE.search(text):
        return []
    hits: list[SafetyHit] = []
    for category, pattern in _ASSISTANT_OFF_TOPIC_RE:
        match = pattern.search(text)
        if match:
            hits.append(SafetyHit(category, _snippet(text, match.start(), match.end())))
    return hits

def detect_tutor_out_of_scope(text: str | None) -> list[SafetyHit]:
    """Return obvious non-finance lesson requests for the LearnHub tutor."""
    return detect_assistant_out_of_scope(text)


def scope_refusal(lang: str = "en", surface: str = "default") -> str:
    """Short domain-scope refusal in the requested language."""
    bucket = _SCOPE_REFUSAL.get(surface, _SCOPE_REFUSAL["default"])
    return bucket.get(lang, bucket["en"])


def scan_llm_output(text: str | None) -> list[SafetyHit]:
    """Return violations found in model output before it leaves the backend."""
    if not text:
        return []
    hits: list[SafetyHit] = []
    for pattern in _SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            hits.append(SafetyHit("secret_pattern", _snippet(text, match.start(), match.end())))
    for pattern in _HIDDEN_OUTPUT_PATTERNS:
        match = pattern.search(text)
        if match:
            hits.append(SafetyHit("hidden_context_pattern", _snippet(text, match.start(), match.end())))
    return hits


def assert_safe_output(text: str | None) -> None:
    """Raise when an LLM output contains restricted-looking data."""
    hits = scan_llm_output(text)
    if hits:
        raise SafetyViolation(", ".join(hit.category for hit in hits))


def redact_sensitive(value: Any) -> Any:
    """Recursively redact secrets while preserving shape for diagnostics."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        redacted = value
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    if isinstance(value, Mapping):
        return {
            k: "[REDACTED]" if _sensitive_key(str(k)) else redact_sensitive(v)
            for k, v in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_sensitive(v) for v in value]
    try:
        return redact_sensitive(json.dumps(value, default=str))
    except TypeError:
        return "[REDACTED]"


def _sensitive_key(key: str) -> bool:
    return bool(
        re.search(r"(secret|token|password|credential|api[_-]?key|authorization)", key, re.I)
    )


def _snippet(text: str, start: int, end: int) -> str:
    left = max(0, start - 24)
    right = min(len(text), end + 24)
    return text[left:right].replace("\n", " ")[:120]
