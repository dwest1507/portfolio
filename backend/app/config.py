import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

#: Production's own OpenAI key. CI evaluates with a separate key (OPENAI_CI_API_KEY) so
#: eval spend and visitor spend can be told apart (ADR-0008).
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]

#: The model ADR-0008's selection rule chose (#72), and the one the generation gate's
#: Floors were measured on. The gate always measures this default, never the override.
DEFAULT_OPENAI_MODEL = "gpt-6-luna"
OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)

#: Chat requests served per UTC day across all visitors, on top of the per-IP limit. A
#: paid model sits behind an anonymous endpoint; past the cap, visitors get a polite
#: "resting for today" reply instead of an answer. The OpenAI project's monthly budget
#: is the backstop (docs/deployment.md).
DAILY_REQUEST_CAP: int = int(os.environ.get("DAILY_REQUEST_CAP", "1000"))

#: Groq no longer serves visitors. These remain for the generation eval's Groq baseline
#: tool (eval/run_generation.py), which replays or recaptures the pre-migration model.
GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL: str = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

ALLOWED_ORIGINS: list[str] = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

INDEXES_DIR = Path(__file__).parent.parent / "indexes"
