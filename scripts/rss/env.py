"""Load local environment variables from .env (optional)."""
from pathlib import Path

from .constants import REPO_ROOT


def load_dotenv() -> None:
    """Load repo-root `.env` if present. CI 可直接注入环境变量，无需此文件。"""
    try:
        from dotenv import load_dotenv as _load_dotenv
    except ImportError:
        return

    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        _load_dotenv(env_file)
