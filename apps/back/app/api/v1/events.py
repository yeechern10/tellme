from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...core.config import Settings
from ...schemas import EventRequest, KeywordShow, ArticleShow, EventResponse
from ..deps import get_settings
from ...core.pipeline import article_event_pipeline
from ...packages import get_logger

router = APIRouter()

class TaskCreated(BaseModel):
    task_id: str
    status: str = "pending"

@router.post("/events:build")
async def build_events(
    payload: EventRequest,
    settings: Settings = Depends(get_settings),
):
    logger = get_logger("build_events", log_level=settings.LOG_LEVEL)
    logger.info("Building events...")
    
    events = article_event_pipeline(
    search_api=settings.SEARCH_API,
    search_api_key=settings.search_api_key.get_secret_value(),
    query_list=payload.query_list,
    time_range=payload.time_range,
    language=payload.language,
    article_event_grouping_model=settings.ARTICLE_EVENT_GROUPING_AGENT_MODEL,
    article_event_grouping_model_source=settings.ARTICLE_EVENT_GROUPING_AGENT_SOURCE,
    article_event_grouping_model_api_key=settings.article_event_grouping_api_key.get_secret_value(),
    event_resolution_model=settings.EVENT_RESOLUTION_AGENT_MODEL,
    event_resolution_model_source=settings.EVENT_RESOLUTION_AGENT_SOURCE,
    event_resolution_model_api_key=settings.event_resolution_api_key.get_secret_value(),
    event_summary_model=settings.EVENT_SUMMARY_AGENT_MODEL,
    event_summary_model_source=settings.EVENT_SUMMARY_AGENT_SOURCE,
    event_summary_model_api_key=settings.event_summary_api_key.get_secret_value(),
    event_summary_max_output_tokens=settings.EVENT_SUMMARY_MAX_OUTPUT_TOKENS,
    event_keyword_matching_model=settings.EVENT_KEYWORD_MATCHING_MODEL,
    event_keyword_matching_model_source=settings.EVENT_KEYWORD_MATCHING_MODEL_SOURCE,
    event_keyword_matching_model_api_key=settings.event_keyword_matching_api_key.get_secret_value(),
    log_level=settings.LOG_LEVEL,
    logger=logger
    )
    
    response = []
    for event in events:
        keywords = sorted(event.keywords.values(), key=lambda k: k[1]) # Sort keywords by importance score
        keywords_show = []
        for keyword in keywords:
            keywords_show.append(KeywordShow(
                label=keyword[0].label,
                path=[path.strip() for path in keyword[0].path_str.split(">")]
            ))
        
        response.append({
            "event_id": str(event.event_id),
            "title": event.title,
            "summary": event.summary,
            "published_at_range": event.published_at_range,
            "importance_score": event.importance_score,
            "keywords": keywords_show,
            "articles": [
                ArticleShow(
                    title=article.title,
                    link=article.link,
                    snippet=article.snippet,
                    published_at=article.published_at,
                    source=article.source
                ) for article in event.articles
            ]
        })
        
    logger.info(f"Built {len(response)} events.")
    
    return EventResponse(events=response)
    