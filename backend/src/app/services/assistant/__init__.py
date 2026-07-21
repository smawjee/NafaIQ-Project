"""NafaIQ Assistant: the voice-and-text agent behind the "Ask NafaIQ AI" CTA.

Layering, and the one rule that shapes it:

    tools.py    the tool registry — what the model may call, and what each call
                still needs from the user
    context.py  the resolver bundle — the user's own goal/bill/portfolio names
                and the controlled vocabularies, injected into the prompt so
                slot-filling resolves in one turn instead of a round trip
    agent.py    the bounded tool loop
    execute.py  ActionDraft -> the existing domain services

The rule: **the model never executes a write.** Read tools run inside the loop
because they only return values the services already computed; write tools stop
at a draft the user sees and confirms, and execution happens in a separate
authenticated request. That boundary is why a misheard amount is a visible edit
rather than a wrong row in someone's ledger.

Entirely separate from services/ai/tutor.py and services/learnhub/*: different
provider routing, its own quota table, and a tool loop rather than plain chat.
The LearnHub tutor and its RAG stack are not modified by this feature.
"""
