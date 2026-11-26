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
from ..db.table_schema import ARTICLE_TABLE_FIELDS, EVENT_TABLE_FIELDS

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
                    discarded = %s
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
                    article.discarded,
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
    
def update_event_summary(
    cursor: Cursor, 
    event: EventModel, 
    logger: Optional[Logger]=None
):
    returning_fields = ", ".join(EVENT_TABLE_FIELDS)
    
    try:
        cursor.execute(
            f"""
            UPDATE {TABLE_NAMES['events']} 
            SET 
                summary = %s,
                published_at_range_start = %s,
                published_at_range_end = %s,
                confidence_score = %s,
                importance_score = %s,
                embedding = %s,
                last_updated = NOW()
            WHERE id = %s
            RETURNING {returning_fields}
            """,
            (
                event.summary,
                event.published_at_range_start,
                event.published_at_range_end,
                event.confidence_score,
                event.importance_score,
                event.embedding,
                
                event.id
            )
        )
        return cursor.fetchone()
    except errors.IntegrityError as e:
        if logger:
            logger.error(f"Error occurred while updating event summary: {e}")
    except Exception as e:
        if logger:
            logger.error(f"Unexpected error occurred while updating event summary: {e}")
            
def update_event_keywords(
    cursor: Cursor,
    event_id: uuid.UUID,
    keyword_id: uuid.UUID,
    relevance_score: float,
    reason: Optional[str] = None,
    logger: Optional[Logger]=None
):
    try:
        cursor.execute(
            f"""
            UPDATE {TABLE_NAMES['event_keyword_relationships']} 
            SET 
                relevance_score = %s,
                reason = %s,
                last_updated = NOW()
            WHERE event_id = %s AND keyword_id = %s
            """,
            (
                relevance_score,
                reason,
                event_id,
                keyword_id
            )
        )
        if logger:
            logger.info(f"Updated relevance score for event {event_id} and keyword {keyword_id}.")
        
    except errors.IntegrityError as e:
        if logger:
            logger.error(f"Error occurred while updating event keywords: {e}")
    except Exception as e:
        if logger:
            logger.error(f"Unexpected error occurred while updating event keywords: {e}")