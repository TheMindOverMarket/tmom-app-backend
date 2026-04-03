from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlmodel import create_engine, Session, SQLModel
from app.config import settings

# Standardizing on Postgres (Supabase)
database_url = settings.database_url

engine = create_engine(database_url, echo=True)


def run_db_migrations() -> None:
    """
    Best-effort startup schema alignment.
    We intentionally migrate before serving traffic so deployed code
    does not run against an older database shape.
    """
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    repo_root = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(repo_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(repo_root / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
