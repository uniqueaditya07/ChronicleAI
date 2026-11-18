import os
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base

# Default to a local SQLite database file in the project or backend directory
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chronicle.db")
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DB_PATH}"


def normalize_database_url(database_url: str) -> str:
    """Select the pinned PostgreSQL driver and require TLS by default."""
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://"):]

    url = make_url(database_url)
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername.startswith("postgresql+") and url.drivername != "postgresql+psycopg":
        raise ValueError("PostgreSQL DATABASE_URL must use the installed psycopg driver.")

    if url.drivername == "postgresql+psycopg":
        query = dict(url.query)
        sslmode = query.get("sslmode")
        if sslmode is None:
            query["sslmode"] = "require"
        elif sslmode not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("PostgreSQL DATABASE_URL must use sslmode=require, verify-ca, or verify-full.")
        query.setdefault("connect_timeout", "10")
        url = url.set(query=query)

    return url.render_as_string(hide_password=False)


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))

# SQLite requires check_same_thread=False for multi-threaded FastAPI access
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

if DATABASE_URL.startswith("postgresql+"):
    # Keep each Render process within a small Supabase connection budget.
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=300,
    )
else:
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
