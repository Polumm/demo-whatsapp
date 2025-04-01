from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import DATABASE_URL

# Create an async engine
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Use async sessionmaker
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

async def get_db():
    """
    Async dependency for FastAPI routes to get an Async SQLAlchemy session.
    """
    async with AsyncSessionLocal() as session:
        yield session
