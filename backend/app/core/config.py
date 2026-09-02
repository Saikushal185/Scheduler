"""Centralised application configuration.

Every tunable knob of the system lives here (or in the database tables that are
seeded from here).  Nothing that a deployment may want to change should be
hardcoded deeper in the codebase.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ app
    APP_NAME: str = "AcademiSync - Automated Interview Scheduling & Evaluation System"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # ------------------------------------------------------------- database
    # Postgres is the production target (see docker-compose.yml).  A SQLite URL
    # is accepted so the stack can be run/tested without a database server.
    DATABASE_URL: str = "sqlite:///./academisync.db"
    SQL_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ------------------------------------------------------------- security
    SECRET_KEY: str = "change-me-in-production-please-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://[::1]:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ]
    )

    # bootstrap administrator (created on first start / seed)
    FIRST_ADMIN_EMAIL: str = "admin@example.com"
    FIRST_ADMIN_PASSWORD: str = "admin123"
    FIRST_ADMIN_NAME: str = "System Administrator"

    # --------------------------------------------------------------- upload
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = Field(
        default_factory=lambda: [".xlsx", ".xls", ".csv"]
    )

    # ----------------------------------------------------------- scheduling
    DEFAULT_INTERVIEW_DURATION_MIN: int = 30
    DEFAULT_BREAK_DURATION_MIN: int = 10
    DEFAULT_DAY_START: str = "09:00"
    DEFAULT_DAY_END: str = "17:00"
    DEFAULT_MIN_PANEL_SIZE: int = 2
    DEFAULT_MAX_PANEL_SIZE: int = 4
    DEFAULT_SLOT_GRANULARITY_MIN: int = 15
    DEFAULT_MAX_INTERVIEWS_PER_FACULTY_PER_DAY: int = 12
    DEFAULT_ALGORITHM: str = "backtracking"

    # Weight applied to every soft-constraint priority band.  The scheduler
    # scores candidate x panel x slot combinations with these multipliers.
    PRIORITY_WEIGHTS: dict[str, float] = Field(
        default_factory=lambda: {
            "HARD": 1000.0,
            "HIGH": 100.0,
            "MEDIUM": 50.0,
            "LOW": 20.0,
            "FLEXIBLE": 5.0,
        }
    )

    # ----------------------------------------------------------- evaluation
    # The seven metrics are seeded into `evaluation_metrics` and are fully
    # editable at runtime.  Names are NEVER referenced literally in the code.
    DEFAULT_EVALUATION_METRICS: List[dict[str, Any]] = Field(
        default_factory=lambda: [
            {"key": "metric_1", "name": "Technical Knowledge", "weight": 0.25, "max_score": 10, "display_order": 1},
            {"key": "metric_2", "name": "Problem Solving", "weight": 0.20, "max_score": 10, "display_order": 2},
            {"key": "metric_3", "name": "Communication", "weight": 0.15, "max_score": 10, "display_order": 3},
            {"key": "metric_4", "name": "Domain Expertise", "weight": 0.15, "max_score": 10, "display_order": 4},
            {"key": "metric_5", "name": "Research Aptitude", "weight": 0.10, "max_score": 10, "display_order": 5},
            {"key": "metric_6", "name": "Teamwork", "weight": 0.10, "max_score": 10, "display_order": 6},
            {"key": "metric_7", "name": "Overall Attitude", "weight": 0.05, "max_score": 10, "display_order": 7},
        ]
    )
    EVALUATION_NORMALISED_SCALE: float = 100.0

    @field_validator("CORS_ORIGINS", "ALLOWED_UPLOAD_EXTENSIONS", mode="before")
    @classmethod
    def _split_csv(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return v
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
