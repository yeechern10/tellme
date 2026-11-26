import json
from pathlib import Path
from psycopg.rows import dict_row

from ..packages.logger import get_logger
from ..llm.embedding import embedding_keywords
from ..db.connect_db import connect_to_postgres
from ..db.insert_record import insert_keyword_record
from ..pydantic_model import KeywordModel

def init_keywords_table():
    with connect_to_postgres() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id UUID PRIMARY KEY DEFAULT uuidv7(),
                source_id TEXT UNIQUE,
                label TEXT NOT NULL,
                definition TEXT,
                parent_id UUID REFERENCES keywords(id) ON DELETE SET NULL,
                synonyms TEXT[],
                keyword_type TEXT,
                embedding vector(1024),
                path ltree NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                last_updated TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        conn.commit()


def insert_initial_keywords(logger=None):
    topics_file_path = Path(__file__).parent / "iptc_media_topics_with_synonyms.json"
    
    keywords: dict[str,dict] = json.load(open(topics_file_path, "r", encoding="utf-8"))
    keywords = embedding_keywords(keywords)
    pending = {source_id for source_id, kw in keywords.items() if not kw.get("id")}
    with connect_to_postgres() as conn:
        cursor = conn.cursor(row_factory=dict_row)
        if logger:
            logger.info(f"Starting to insert {len(pending)} keywords into the database.")
        while pending:
            done = set()
            for source_id in pending:
                parent_source_id = keywords[source_id].get('parent')
                if parent_source_id is None or keywords[parent_source_id].get('id'):
                    returned_keyword = insert_keyword_record(
                        cursor=cursor,
                        keyword_label=keywords[source_id]['label'],
                        keyword_type="iptc_media_topic",
                        keyword_source_id=source_id,
                        keyword_definition=keywords[source_id]['definition'],
                        keyword_synonyms=keywords[source_id]['synonyms'],
                        keyword_parent_id=keywords[parent_source_id].get('id') if parent_source_id else None,
                        keyword_embedding=keywords[source_id]['embedding'],
                        logger=logger
                    )
                    keywords[source_id]['id'] = returned_keyword.id
                    if logger:
                        logger.info(f"Inserted keyword {source_id} with ID {returned_keyword.id}")
                    
                    done.add(source_id)
            
            if not done:
                if logger:
                    logger.error("No keywords were inserted in this iteration. There might be a circular dependency or missing parent keywords.")
                break
            
            # Remove the processed keywords from the pending list for next loop
            pending -= done

            if logger:
                logger.info(f"Inserted {len(done)} keywords in this iteration. {len(pending)} keywords remaining.")
        
        conn.commit()

def main():
    # changed to use .sql file for schema creation
    # init_keywords_table()
    logger = get_logger("init_keywords_table")
    
    insert_initial_keywords(logger=logger)
    
if __name__ == "__main__":
    main()
                