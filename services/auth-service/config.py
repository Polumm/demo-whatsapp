import os
from dotenv import load_dotenv

APP_ENV = os.getenv("APP_ENV", "development")

if APP_ENV == "development":
    load_dotenv()

# Secret keys & security
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_SECRET_KEY = os.getenv("ACCESS_SECRET_KEY", "access_secret_key")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
)  # Convert to int

# Database Config
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://authuser:authpass@postgres-auth:5432/authdb"
)
