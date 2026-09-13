# -*- coding: utf-8 -*-
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./app.db"
    secret_key: str = "not-real-key"
    session_max_age_days: int = 7
    environment: str = "development"
    base_dir: Path = Path(__file__).parent
    templates_dir: Path = base_dir / "templates"
    static_dir: Path = base_dir / "static"
    defaults_dir: Path = base_dir / "assets" / "defaults"
    org_templates_dir: Path = base_dir / "assets" / "org_templates"
    solutions_dir: Path = base_dir / "assets" / "solutions"
    admin_email: str = ""
    admin_password: str = ""
    admin_session_hours: int = 5

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def is_dev(self) -> bool:
        return self.environment == "development"

    @property
    def is_prod(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()