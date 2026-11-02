import json
from datetime import datetime
from psycopg import Cursor, Connection
from psycopg import errors
from psycopg.rows import dict_row
import re
import uuid
from typing import Literal, Optional
from pydantic import validate_call
from logging import Logger

from ..pydantic_model import KeywordModel, ArticleModel, EventModel
from .connect_db import connect_to_postgres
from ..configuration import TABLE_NAMES
from ..db.table_schema import ARTICLE_TABLE_FIELDS

def update_articles_record(conn: Connection, article: ArticleModel, logger: Optional[Logger]=None):
    returning_fields = ", ".join(ARTICLE_TABLE_FIELDS)
    
    try:
        with conn.transaction():
            cursor = conn.cursor(row_factory=dict_row)
            cursor.execute(
                f"""
                UPDATE {TABLE_NAMES['articles']} 
                SET 
                    title = %s,
                    link = %s,
                    snippet = %s,
                    published_at = %s,
                    source = %s,
                    article_language = %s,
                    article_type = %s,
                    content = %s,
                    content_status = %s,
                    content_error = %s,
                    embedding = %s,
                    last_updated = NOW(),
                    filtered = %s
                WHERE id = %s
                RETURNING {returning_fields}
                """,
                (
                    article.title,
                    article.link,
                    article.snippet,
                    article.published_at,
                    article.source,
                    article.article_language,
                    article.article_type,
                    article.content,
                    article.content_status,
                    article.content_error,
                    article.embedding,
                    article.filtered,
                    article.id
                )
            )
            return cursor.fetchone()
    except errors.IntegrityError as e:
        if logger:
            logger.error(f"Error occurred while updating articles record: {e}")
        return None
    except Exception as e:
        if logger:
            logger.error(f"Unexpected error occurred while updating articles record: {e}")
        return None