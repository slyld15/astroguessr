import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL=os.getenv("DATABASE_URL", "sqlite:///default.db")
DEBUG=os.getenv("DEBUG_MODE", "True").lower() in ("true", "1", "yes")

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
Base = declarative_base()

print(f"Database URL: {DATABASE_URL}")