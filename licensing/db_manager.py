# -*- coding: utf-8 -*-
"""Company database manager for multi-tenant DynamicPro ERP."""
import logging
from datetime import datetime

from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker
from database import db
from licensing.models import LicCompany, LicDatabaseRegistry

log = logging.getLogger(__name__)

# HIGH #10: Use config module's credentials instead of hardcoded values
import config as _cfg
DB_USER = _cfg.DB_USER
DB_PASSWORD = _cfg.DB_PASSWORD
DB_HOST = _cfg.DB_HOST
DB_PORT = _cfg.DB_PORT

SCHEMA_DIR = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))), "migrations")

# HIGH #11: Cache engines to prevent pool leaks
_ENGINE_CACHE = {}


def generate_db_name(company_id: int, company_name: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in company_name.lower().strip())
    safe = "_".join(filter(None, safe.split("_")))[:30]
    return f"company_{company_id}_{safe}"


def create_company_db(company: LicCompany) -> bool:
    db_name = company.db_name
    try:
        conn_str = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
        engine = create_engine(conn_str, isolation_level="AUTOCOMMIT")

        with engine.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                log.info("Created database: %s", db_name)

        schema_file = __import__("os").path.join(SCHEMA_DIR, "company_schema.sql")
        if __import__("os").path.exists(schema_file):
            company_db_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{db_name}"
            company_engine = create_engine(company_db_url)
            with open(schema_file, "r", encoding="utf-8") as f:
                sql = f.read()
            with company_engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            log.info("Applied schema to: %s", db_name)

        registry = LicDatabaseRegistry(
            company_id=company.id, db_name=db_name, db_host=DB_HOST,
            db_port=int(DB_PORT), db_user=DB_USER, schema_version="1.0.0",
            last_migration=datetime.utcnow(), status="active",
        )
        db.session.add(registry)
        db.session.commit()
        return True

    except Exception as e:
        log.error("Failed to create DB for company %d: %s", company.id, e)
        db.session.rollback()
        return False


def get_company_engine(company: LicCompany):
    """Get or create a cached SQLAlchemy engine for a company."""
    cache_key = f"{company.db_host}:{company.db_port}:{company.db_name}"
    if cache_key not in _ENGINE_CACHE:
        url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{company.db_host}:{company.db_port}/{company.db_name}"
        _ENGINE_CACHE[cache_key] = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
    return _ENGINE_CACHE[cache_key]


def get_company_session(company: LicCompany):
    engine = get_company_engine(company)
    Session = sessionmaker(bind=engine)
    return Session()


def test_company_db(company: LicCompany) -> bool:
    try:
        engine = get_company_engine(company)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        log.error("DB connection test failed for company %d: %s", company.id, e)
        return False


def get_db_size(company: LicCompany) -> float:
    try:
        engine = get_company_engine(company)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT pg_database_size(current_database()) / 1024.0 / 1024.0 AS size_mb"))
            row = result.fetchone()
            return float(row[0]) if row else 0.0
    except Exception:
        return 0.0


def archive_company_db(company: LicCompany) -> bool:
    try:
        old_name = company.db_name
        new_name = f"archived_{old_name}_{datetime.utcnow().strftime('%Y%m%d')}"
        conn_str = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
        engine = create_engine(conn_str, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            conn.execute(text(f'ALTER DATABASE "{old_name}" RENAME TO "{new_name}"'))
        registry = LicDatabaseRegistry.query.filter_by(company_id=company.id).first()
        if registry:
            registry.db_name = new_name
            registry.status = "archived"
            db.session.commit()
        # Remove from cache
        cache_key = f"{company.db_host}:{company.db_port}:{old_name}"
        _ENGINE_CACHE.pop(cache_key, None)
        log.info("Archived DB: %s -> %s", old_name, new_name)
        return True
    except Exception as e:
        log.error("Failed to archive DB for company %d: %s", company.id, e)
        return False
