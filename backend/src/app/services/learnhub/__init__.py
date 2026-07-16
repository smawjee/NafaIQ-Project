"""LearnHub RAG — retrieval over lesson/glossary/quiz content.

Serves the non-chat LearnHub surfaces (search, related lessons, glossary
lookup, and later grounded quiz explanations/summaries). The AI tutor does NOT
consume anything in this package — see tests/test_tutor_isolation.py, which
fails the build if the tutor's source ever references it.
"""
