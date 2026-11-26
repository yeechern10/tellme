from logging import Logger
from langchain_ollama import ChatOllama
from langchain.messages import SystemMessage, HumanMessage
from psycopg.rows import dict_row
from uuid import UUID
import json

from ..db.connect_db import connect_to_postgres
from ..db.update_record import update_event_keywords
from ..db.insert_record import insert_event_keyword_relationship
from ..packages.logger import get_logger
from ..pydantic_model import EventKeywordMatchingResult, EventModel, KeywordModel
from ..db.retrieve import get_event_keywords, get_event_similar_keywords
from ..llm.prompts import get_prompt
from ..packages.raw_message_json import raw_message_json


def match_keywords_to_event (
    event_id: UUID,
    event_dict: dict[UUID, EventModel],
    keywords_dict: dict[UUID, KeywordModel],
    model_name: str,
    model_source: str,
    api_key: str,
    prompt_version: str,
    logger: Logger = None
):
    if logger is None:
        logger = get_logger(__name__)
    
    event = event_dict.get(event_id)
    if not event:
        logger.error(f"Event with ID {event_id} not found in event_dict.")
        return None
    
    with connect_to_postgres() as conn:
        cursor = conn.cursor(row_factory=dict_row)
        # get keywords related to the event
        related_keyword_ids = get_event_keywords(
            cursor=cursor,
            event=event,
            keywords_dict=keywords_dict,
            logger=logger
        )


        # get similar keywords via vector search
        similar_keyword_ids = get_event_similar_keywords(
            cursor=cursor,
            event=event,
            keywords_dict=keywords_dict,
            top_k=5,
            logger=logger
        )
    
    keyword_ids = set(related_keyword_ids or []) | set(similar_keyword_ids or [])
    
    # assign reference IDs to keywords and create a mapping from reference ID to keyword ID
    keyword_ref_id_map = {}
    for i , keyword_id in enumerate(keyword_ids):
        ref = f"K_{i+1}"
        keyword = keywords_dict.get(keyword_id)
        keyword.ref_id = ref  # Assign a reference ID to each keyword
        keyword_ref_id_map[ref] = keyword_id  # Map keyword ID to reference ID
    
    if logger:
        logger.debug(f"Event {event.id} has keyworeds {keyword_ref_id_map.keys()}.")

    sys_prompt = get_prompt("event_keyword_matching_agent", version=prompt_version)
    
    content = {
        "event":{
            "event_title": event.title,
            "event_summary": event.summary,
        },
        "candidate_keywords": []
    }
    
    for keyword_id in keyword_ids:
        keyword = keywords_dict.get(keyword_id)
        if keyword:
            content["candidate_keywords"].append({
                "keyword_ref": keyword.ref_id,
                "label": keyword.label,
                "definition": keyword.definition,
                "path": keyword.path_str,
            })

    if logger:
        logger.info(f"Matching keywords for event {event.id} with {len(keyword_ids)} candidate keywords.")
    if model_source == 'ollama':
        llm_client = ChatOllama(model=model_name, api_key=api_key)
    else:
        if logger:
            logger.error(f"Unsupported model source: {model_source}")
        raise ValueError(f"Unsupported model source: {model_source}")
    
    llm_client = llm_client.with_structured_output(EventKeywordMatchingResult, include_raw=True)
    
    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=json.dumps(content))
    ]
    
    max_retries = 5
    try_times = 0
    
    while try_times < max_retries:
        try:
            response = llm_client.invoke(messages)
            
            raw_ai_message = raw_message_json(response["raw"])
            parsed = response["parsed"]
            parsing_error = response["parsing_error"]
            
            if parsing_error or not parsed:
                if logger:
                    logger.warning(f"Auto parsing error for event {event.id}: {parsing_error}. Raw AI message: {raw_ai_message}. Trying manual parsing.")
                    parsed = EventKeywordMatchingResult.model_validate_json(raw_ai_message)
                
            break  # Exit the retry loop if parsing is successful
            
        except Exception as e:
            try_times += 1
            if logger:
                logger.error(f"Error during LLM generation for event {event.id}: {e}. Retry {try_times}/{max_retries}")
            continue
    
    else:
        if logger:
            logger.error("Failed to get a valid response from the LLM after multiple attempts.")
        raise Exception("Failed to get a valid response from the LLM after multiple attempts.")
    
    results = parsed.model_dump().get("keyword_matches", [])
    if not results:
        if logger:
            logger.warning(f"No keyword matches found for event {event.id}.")
        return None
    
    with (
        connect_to_postgres() as conn,
        conn.transaction()
    ):
        cursor = conn.cursor(row_factory=dict_row)
        for result in results:
            ref_id = result.get("keyword_ref")
            if not ref_id in keyword_ref_id_map:
                if logger:
                    logger.warning(f"Reference ID {ref_id} not found in mapping for event {event.id}.")
                    continue
            
            keyword_id = keyword_ref_id_map[ref_id]

            event.keyword_id_relevance_score_dict[keyword_id] = result.get("relevance_score", 0.0)
            
            if  keyword_id in related_keyword_ids:
                # Update the relevance score for keywords that are already related to the database
                update_event_keywords(
                    cursor=cursor,
                    event_id=event.id,
                    keyword_id=keyword_id,
                    relevance_score=result.get("relevance_score", 0.0),
                    reason=result.get("reason", None),
                    logger=logger
                )
            else:
                # Insert new keyword-event relationship for keywords that are not yet related to the database
                insert_event_keyword_relationship(
                    cursor=cursor,
                    event_id=event.id,
                    keyword_id=keyword_id,
                    relevance_score=result.get("relevance_score", 0.0),
                    reason=result.get("reason", None),
                    logger=logger
                )
                
            if logger:
                logger.warning(f"Reference ID {ref_id} not found in mapping for event {event.id}.")
    