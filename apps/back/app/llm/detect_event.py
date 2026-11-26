from datetime import datetime, date
import json
import openai
import sqlite3
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
import os
from logging import Logger
from uuid import UUID
import re
from transformers import AutoTokenizer
from psycopg.rows import dict_row

from ..db.update_record import update_event_summary
from ..packages.raw_message_json import raw_message_json
from ..db.connect_db import connect_to_postgres
from ..db.insert_record import insert_events_record, insert_event_article_relationships
from ..pydantic_model import ArticleModel, EventModel, KeywordModel, EventSummaryResult
from ..packages.logger import get_logger
from ..llm.prompts import get_prompt
from ..llm.embedding import embedding_event
from ..llm.outputs import EventGroupingResult, FirstPassEventResolutionResult


def json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()   # aware
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")



def group_articles_by_event(
    to_process_article_ids: set[UUID],
    articles_dict: dict,
    model_name,
    model_source,
    api_key,
    logger=None) -> tuple[dict, dict]:
    
    system_prompt = get_prompt("article_event_grouping_agent", version="latest")

    article_list = []
    for id in to_process_article_ids:
        article = articles_dict.get(id)
        if not article:
            if logger:
                logger.error(f"Article with ID {id} not found in articles_dict.")
            continue
        
        article_list.append({
            "article_ref": article.ref_id,
            "title": article.title,
            "source_name": article.source,
            "published_at": article.published_at
        })
        
    if logger:
        logger.info(f"Grouping {len(article_list)} articles into events using model {model_name} from source {model_source}.")
    
    if model_source == "ollama":
        # The model was stopping near 4096 tokens and returning truncated JSON.
        llm_client = ChatOllama(
            model=model_name,
            api_key=api_key,
            num_ctx=16384,
            num_predict=8192,
        )
    else:
        logger.error(f"Unsupported model source: {model_source}")

    llm_client = llm_client.with_structured_output(EventGroupingResult, include_raw=True)
    messages=[
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(article_list, default=json_default))
    ]

    max_retries = 5
    try_times = 0
    
    while try_times < max_retries:
        try:
            response = llm_client.invoke(messages)
            
            raw_ai_message = raw_message_json(response["raw"])
            parsed = response["parsed"]
            parsing_error = response["parsing_error"]
            
            
            if logger:
                logger.debug(f"Raw AI message: {raw_ai_message}")
                logger.debug(f"Parsed AI message: {parsed.model_dump() if parsed else None}")
                logger.debug(f"Parsing error: {parsing_error}")
            
            if parsing_error or not parsed:
                # If parsing fails, try to parse the raw AI message manually using Pydantic
                validated = EventGroupingResult.model_validate_json(raw_ai_message)
            else:
                validated = parsed
                
            return validated.model_dump()
        
        except Exception as e:
            try_times += 1
            if logger:
                logger.error(f"Error during event grouping: {e}, attempt {try_times} of {max_retries}")

            continue
    else:
            if logger:
                logger.error("Failed to get a valid response from the LLM after multiple attempts.")
            raise Exception("Failed to get a valid response from the LLM after multiple attempts.")

def event_resolution(
    grouped_article_ids: list[UUID],
    similar_article_event_ids: list[UUID],
    same_batch_event_ids: list[UUID],
    articles_dict: dict[UUID, ArticleModel],
    events_dict: dict[UUID, EventModel],
    model_name: str,
    model_source: str,
    api_key: str,
    prompt_version: str = "latest",
    logger: Logger = None) -> dict:
    
    sys_prompt = get_prompt("event_resolution_agent", version=prompt_version)
    
    article_list = [{
        "article_ref": articles_dict[article_id].ref_id,
        "title": articles_dict[article_id].title,
        "source_name": articles_dict[article_id].source,
        "published_at": articles_dict[article_id].published_at
    } for article_id in grouped_article_ids]
    
    similar_article_event_list = [{
        "event_ref": events_dict[event_id].ref_id,
        "event_title": events_dict[event_id].title,
        "event_summary": events_dict[event_id].summary,
        "published_at_range": [events_dict[event_id].published_at_range_start, events_dict[event_id].published_at_range_end],
        "representative_article": [articles_dict[article_id].title for article_id in list(events_dict[event_id].article_ids)[:5] if article_id in articles_dict]
    } for event_id in similar_article_event_ids]
    
    same_batch_events = [{
        "event_ref": events_dict[event_id].ref_id,
        "event_title": events_dict[event_id].title,
        "event_summary": events_dict[event_id].summary,
        "published_at_range": [events_dict[event_id].published_at_range_start, events_dict[event_id].published_at_range_end],
        "representative_article": [articles_dict[article_id].title for article_id in list(events_dict[event_id].article_ids)[:5] if article_id in articles_dict]
    } for event_id in same_batch_event_ids]
    
    content = {
        'articles': article_list,
        'similar_article_events': similar_article_event_list,
        'same_batch_events': same_batch_events
    }
    
    if model_source == "ollama":
        llm_client = ChatOllama(model=model_name, api_key=api_key)
    else:
        logger.error(f"Unsupported model source: {model_source}")
      
    llm_client = llm_client.with_structured_output(FirstPassEventResolutionResult, include_raw=True)
    messages=[
        SystemMessage(content=sys_prompt),
        HumanMessage(content=json.dumps(content, default=json_default))
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
                # If parsing fails, try to parse the raw AI message manually using Pydantic
                validated = FirstPassEventResolutionResult.model_validate_json(raw_ai_message)
            else:
                validated = parsed
            
            return validated.model_dump()
            
        except Exception as e:
            try_times += 1
            if logger:
                logger.error(f"Error during first pass event resolution: {e}, attempt {try_times} of {max_retries}")

            continue
    else:
        if logger:
            logger.error("Failed to get a valid response from the LLM after multiple attempts.")
        raise Exception("Failed to get a valid response from the LLM after multiple attempts.")



def get_model_context_window_size(model_name: str, model_source: str, logger: Logger = None) -> int:
    context_size = None
    if model_source == "ollama":
        # Define context window sizes for known Ollama models
        ollama_context_sizes = {
            "gemma4:e4b": 128*1000,
            "gemma3:4b": 128*1000,
        }
        context_size = ollama_context_sizes.get(model_name)
        
    if context_size is None:
        if logger:
            logger.warning(f"Unknown {model_source} model '{model_name}'. Defaulting context window size to 100K tokens.")
        context_size = 100*1000  # Default to 100K tokens for unknown models

    return context_size

def model_to_hfmodel(model_name: str, logger: Logger = None) -> str:
    # Mapping of model names to Hugging Face model identifiers
    model_mapping = {
        "gemma4:e4b": "google/gemma-4-E4B-it",
        "gemma3:4b": "google/gemma-3-4b-it",
        "maternion/minicpm5:2b": "maternion/minicpm5:2b"
    }
    hf_model = model_mapping.get(model_name)
    if hf_model is None:
        if logger:
            logger.error(f"Unknown model name '{model_name}'. Please provide a valid model name.")
        raise ValueError(f"Unknown model name '{model_name}'. Please provide a valid model name.")
    
    return hf_model


def get_article(article_ids:set[UUID], articles_dict: dict[UUID, ArticleModel], logger=None) :
    for article_id in article_ids:
        article = articles_dict.get(article_id)
        if not article:
            if logger:
                logger.error(f"Article with ID {article_id} not found in articles_dict.")
            continue
        
        yield article

def get_prefix(article:ArticleModel):
    prefix = f"article_title: {article.title}\narticle_source: {article.source}\narticle_published_at: {article.published_at.strftime('%Y-%m-%d %H:%M %z')}\narticle_content:\n"

    return prefix

def get_contents(
    article_ids:set[UUID],
    articles_dict: dict[UUID, ArticleModel],
    model_name: str,
    model_source: str,
    sys_prompt: str,
    max_output_tokens: int,
    logger=None
    ) -> list[list[str]]:
    CONTEXT_WINDOW_SIZE = get_model_context_window_size(model_name, model_source, logger)
    MAX_INPUT_TOKENS = CONTEXT_WINDOW_SIZE - max_output_tokens - 1000  # Reserve some buffer for system and human messages
    
    if model_source == "ollama":
        TOKENIZER = AutoTokenizer.from_pretrained(model_to_hfmodel(model_name, logger))
    else:
        if logger:
            logger.error(f"Unsupported model source: {model_source}")
        return None
    
    contents = []
    
    sys_prompt_token_length = len(TOKENIZER.encode(sys_prompt, add_special_tokens=True))
    
    token_length = sys_prompt_token_length
    content = []
    article_generator = get_article(article_ids, articles_dict, logger)
    truncated_info_token_length = len(TOKENIZER.encode("\ncontent_truncated: True\n", add_special_tokens=True))
    
    while True:
        article = next(article_generator, None)
        if not article:
            break #break the loop if there are no more articles
        
        prefix = get_prefix(article)
        prefix_token_length = len(TOKENIZER.encode(prefix, add_special_tokens=True))
        

        if article.content:
            article_content = article.content
            truncated = False
        else:
            article_content = article.snippet
            truncated = True
        
        if not article_content:
            if logger:
                logger.warning(f"Article {article.id} has no content or snippet. Skipping this article.")
            continue
        
        token_left = MAX_INPUT_TOKENS - token_length - prefix_token_length - truncated_info_token_length # calculate the remaining token space with last loop's token_length and the new prefix_token_length and truncated_info_token_length

        if token_left <= 100:
            contents.append(content)
            content = []
            token_length = sys_prompt_token_length
        
            # Refresh token_left after resetting content and token_length
            token_left = MAX_INPUT_TOKENS - token_length - prefix_token_length - truncated_info_token_length
        
        
            if token_left <= 100:
                if logger:
                    logger.warning(f"Not enough token space left for article {article.id} after adding prefix. Skipping this article.")
                # preventing the prefix of articles too large
                continue
        

        article_content_ids = TOKENIZER.encode(article_content, add_special_tokens=True)
        article_content_token_length = len(article_content_ids)
        
        if article_content_token_length + truncated_info_token_length > token_left:
            # chunk the article into parts
            start_idx = 0
            end_idx = start_idx + token_left
            chunk_idx = 0
            while start_idx < article_content_token_length:
                truncated = True
                truncated_article_content_ids = article_content_ids[start_idx:end_idx]
                truncated_article_content = TOKENIZER.decode(truncated_article_content_ids, skip_special_tokens=True)
                contents.append(content + [f"{prefix}{truncated_article_content}\ncontent_truncated: {truncated} (chunk_{chunk_idx})\n"])
                chunk_idx += 1
                content = [] #clear content for the next batch
                token_length = sys_prompt_token_length
                token_left = MAX_INPUT_TOKENS - token_length - prefix_token_length - truncated_info_token_length
                
                start_idx = end_idx
                end_idx = start_idx + token_left  # leave some buffer for safety
            
        else:
            # if the article content fits within the remaining token limit, add it to the content
            content.append(f"{prefix}{article_content}\ncontent_truncated: {truncated}\n")
            token_length += prefix_token_length + article_content_token_length + truncated_info_token_length
    
    if content:
        contents.append(content)

    return contents

def get_published_at_range(
    event: EventModel,
    articles: dict[UUID, ArticleModel],
    current_start=None, current_end=None
    ):
    for id in event.article_ids:
        article = articles.get(id)
        if article:
            published_at = article.published_at
            if published_at:
                if current_start is None or published_at < current_start:
                    current_start = published_at
                if current_end is None or published_at > current_end:
                    current_end = published_at
    return current_start, current_end

def event_summary(
    event_id: UUID|str,
    event_dict: dict[UUID|str, EventModel],
    articles_dict: dict[UUID, ArticleModel],
    model_name: str,
    model_source: str,
    api_key: str,
    prompt_version: str = "latest",
    max_output_tokens: int = 1000,
    logger: Logger = None
    ):
    sys_prompt = get_prompt("event_summary_agent", version=prompt_version)
    
    event = event_dict.get(event_id)
    
    if not event:
        if logger:
            logger.error(f"Event with ID {event_id} not found in event_dict.")
        return None
    
    new_article_ids = event.new_article_ids
    if not new_article_ids:
        if logger:
            logger.info(f"No new articles to summarize for event {event_id}.")
        return None
    
    contents = get_contents(
        article_ids=new_article_ids,
        articles_dict=articles_dict,
        model_name=model_name,
        model_source=model_source,
        sys_prompt=sys_prompt,
        max_output_tokens=max_output_tokens,
        logger=logger
    )
    
    if model_source == "ollama":
        llm_client = ChatOllama(model=model_name, api_key=api_key, max_output_tokens=max_output_tokens)
    else:
        if logger:
            logger.error(f"Unsupported model source: {model_source}")
        raise ValueError(f"Unsupported model source: {model_source}")
    llm_client = llm_client.with_structured_output(EventSummaryResult, include_raw=True)
    
    for content_batch in contents:
        messages=[
            SystemMessage(content=sys_prompt),
            HumanMessage(content="\n".join(content_batch))
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
                    # If parsing fails, try to parse the raw AI message manually using Pydantic
                    validated = EventSummaryResult.model_validate_json(raw_ai_message)
                else:
                    validated = parsed
                
                # Update the event summary and scores
                event.summary = validated.summary
                event.confidence_score = validated.confidence_score
                event.importance_score = validated.importance_score
                event.published_at_range_start, event.published_at_range_end = get_published_at_range(event, articles_dict, event.published_at_range_start, event.published_at_range_end)

                # Update article_ids with the new articles
                event.article_ids.update(new_article_ids)

                if logger:
                    logger.info(f"Updated event {event_id} summary and scores from LLM.")
                    logger.debug(f"Event {event_id} summary: {validated.summary} confidence score: {validated.confidence_score} importance score: {validated.importance_score}")
                
                break  # Exit the retry loop on success
            
            except Exception as e:
                try_times += 1
                if logger:
                    logger.error(f"Error during event summary generation: {e}, attempt {try_times} of {max_retries}")
                continue
        else:
            if logger:
                logger.error("Failed to get a valid response from the LLM after multiple attempts.")
            raise Exception("Failed to get a valid response from the LLM after multiple attempts.")
    
    
    # Embedding event title and summary for future vector search
    embedding_event(event)
    
    with (connect_to_postgres() as conn, conn.transaction()):
        cursor = conn.cursor(row_factory=dict_row )
        if not event.id :
            # if the event has no ID, it means it's a new event, insert it into the db
            insert_events_record(cursor, event, logger=logger)
    
        else:
            # if the event already exists, update it in the db
            update_event_summary(cursor, event, logger=logger)
            
        # save the event-article relationships into the database
        insert_event_article_relationships(cursor, event, logger=logger)
 

                
            
                