import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi.templating import Jinja2Templates
from functools import lru_cache
from app.utils import (
    days_since,
    days_until,
    markdown_filter,
    highlight_filter,
    local_time_filter,
    time_ago_filter,
)


class Settings(BaseSettings):
    PROJECT_NAME: str
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///./tracker.db"

    APP_PORT: int
    APP_ENV: str

    # Path to templates directory
    TEMPLATE_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "templates"
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()


# Global Jinja2 Template Environment
# We configured it here so it can be imported anywhere
templates = Jinja2Templates(directory=settings.TEMPLATE_DIR)

# Register filters
templates.env.filters["days_until"] = days_until
templates.env.filters["days_since"] = days_since
templates.env.filters["markdown"] = markdown_filter
templates.env.filters["highlight"] = highlight_filter
templates.env.filters["local"] = local_time_filter
templates.env.filters["time_ago"] = time_ago_filter
