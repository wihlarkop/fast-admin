"""
Configuration settings using Pydantic Settings for Fast-Admin.
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Database configuration - no defaults to force .env usage
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str

    @field_validator('DATABASE_HOST')
    @classmethod
    def validate_host(cls, v):
        if not v.strip():
            raise ValueError("DATABASE_HOST cannot be empty")
        return v

    @field_validator('DATABASE_USER')
    @classmethod
    def validate_user(cls, v):
        if not v.strip():
            raise ValueError("DATABASE_USER cannot be empty")
        return v

    @field_validator('DATABASE_PASSWORD')
    @classmethod
    def validate_password(cls, v):
        if not v.strip():
            raise ValueError("DATABASE_PASSWORD cannot be empty")
        return v

    @field_validator('DATABASE_NAME')
    @classmethod
    def validate_database_name(cls, v):
        if not v.strip():
            raise ValueError("DATABASE_NAME cannot be empty")
        return v

    def database_url(self) -> URL:
        """Construct PostgreSQL database URL using SQLAlchemy URL."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.DATABASE_USER,
            password=self.DATABASE_PASSWORD,
            host=self.DATABASE_HOST,
            port=self.DATABASE_PORT,
            database=self.DATABASE_NAME,
        )


def validate_env_file():
    """Validate that .env file exists with required variables."""
    env_file = Path(".env")
    if not env_file.exists():
        raise FileNotFoundError(
            ".env file not found. Please create a .env file with the following variables:\n"
            "DATABASE_HOST=localhost\n"
            "DATABASE_PORT=5432\n"
            "DATABASE_USER=your_username\n"
            "DATABASE_PASSWORD=your_password\n"
            "DATABASE_NAME=your_database"
        )

    required_vars = [
        "DATABASE_HOST",
        "DATABASE_PORT",
        "DATABASE_USER",
        "DATABASE_PASSWORD",
        "DATABASE_NAME"
    ]

    missing_vars = []
    with open(env_file) as f:
        content = f.read()
        for var in required_vars:
            if f"{var}=" not in content:
                missing_vars.append(var)

    if missing_vars:
        raise ValueError(
            f"Missing required environment variables in .env file: {', '.join(missing_vars)}\n"
            "Please add them to your .env file."
        )


# Validate environment setup
validate_env_file()

# Global settings instance
try:
    settings = Settings()
except Exception as e:
    raise RuntimeError(
        f"Failed to load settings: {e}\n"
        "Please check your .env file contains all required database variables."
    ) from e
