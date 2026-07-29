"""Pydantic request/response schemas (DTOs), grouped by domain.

Canonical home for API models. Route files import from here; they must not
define BaseModel classes themselves. `app.models` re-exports these names for
backwards compatibility.
"""
