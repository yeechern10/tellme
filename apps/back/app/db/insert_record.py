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
from ..db.table_schema import ARTICLE_TABLE_FIELDS, EVENT_TABLE_FIELDS, KEYWORD_TABLE_FIELDS
from ..core.config import TABLE_NAMES

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


def insert_keyword_record(
    cursor: Cursor,
    keyword_label: str, 
    keyword_type: Literal["iptc_media_topic", "location", "custom"] | None = None,
    keyword_source_id: Optional[str] = None, 
    keyword_definition: Optional[str] = None, 
    keyword_synonyms: Optional[list] = None, 
    keyword_parent_id: Optional[uuid.UUID] = None,
    keyword_embedding: list[float] = None, 
    logger: Optional[Logger] = None
    ) -> Optional[KeywordModel]:
    returning_fields = ", ".join(KEYWORD_TABLE_FIELDS)
    
    try:
        cursor.execute(f"""
            INSERT INTO {TABLE_NAMES['keywords']} 
            (source_id, label, definition, parent_id, synonyms, keyword_type, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING {returning_fields}
        """, (
            keyword_source_id,
            keyword_label,
            keyword_definition,
            keyword_parent_id,
            keyword_synonyms,
            keyword_type,
            keyword_embedding
        ))
        result = cursor.fetchone()
        if result:
            result['embedded'] = True if result.pop('embedding') is not None else False
            return KeywordModel(**result)
        return None
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
                        logger.debug(f"Existing record: {existing_record.get('label')} with ID {existing_record.get('id')}")
                    
                    return KeywordModel(**existing_record)
        return None
    except errors.IntegrityError as e:
        if logger:
            logger.error(f"Integrity error inserting keyword {keyword_source_id} {keyword_label}: {e.diag.message_detail}")
        return None
            
def insert_event_keyword_relationship(
    cursor: Cursor,
    event_id: uuid.UUID,
    keyword_id: uuid.UUID,
    relevance_score: float,
    reason: Optional[str] = None,
    logger: Optional[Logger] = None
) -> bool:
    try:
        cursor.execute(f"""
            INSERT INTO {TABLE_NAMES['event_keyword_relationships']} 
            (event_id, keyword_id, relevance_score, reason)
            VALUES (%s, %s, %s, %s)
        """, (
            event_id,
            keyword_id,
            relevance_score,
            reason
        ))
        if logger:
            logger.info(f"Inserted event-keyword relationship for event {event_id} and keyword {keyword_id}.")
        return True
    except errors.UniqueViolation as e:
        if logger:
            logger.error(f"Error inserting event-keyword relationship for event {event_id} and keyword {keyword_id}: {e.diag.message_detail}")
        return False
    except errors.IntegrityError as e:
        if logger:
            logger.error(f"Integrity error inserting event-keyword relationship for event {event_id} and keyword {keyword_id}: {e.diag.message_detail}")
        return False
    except Exception as e:
        if logger:
            logger.error(f"Unexpected error inserting event-keyword relationship for event {event_id} and keyword {keyword_id}: {e}")
        return False

def insert_event_article_relationships(
    cursor: Cursor,
    event: EventModel,
    logger: Optional[Logger] = None
) -> bool:
    event_article_pairs = []
    if not event.new_article_ids:
        if logger:
            logger.info(f"No new articles to insert for event {event.id}.")
        return True  # Nothing to insert, but not an error
    
    for article_id in event.new_article_ids:
        event_article_pairs.append((event.id, article_id))
    
    row_placeholder = "(%s, %s)"
    placeholders = ", ".join([row_placeholder] * len(event_article_pairs))

    # flatten the list of tuples for the execute method
    flat_params = [v for pair in event_article_pairs for v in pair]

    try:
        cursor.execute(f"""
            INSERT INTO {TABLE_NAMES['event_article_relationships']} 
            (event_id, article_id)
            VALUES {placeholders}
            ON CONFLICT (event_id, article_id) DO NOTHING
        """, flat_params)
        return True
    except errors.UniqueViolation as e:
        if logger:
            logger.error(f"Error inserting event-article relationships for event {event.id}: {e.diag.message_detail}")
        return False
    except errors.IntegrityError as e:
        if logger:
            logger.error(f"Integrity error inserting event-article relationships for event {event.id}: {e.diag.message_detail}")
        return False
    except Exception as e:
        if logger:
            logger.error(f"Unexpected error inserting event-article relationships for event {event.id}: {e}")
        return False

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
            logger.debug(f"Failed to insert article {article.title}: {e.diag.message_detail}")

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
                        logger.debug(f"Existing record: {existing_record.get('title')} with ID {existing_record.get('id')}")
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
    event: EventModel,
    logger: Optional[Logger]=None
    ):
    returning_fields = ", ".join(EVENT_TABLE_FIELDS)
    try:
        cursor.execute(f"""
            INSERT INTO {TABLE_NAMES['events']} 
            (title, summary, published_at_range_start, 
            published_at_range_end, confidence_score,
            importance_score, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING {returning_fields}
        """, (
            event.title,
            event.summary,
            event.published_at_range_start,
            event.published_at_range_end,
            event.confidence_score,
            event.importance_score,
            event.embedding
        ))
        
        returned_event = cursor.fetchone()
        if returned_event:
            event.id = returned_event['id']       
        
        return EventModel(**returned_event), True
    except errors.UniqueViolation as e:
        if logger:
            logger.debug(f"Failed to insert event {event.title}: {e.diag.message_detail}")
            
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
                        logger.debug(f"Existing record: {existing_record.get('title')} with ID {existing_record.get('id')}")
                    if existing_record:
                        existing_record['embedded'] = True if existing_record.get('embedding') is not None else False
                        return EventModel(**existing_record), False
                    
        return None, False
    except errors.IntegrityError as e:
        if logger:
            logger.error(f"Integrity error inserting event {event.title}: {e.diag.message_detail}")
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
            logger.debug(f"Failed to update event {event['event_title']}: {e}")
        else:
            print(f"Error updating event {event['event_title']}: {e}")