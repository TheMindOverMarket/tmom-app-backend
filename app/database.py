from sqlmodel import create_engine, Session, SQLModel
from app.config import settings

# SQLite for local development, Postgres (Supabase/Neon) for production
sqlite_url = settings.database_url
connect_args = {"check_same_thread": False} if "sqlite" in sqlite_url else {}

engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
