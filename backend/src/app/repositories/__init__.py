"""Data-access layer.

Repositories own ALL database queries (raw SQL / SQLAlchemy Core) and return
plain Python data. Services call repositories for persistence and keep business
logic; routes stay thin. The database schema source of truth remains the SQL
migrations under backend/database/migrations/ — repositories match those
migrations, they do not define schema.
"""
