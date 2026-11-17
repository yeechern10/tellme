import psycopg
from psycopg.rows import dict_row
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from uuid import UUID
from typing import Optional

from apps.back.app.db.table_schema import ARTICLE_TABLE_FIELDS

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
        return event
    except Exception as e:
        print(f"Error retrieving event with event_id {event_id}: {e}")
        return None

def get_article_event(cursor: psycopg.Cursor, article: ArticleModel):
    event_dict = {}
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
            if event:
                event.article_ids.add(article.id)  # Add the article ID to the event's article_ids set
                event_dict[event_id] = event
        
        return article, event_dict        
    except Exception as e:
        print(f"Error retrieving event for article {article.id}: {e}")
        return article, None
    
def get_similar_articles(cursor: psycopg.Cursor, article: ArticleModel, threshold: float = 0.2, top_k: int = 5) -> Optional[list[ArticleModel]]:
    returning_fields = ", ".join(ARTICLE_TABLE_FIELDS)
    try:
        cursor.execute(f"""
            WITH top_k AS (
                SELECT {returning_fields}, embedding <=> %s AS distance
                FROM {TABLE_NAMES['articles']}
                WHERE embedding IS NOT NULL
                AND id <> %s
                ORDER BY embedding <=> %s
                LIMIT %s
            )
            SELECT {returning_fields} FROM top_k
            WHERE distance < %s
        """, (article.embedding, article.id, top_k, threshold))
        results = cursor.fetchall()
        
        if not results:
            return None
        
        for row in results:
            row['embedded'] = True if row['embedding'] is not None else False
            
        return [ArticleModel(**row) for row in results]
        
        
    except Exception as e:
        print(f"Error finding similar article for article {article.id}: {e}")
        return None