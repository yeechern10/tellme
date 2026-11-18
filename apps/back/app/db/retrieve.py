import psycopg
from psycopg.rows import dict_row
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from uuid import UUID
from typing import Optional
from logging import Logger

from ..db.table_schema import ARTICLE_TABLE_FIELDS
from ..pydantic_model import ArticleModel, EventModel, KeywordModel

from ..db.connect_db import connect_to_postgres
from ..configuration import TABLE_NAMES


def retrieve_leaves_keywords_from_db():
    with connect_to_postgres() as conn:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute(f"SELECT * FROM {TABLE_NAMES['keywords']} WHERE child_ids IS NULL")
        keywords = cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        keyword_dict = {}
        for row in keywords:
            keyword_dict[row['id']] = KeywordModel(**row)
    return keyword_dict

def get_event_with_event_id(cursor: psycopg.Cursor, event_id: str):
    try:
        cursor.execute(f"""SELECT * 
                       FROM {TABLE_NAMES['events']} 
                       WHERE id = %s""", (event_id,)
                       )
        event = cursor.fetchone()
        event['embedded'] = True if event['embedding'] is not None else False
        event = EventModel(**event)
        
        cursor.execute(f"""SELECT article_id
                        FROM {TABLE_NAMES['event_article_relationships']}
                        WHERE event_id = %s""", (event_id,)
                       )
        event_article_ids = cursor.fetchall()
        event.article_ids = set([row['article_id'] for row in event_article_ids])
        
        return event
    except Exception as e:
        print(f"Error retrieving event with event_id {event_id}: {e}")
        return None

def get_article_event(
    cursor: psycopg.Cursor, 
    article: ArticleModel,
    events_dict: dict[UUID, EventModel],
    logger: Optional[Logger] = None
    ) -> Optional[set[UUID]]:
    try:
        cursor.execute(f"""SELECT event_id 
                       FROM {TABLE_NAMES['event_article_relationships']} 
                       WHERE article_id = %s""", (article.id,)
                       )
        result = cursor.fetchall()
        
        event_ids = set([row['event_id'] for row in result])
        article.event_ids = event_ids  # Update the article's event_ids attribute
        
        for event_id in event_ids:
            event = get_event_with_event_id(cursor, event_id)
            if not event:
                if logger:
                    logger.error(f"Event with ID {event_id} not found in the database.")
                continue

            if event.id not in events_dict:
                events_dict[event.id] = event
                
            events_dict[event.id].article_ids.update(event.article_ids) # Add the article IDs to the existing event's article_ids set
        
        return event_ids        
    except Exception as e:
        if logger:
            logger.error(f"Error retrieving events for article {article.id}: {e}")
        return None

def get_similar_articles(
    cursor: psycopg.Cursor,
    article_id: UUID, 
    articles_dict: dict[UUID, ArticleModel], 
    threshold: float = 0.2, 
    top_k: int = 5,
    logger: Optional[Logger] = None
) -> Optional[list[UUID]]:
    returning_fields_with_ref = ", ".join(["a."+field for field in ARTICLE_TABLE_FIELDS])
    returning_fields = ", ".join(ARTICLE_TABLE_FIELDS)
    
    article = articles_dict.get(article_id)
    if not article:
        if logger:
            logger.error(f"Article with ID {article_id} not found in articles_dict.")
        return None
    logger.info(f"Retrieving similar articles for article {article_id} with threshold {threshold} and top_k {top_k}.")
    
    try:
        cursor.execute(f"""
            WITH target AS (
                SELECT embedding
                FROM {TABLE_NAMES['articles']}
                WHERE id = %s
            ),
            top_k AS (
                SELECT {returning_fields_with_ref}, a.embedding <=> t.embedding AS distance
                FROM {TABLE_NAMES['articles']} a
                CROSS JOIN target t
                WHERE a.embedding IS NOT NULL
                AND a.id <> %s
                ORDER BY distance 
                LIMIT %s
            )
            SELECT {returning_fields} FROM top_k
            WHERE distance < %s
        """, (article.id, article.id, top_k, threshold))
        
        results = cursor.fetchall()
        
        if not results:
            return None
        
        for row in results:
            row['embedded'] = True if row['embedding'] is not None else False
     
        similar_article_ids = []
        for row in results:
            id = row['id']
            similar_article_ids.append(id)
            if id not in articles_dict:
                articles_dict[id] = ArticleModel(**row)
            else:
                articles_dict[id].simlilar_article_ids.add(article_id)  # Add the original article ID to the similar article's simlilar_article_ids set

        article.simlilar_article_ids.update(similar_article_ids)
                
        return similar_article_ids  # Return the list of similar article IDs
        
    except Exception as e:
        if logger:
            logger.error(f"Error retrieving similar articles for article {article_id}: {e}")
        return None