import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

# db
DB_DIR = Path(__file__).parent.parent / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)

# postgres
username = os.getenv("POSTGRES_USER", "postgres")
password = os.getenv("POSTGRES_PASSWORD", "postgres")
host = "localhost"
port = "5432"
db_name = "tellme_db"
PG_CONNECTION_STRING = f"postgresql://{username}:{password}@{host}:{port}/{db_name}"

# table names
TABLE_NAMES = {
    "users": "users",
    "articles": "articles",
    "events": "events",
    "keywords": "keywords",
    "user_keywords": "user_keywords",
    "user_article_interactions": "user_article_interactions",
    "user_event_interactions": "user_event_interactions",
    "event_article_relationships": "event_article_relationships",
    "events_keywords_relationships": "events_keywords_relationships"
}


# keywords
KEYWORDS_FILE_PATH = Path(__file__).parent.parent / "db" / "keywords.json"

# news
SEARCH_API = 'brave'    # Options: 'brave'

# llm
CHAT_AGENT_BASE_URL = "http://localhost:11434/v1/"
CHAT_AGENT_MODEL = "maternion/minicpm5:2b"

ARTICLE_EVENT_GROUPING_AGENT_SOURCE = "ollama"
ARTICLE_EVENT_GROUPING_AGENT_MODEL = "gemma4:e4b"


FIRST_PASS_EVENT_RESOLUTION_AGENT_SOURCE = "ollama"
FIRST_PASS_EVENT_RESOLUTION_AGENT_MODEL = "gemma4:e4b"

EVENT_DETECTOR_BASE_URL = "http://localhost:11434/v1/"
EVENT_DETECTOR_MODEL = "gemma4:e4b"


# api keys
if SEARCH_API == 'serper':
    SEARCH_API_KEY = os.getenv("SERPER_API_KEY", None)
elif SEARCH_API == 'brave':
    SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", None)


CHAT_AGENT_API_KEY = os.getenv("CHAT_AGENT_API_KEY", "null")
ARTICLE_SUMMARIZER_API_KEY = os.getenv("ARTICLE_SUMMARIZER_API_KEY", CHAT_AGENT_API_KEY)
NEWS_SUMMARY_AGENT_API_KEY = os.getenv("NEWS_SUMMARY_AGENT_API_KEY", CHAT_AGENT_API_KEY)
EVENT_DETECTOR_API_KEY = os.getenv("EVENT_DETECTOR_API_KEY", CHAT_AGENT_API_KEY)

ARTICLE_EVENT_GROUPING_AGENT_API_KEY = os.getenv("ARTICLE_EVENT_GROUPING_AGENT_API_KEY", CHAT_AGENT_API_KEY)
FIRST_PASS_EVENT_RESOLUTION_AGENT_API_KEY = os.getenv("FIRST_PASS_EVENT_RESOLUTION_AGENT_API_KEY", CHAT_AGENT_API_KEY)

HF_TOKEN = os.getenv("HF_TOKEN", None)

# context lengths
MAX_ARTICLE_TOKENS = 8000  # Maximum length of the article content to be summarized

# uncertain article reanalysis
UNCERTAIN_ARTICLE_REANALYSIS_CONTENT_TRUNCATE = 2000  # Maximum length of the article content to be reanalyzed

# embedding
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_BATCH_SIZE = 16
