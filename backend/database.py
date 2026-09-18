import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Local connection file is excluded from version control.
local_file = Path(__file__).with_name('.database-url')
SQLALCHEMY_DATABASE_URL = os.environ.get('DATABASE_URL') or (local_file.read_text().strip() if local_file.exists() else None)
if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError('Configura DATABASE_URL o backend/.database-url antes de iniciar.')
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, hide_parameters=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
