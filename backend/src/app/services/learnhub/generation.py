"""Grounded generation over the LearnHub corpus — quiz explanations + summaries.

Two rules define this module:

1. NOTHING is generated without retrieved content. If retrieval comes back
   empty, we return None and the caller falls back to its bundled static text.
   An LLM asked to explain a lesson it wasn't shown will invent one fluently,
   and invented course material is worse than no explanation at all.
2. The model cannot cite what it wasn't shown. `sources` is filtered HERE
   against the section_ids retrieval actually returned — the client deep-links
   those ids, so a hallucinated one is a broken link presented as a reference.

Failure posture matches retrieval.py: every failure path returns None rather
than raising. These surfaces are enhancements over content the client already
has, so a provider outage must degrade to that content, never to an error.

Nothing here touches the AI tutor. See tests/test_tutor_isolation.py.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import structlog
from pydantic import BaseModel, ConfigDict

from app.config import settings
from app.services.ai.prompts import load_prompt, security_rules
from app.services.ai.providers import (
    aclose_report_client,
    generate_structured,
    make_report_client,
)
from app.services.learnhub import retrieval

log = structlog.get_logger(__name__)

# Delimiters for the two data blocks. Module constants, not literals, because
# the prompt-injection tests assert that chunk/question text appears ONLY
# between them — the boundary is the defense, so it is named and pinned.
DATA_BLOCK_OPEN = "<<<LESSON_CONTENT"
DATA_BLOCK_CLOSE = "LESSON_CONTENT>>>"
QUIZ_BLOCK_OPEN = "<<<QUIZ_ATTEMPT"
QUIZ_BLOCK_CLOSE = "QUIZ_ATTEMPT>>>"

# How many chunks to ground on. Enough for a lesson's worth of context without
# burning the free tier's token budget on a 2-4 sentence answer.
_RETRIEVE_LIMIT = 6


class QuizExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation: str
    sources: list[str]


class LessonSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_ideas: list[str]
    terms: list[str]
    pitfall: Optional[str]
    sources: list[str]


# ===========================================================================
# Prompt
# ===========================================================================

# Shared scaffold, loaded from prompts/learnhub_rules.txt. Deliberately mirrors
# the report prompt's trust engineering (services/ai/specs.py): output language,
# a delimited block whose contents are DATA never instructions, and the
# educational/no-advice guardrail. It does not reuse that module — reports carry
# citations, verification and a disclaimer field that make no sense for a
# two-sentence quiz explanation. Formatted with .format(lang=...) at each call.
_RULES = security_rules() + "\n\n" + load_prompt("learnhub_rules")


def _content_block(rows: list[dict]) -> str:
    """The retrieved chunks, one labelled entry each, inside the data block."""
    entries = []
    for row in rows:
        header = " | ".join(
            part
            for part in (
                f"section_id={row.get('section_id') or 'none'}",
                row.get("title") or "",
                row.get("heading") or "",
            )
            if part
        )
        # text_en, NOT snippet_en: the snippet is a 240-char DISPLAY cut for
        # the search UI. Grounding on it gave the model ~53% of a lesson —
        # opening sentences only — so answers silently lost everything in the
        # back half of every section.
        # English even for Urdu output: the corpus is embedded in English and
        # text_ur may lag it; the language rule in _RULES drives the response.
        body = row.get("text_en") or row.get("snippet_en") or ""
        entries.append(f"[{header}]\n{body}")
    return "\n\n".join(entries)


def _claimed_to_ids(claimed: list[str], rows: list[dict]) -> list[str]:
    """Resolve what the model wrote in `sources` to retrieved section_ids.

    Accepts the section_id OR the section's heading, because the model cites
    either. Live against the real index, gemini-3.1-flash-lite answered a
    pe-ratio summary with
        sources=["Understanding P/E Ratio | What the P/E Ratio Tells You"]
    — it copied the data block's whole header line instead of the `section_id=`
    value in it. Those claims resolved to nothing and the learner got a grounded
    summary with its citations silently stripped. Prompt wording did not fix
    this reliably; accepting the label the model actually reaches for does.

    This is NOT a weaker filter, which is the point: every key in the map comes
    from `rows`, so an id or heading the model invented still resolves to
    nothing. Rows without a section_id (glossary_term, lesson_overview) ground
    the answer but stay uncitable — the client deep-links these ids and there is
    nothing to link to.
    """
    by_key: dict[str, str] = {}
    for row in rows:
        sid = row.get("section_id")
        if not sid:
            continue
        by_key.setdefault(sid.strip().lower(), sid)
        heading = (row.get("heading") or "").strip().lower()
        if heading:
            by_key.setdefault(heading, sid)

    kept: list[str] = []
    for claim in claimed:
        # Second candidate: the trailing segment of a copied "title | heading"
        # header line.
        for key in (claim.strip().lower(), claim.rsplit("|", 1)[-1].strip().lower()):
            sid = by_key.get(key)
            if sid:
                if sid not in kept:
                    kept.append(sid)
                break
    return kept


def _sources_for_display(section_ids: list[str], rows: list[dict]) -> list[str]:
    """section_id -> the section's heading.

    The model cites ids (stable, and what the data block labels each chunk
    with), but both UIs render `sources` straight to the learner, and the
    client contract calls them "Cited section headings". Shipping raw slugs
    put "what-is-a-dividend" under a summary. Falls back to the de-slugged
    words if a heading is somehow absent — never shows a raw slug.
    """
    heading_by_id = {
        r["section_id"]: (r.get("heading") or "").strip()
        for r in rows
        if r.get("section_id")
    }
    out: list[str] = []
    for sid in section_ids:
        label = heading_by_id.get(sid) or _slug_words(sid)
        if label and label not in out:
            out.append(label)
    return out


def _slug_words(slug: str) -> str:
    """"what-is-a-dividend" -> "what is a dividend". Retrieval is already scoped
    to the lesson, so the slug's words only need to rank sections within it."""
    return slug.replace("-", " ").replace("_", " ").strip()


# ===========================================================================
# Generation
# ===========================================================================
async def _generate(
    *,
    response_model: type[BaseModel],
    system: str,
    user: str,
    report_type: str,
    lang: str,
) -> Optional[BaseModel]:
    """One structured generation with the engine's lifecycle discipline: a
    wall-clock deadline INSIDE the try (so the deadline firing still releases
    the pool) and an unconditional close in `finally`.

    make_report_client builds an httpx.AsyncClient that AsyncOpenAI does not own,
    so without the close every call — including the failure paths — would strand
    a connection pool for the life of the process (engine.py learned this).

    Routed as non-confidential: the corpus is published course material and the
    only user-derived value in the prompt is which multiple-choice option was
    picked. No portfolio, finance or identity data reaches this prompt, so it
    belongs on the free tier rather than the paid confidential one.
    """
    try:
        client = make_report_client(confidential=False)
    except Exception:
        log.warning("learn_ai_client_failed", report_type=report_type, exc_info=True)
        return None

    try:
        # Reuses the report deadline: same provider, same structured-output call
        # shape, same failure mode (a slow key-pool rotation holding a request
        # open). A dedicated setting would be a second knob meaning the same
        # thing.
        async with asyncio.timeout(settings.ai_report_deadline_s):
            return await generate_structured(
                client,
                response_model=response_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                report_type=report_type,
                lang=lang,
            )
    except Exception:
        # Provider down, keys exhausted, schema validation failed, deadline
        # fired — the caller's answer is the same in every case: fall back.
        log.warning("learn_ai_generation_failed", report_type=report_type, exc_info=True)
        return None
    finally:
        await aclose_report_client(client)


def _selected_label(selected_option: str) -> str:
    """An empty selection means the quiz timer expired before the learner
    answered. Say that plainly — a blank here would read as a missing field and
    invite the model to invent what they picked."""
    return selected_option.strip() or "(no answer — the learner ran out of time)"


async def explain_quiz_answer(
    *,
    lesson_id: str,
    question: str,
    selected_option: str,
    correct_option: str,
    lang: str = "en",
) -> Optional[QuizExplanation]:
    """Explain why the correct answer is correct, grounded in the lesson.

    Returns None when nothing could be retrieved or generation failed; the
    client then shows the quiz's bundled static explanation.
    """
    # The question plus the right answer is the best available query: it names
    # the concept under test in the learner's own lesson wording.
    rows = await retrieval.search(
        f"{question} {correct_option}",
        mode=retrieval.MODE_LESSON,
        lesson_id=lesson_id,
        limit=_RETRIEVE_LIMIT,
    )
    if not rows:
        log.info("learn_ai_ungrounded", report_type="learn_quiz_explanation")
        return None

    system = _RULES.format(lang=lang) + "\n" + load_prompt("learnhub_quiz").format(
        data_open=DATA_BLOCK_OPEN,
        content_block=_content_block(rows),
        data_close=DATA_BLOCK_CLOSE,
        quiz_open=QUIZ_BLOCK_OPEN,
        question=question,
        selected=_selected_label(selected_option),
        correct=correct_option,
        quiz_close=QUIZ_BLOCK_CLOSE,
    )
    result = await _generate(
        response_model=QuizExplanation,
        system=system,
        user="Write the explanation as structured output now.",
        report_type="learn_quiz_explanation",
        lang=lang,
    )
    if result is None:
        return None

    result.sources = _sources_for_display(_claimed_to_ids(result.sources, rows), rows)
    return result


async def summarize(
    *,
    lesson_id: str,
    section_id: Optional[str] = None,
    lang: str = "en",
) -> Optional[LessonSummary]:
    """Summarize a lesson (or one section of it), grounded in its content.

    Returns None when nothing could be retrieved or generation failed; the
    client then shows the lesson's bundled static summary.
    """
    rows = await retrieval.search(
        _slug_words(section_id or lesson_id),
        mode=retrieval.MODE_LESSON,
        lesson_id=lesson_id,
        limit=_RETRIEVE_LIMIT,
    )
    # A section summary must ground on THAT section, not the whole lesson —
    # otherwise the model blends neighbouring sections and the "section"
    # framing is aspirational. Filter post-retrieval (retrieval has no section
    # mode); fall back to the lesson rows if ranking missed the section
    # entirely, which beats returning None for a section that exists.
    scope = "the lesson"
    if section_id:
        section_rows = [r for r in rows if r.get("section_id") == section_id]
        if section_rows:
            rows = section_rows
            heading = (section_rows[0].get("heading") or "").strip()
            scope = f"the section \"{heading or _slug_words(section_id)}\""
    if not rows:
        log.info("learn_ai_ungrounded", report_type="learn_summary")
        return None
    system = _RULES.format(lang=lang) + "\n" + load_prompt("learnhub_summary").format(
        scope=scope,
        data_open=DATA_BLOCK_OPEN,
        content_block=_content_block(rows),
        data_close=DATA_BLOCK_CLOSE,
    )
    result = await _generate(
        response_model=LessonSummary,
        system=system,
        user="Write the summary as structured output now.",
        report_type="learn_summary",
        lang=lang,
    )
    if result is None:
        return None

    result.sources = _sources_for_display(_claimed_to_ids(result.sources, rows), rows)
    return result
