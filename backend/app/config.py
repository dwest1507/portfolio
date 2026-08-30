import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.environ["GROQ_API_KEY"]
GROQ_MODEL: str = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
ALLOWED_ORIGINS: list[str] = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

INDEXES_DIR = Path(__file__).parent.parent / "indexes"
