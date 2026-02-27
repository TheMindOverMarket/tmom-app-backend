from sqlmodel import create_engine, Session, SQLModel
from app.config import settings

# Standardizing on Postgres (Supabase)
database_url = settings.database_url

engine = create_engine(database_url, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
