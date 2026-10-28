from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Numeric
from sqlalchemy.dialects.postgresql import JSONB

# JSONB no PostgreSQL; JSON genérico em SQLite (testes)
JsonDoc = JSON().with_variant(JSONB(), "postgresql")
Kg = Numeric(14, 3, asdecimal=False)
Mm = Numeric(10, 2, asdecimal=False)
DataHora = DateTime(timezone=True)
Densidade = Numeric(5, 3, asdecimal=False)


def agora() -> datetime:
    return datetime.now(timezone.utc)
