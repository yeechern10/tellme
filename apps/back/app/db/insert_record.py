import sqlite3
import json
from datetime import datetime
from psycopg import Connection, Cursor
from psycopg import errors
from psycopg.rows import dict_row
import re
import uuid
from typing import Literal, Optional
from pydantic import validate_call
from logging import Logger

from ..pydantic_model import KeywordModel, ArticleModel, EventModel
from .connect_db import connect_to_postgres
from ..db.table_schema import ARTICLE_TABLE_FIELDS
from ..configuration import TABLE_NAMES

def get_conflict_condition(error_message: str):
    match = re.search(r'Key \((.*?)\)=\((.*?)\)', error_message)
    if match:
        conflict_fields = match.group(1).split(',')
        conflict_values = match.group(2).split(',')
        conditions = []
        for field, value in zip(conflict_fields, conflict_values):
            conditions.append(f"{field.strip()} = '{value.strip()}'")
        conflict_condition = " AND ".join(conditions)
        
        return conflict_condition
    return None


def insert_keywords_record(
    cursor: Cursor,
    keyword_label: str, 
    keyword_type: Literal["iptc_media_topic", "location", "custom"] | None = None,
    keyword_source_id: Optional[str] = None, 
    keyword_definition: Optional[str] = None, 
    keyword_synonyms: Optional[list] = None, 
    keyword_embedding: list[float] = None, 
    logger: Optional[Logger] = None
    ):
    returning_fields = ", ".join(["id", "source_id", "label", "definition", "synonyms", "type", "embedding", "created_at", "last_updated"])
    
    try:
        cursor.execute(f"""
            INSERT INTO {TABLE_NAMES['keywords']} 
            (source_id, label, definition, synonyms, keyword_type, embedding)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING {returning_fields}
        """, (
            keyword_source_id,
            keyword_label,
            keyword_definition,
            keyword_synonyms,
            keyword_type,
            keyword_embedding
        ))
        result = cursor.fetchone()
        if result:
            result['embedded'] = True if result.pop('embedding') is not None else False
            return KeywordModel(**result), True
        return None, False
    except errors.UniqueViolation as e:
        if logger:
            logger.error(f"Error inserting keyword {keyword_source_id} {keyword_label}: {e.diag.message_detail}")

        conflict_condition = get_conflict_condition(e.diag.message_detail)
        
        # retrieve the existing record
        if conflict_condition:                
            with connect_to_postgres() as new_conn:
                with new_conn:
                    new_cursor = new_conn.cursor(row_factory=dict_row)
                    new_cursor.execute(f"""
                        SELECT {returning_fields} FROM {TABLE_NAMES['keywords']} WHERE {conflict_condition}
                    """)
                    existing_record = new_cursor.fetchone()
                    existing_record['embedded'] = True if existing_record.pop('embedding') is not None else False
                    if logger:
                        logger.info(f"Existing record: {existing_record}")
                    
                    return KeywordModel(**existing_record), False
        return None, False
    except errors.IntegrityError as e:
        if logger:
            logger.error(f"Integrity error inserting keyword {keyword_source_id} {keyword_label}: {e.diag.message_detail}")
        return None, False
            


def insert_articles_record(
    conn: Connection,
    article: ArticleModel,
    logger: Optional[Logger] = None
    ):
    returning_fields = ", ".join(ARTICLE_TABLE_FIELDS)

    try:
        with conn.transaction():
            cursor = conn.cursor(row_factory=dict_row)
            cursor.execute(f"""
                INSERT INTO {TABLE_NAMES['articles']} 
                (title, link, snippet, published_at, source, article_language, 
                article_type, content, content_status, content_error
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING {returning_fields}
            """, (
                article.title,
                article.link,
                article.snippet,
                article.published_at,
                article.source,
                article.article_language,
                article.article_type,
                article.content,
                article.content_status,
                article.content_error
            ))
            returned_article = cursor.fetchone()
            if returned_article:
                returned_article['embedded'] = True if returned_article.pop('embedding') is not None else False
                return ArticleModel(**returned_article), True
            else:
                raise Exception(f"Failed to insert article {article.link}. No record returned.")    
    
    except errors.UniqueViolation as e:
        if logger:
            logger.info(f"Error inserting article {article.title}: {e.diag.message_detail}")

        conflict_condition = get_conflict_condition(e.diag.message_detail)
                
        # retrieve the existing record
        if conflict_condition:                
            with connect_to_postgres() as new_conn:
                with new_conn.transaction():
                    new_cursor = new_conn.cursor(row_factory=dict_row)
                    new_cursor.execute(f"""
                        SELECT {returning_fields}
                        FROM {TABLE_NAMES['articles']} 
                        WHERE {conflict_condition}
                    """)
                    existing_record = new_cursor.fetchone()
                    if logger:
                        logger.info(f"Existing record: {existing_record}")
                    if existing_record:
                        existing_record['embedded'] = True if existing_record.pop('embedding') is not None else False
                        return ArticleModel(**existing_record), False
        
        return None, False
    except errors.IntegrityError as e:
        if logger:
            logger.error(f"Integrity error inserting article {article.title}: {e.diag.message_detail}")
        return None, False
    except Exception as e:
        if logger:
            logger.error(f"{e}")
        return None, False

    # TODO: Consider to fix returning fields



def insert_events_record(
    cursor: Cursor, 
    event_title: str,
    event_summary: Optional[str] = None,
    event_published_at_range_start: Optional[datetime] = None,
    event_published_at_range_end: Optional[datetime] = None,
    event_confidence_score: Optional[float] = None,
    event_importance_score: Optional[int] = None,
    event_embedding: list[float] = None,
    logger: Optional[Logger]=None
    ):
    returning_fields = ", ".join([
        "id", "title", "summary", "published_at_range_start",
        "published_at_range_end", "confidence_score", "importance_score",
        "embedding", "created_at", "last_updated"
    ])
    try:
        cursor.execute(f"""
            INSERT INTO {TABLE_NAMES['events']} 
            (title, summary, published_at_range_start, 
            published_at_range_end, confidence_score,
            importance_score, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING {returning_fields}
        """, (
            event_title,
            event_summary,
            event_published_at_range_start,
            event_published_at_range_end,
            event_confidence_score,
            event_importance_score,
            event_embedding
        ))
        
        returned_event = cursor.fetchone()
        if returned_event:
            returned_event['embedded'] = True if returned_event.pop('embedding') is not None else False
            return EventModel(**returned_event), True        
        return None, False
    except errors.UniqueViolation as e:
        if logger:
            logger.error(f"Error inserting event {event_title}: {e.diag.message_detail}")
            
        conflict_condition = get_conflict_condition(e.diag.message_detail)
                        
        # retrieve the existing record
        if conflict_condition:  
            with connect_to_postgres() as new_conn:
                with new_conn:
                    new_cursor = new_conn.cursor(row_factory=dict_row)
                    new_cursor.execute(f"""
                        SELECT {returning_fields}
                        FROM {TABLE_NAMES['events']} 
                        WHERE {conflict_condition}
                    """)
                    existing_record = new_cursor.fetchone()
                    if logger:
                        logger.info(f"Existing record: {existing_record}")
                    if existing_record:
                        existing_record['embedded'] = True if existing_record.pop('embedding') is not None else False
                        return EventModel(**existing_record), False
                    
        return None, False
    except errors.IntegrityError as e:
        if logger:
            logger.error(f"Integrity error inserting event {event_title}: {e.diag.message_detail}")
        return None, False


def update_event_articles(event: dict, cursor: Cursor, logger: Optional[Logger]=None):
    try:
        cursor.execute(f"""
            UPDATE {TABLE_NAMES['events']}
            SET article_ids = %s, published_at_range_start = %s, published_at_range_end = %s, confidence_score = %s
            WHERE event_id = %s
        """, (
            json.dumps(event['article_ids']),
            event.get('published_at_range_start', None).totimestamp() if event.get('published_at_range_start', None) else None,
            event.get('published_at_range_end', None).totimestamp() if event.get('published_at_range_end', None) else None,
            event.get('confidence_score', None),
            event['event_id']
        ))
    except errors.UniqueViolation as e:
        if logger:
            logger.error(f"Error updating event {event['event_title']}: {e}")
        else:
            print(f"Error updating event {event['event_title']}: {e}")