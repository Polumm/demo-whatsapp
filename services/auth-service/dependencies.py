from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

# Improve connection stability
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Ensure sessions are properly managed
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency for FastAPI routes to get a SQLAlchemy session.
    Ensures connections are opened/closed properly.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
