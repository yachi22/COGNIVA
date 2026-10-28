import json
import os
import re
from typing import List, Optional, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    Designed to be clear, modular, and production-ready.
    """
    PROJECT_NAME: str = "Cogniva"
    VERSION: str = "0.1.1"
    DESCRIPTION: str = "Cogniva | Multimodal Enterprise Knowledge Agent"
    API_V1_STR: str = "/api/v1"
    
    # Server settings (supports dynamic $PORT from cloud container hosts)
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # CORS settings (allowed origins for frontend access)
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Database Configuration (PostgreSQL + pgvector)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "cogniva"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    DATABASE_URL: Optional[str] = None

    # Authentication & JWT Configuration
    SECRET_KEY: str = "cogniva-super-secret-key-for-development-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Storage and Document Upload Configuration
    STORAGE_PROVIDER: str = "local"  # "local", "s3", or "r2"
    STORAGE_DIR: str = "storage"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "csv"]

    # S3 / Cloudflare R2 / MinIO Object Storage Configuration
    S3_BUCKET_NAME: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None  # e.g. "https://<accountid>.r2.cloudflarestorage.com"
    S3_REGION_NAME: str = "us-east-1"
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_SIGNED_URL_EXPIRATION_SECONDS: int = 900  # 15 minutes
    S3_PREFIX: str = "cogniva"


    # Document Chunking Configuration
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150
    MIN_CHUNK_SIZE: int = 50

    # Embedding Configuration
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_BATCH_SIZE: int = 64
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None

    # Semantic Retrieval Configuration
    DEFAULT_RETRIEVAL_TOP_K: int = 5
    MAX_RETRIEVAL_TOP_K: int = 20

    # LLM & RAG Generation Configuration
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 1000
    MAX_CONTEXT_CHARS: int = 8000
    RAG_MIN_SIMILARITY: Optional[float] = None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("[") and s.endswith("]"):
                try:
                    return json.loads(s)
                except Exception:
                    pass
            return [i.strip() for i in s.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        """
        Enforce critical security validations in production mode.
        """
        if self.ENVIRONMENT.lower() == "production":
            self.DEBUG = False
            if self.SECRET_KEY == "cogniva-super-secret-key-for-development-change-in-production":
                raise ValueError(
                    "CRITICAL SECURITY ERROR: The default development SECRET_KEY cannot be used in production. "
                    "Set a strong, random SECRET_KEY environment variable (e.g. openssl rand -hex 32)."
                )
        return self

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @staticmethod
    def _normalize_raw_database_url(url: str) -> str:
        """
        Cleans and sanitizes raw database URL string:
        - Strips whitespace and surrounding quotes
        - Safely percent-encodes unencoded special characters (e.g. '@' in passwords)
        """
        if not url:
            return url
        url = url.strip()
        if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
            url = url[1:-1].strip()

        if "://" in url:
            scheme, rest = url.split("://", 1)
            # If rest contains multiple '@', the password contains unencoded '@'
            if rest.count("@") > 1:
                import urllib.parse
                userinfo, hostpath = rest.rsplit("@", 1)
                if ":" in userinfo:
                    user, pwd = userinfo.split(":", 1)
                    if "%" not in pwd:
                        pwd = urllib.parse.quote(pwd, safe="")
                    url = f"{scheme}://{user}:{pwd}@{hostpath}"
        return url

    @property
    def async_database_url(self) -> str:
        """
        Returns asynchronous PostgreSQL database URL (postgresql+asyncpg://).
        Normalizes postgres://, quotes, unencoded passwords, and handles sslmode parameters for asyncpg.
        """
        if self.DATABASE_URL:
            url = self._normalize_raw_database_url(self.DATABASE_URL)
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            
            # Translate libpq sslmode parameter for asyncpg compatibility
            if "sslmode=" in url:
                url = (
                    url.replace("sslmode=require", "ssl=require")
                    .replace("sslmode=prefer", "ssl=prefer")
                    .replace("sslmode=disable", "ssl=disable")
                    .replace("sslmode=verify-ca", "ssl=verify-ca")
                    .replace("sslmode=verify-full", "ssl=verify-full")
                )
            if "ssl=true" in url:
                url = url.replace("ssl=true", "ssl=require")
            return url

        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        """
        Returns synchronous PostgreSQL database URL (postgresql+psycopg://) for Alembic & sync operations.
        Normalizes postgres://, postgresql+asyncpg://, and ssl query parameters for psycopg (libpq).
        """
        if self.DATABASE_URL:
            url = self._normalize_raw_database_url(self.DATABASE_URL)
            if url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)

            # Translate asyncpg ssl parameter to libpq sslmode parameter for psycopg compatibility
            if "ssl=" in url:
                url = (
                    url.replace("ssl=require", "sslmode=require")
                    .replace("ssl=prefer", "sslmode=prefer")
                    .replace("ssl=disable", "sslmode=disable")
                    .replace("ssl=true", "sslmode=require")
                )
            return url

        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
