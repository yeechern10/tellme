import psycopg
from dotenv import load_dotenv

from ..core.config import settings

def connect_to_postgres():
    try:
        conn = psycopg.connect(settings.pg_connection_string)
        return conn
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None
    