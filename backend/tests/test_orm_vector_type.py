"""Reflection must survive pgvector's `vector` columns.

orm.reflect_metadata walks every public table, so it meets
learnhub_knowledge_chunks.embedding — declared vector(768). Without a
registered type SQLAlchemy warns on every boot; with a WRONG one it raises and
reflection dies at startup (an early version of the shim took no args and blew
up with TypeError on the dimension). These pin both failure modes.
"""
from __future__ import annotations

from sqlalchemy.dialects.postgresql.base import ischema_names

from app.db.orm import _PgVector


def test_vector_is_registered_for_reflection():
    """Unregistered => 'Did not recognize type vector' on every startup."""
    assert ischema_names.get("vector") is _PgVector


def test_type_accepts_the_dimension_reflection_passes_it():
    """Reflection instantiates the type as _PgVector(768) from vector(768) —
    a shim that takes no args raises TypeError and kills reflection."""
    assert _PgVector(768).get_col_spec() == "vector(768)"


def test_type_without_a_dimension_is_still_valid():
    assert _PgVector().get_col_spec() == "vector"
