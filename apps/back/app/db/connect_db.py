import psycopg
from dotenv import load_dotenv

from ..core.config import PG_CONNECTION_STRING, TABLE_NAMES

def connect_to_postgres():
    try:
        conn = psycopg.connect(PG_CONNECTION_STRING)
        return conn
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None
    