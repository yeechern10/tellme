import pandas as pd
from typing import Optional, Literal
from logging import Logger

from ..llm.detect_event import group_articles_by_event, first_pass_event_resolution
from ..db.retrieve import get_article_event, get_similar_articles
from ..db.connect_db import connect_to_postgres
from ..packages.collect_news import collect_article_pipeline
from ..packages.logger import get_logger
from ..llm.summarize_article import summarize_articles
from ..llm.detect_event import event_detection_pipeline
from ..configuration import  ARTICLE_SUMMARIZER_BASE_URL

def articles_request_event_pipeline(
    search_api:str,
    search_api_key: str,
    query_list: list[str], 
    time_range: Literal["pd", "pw", "pm", "py"],
    language: str,
    article_event_grouping_model: str,
    article_event_grouping_model_source: str,
    article_event_grouping_model_api_key: str,
    logger: Optional[Logger]=None):
    if logger is None:
        logger = get_logger(__name__)
    
    articles_dict = collect_article_pipeline(
        search_api=search_api,
        search_api_key=search_api_key,
        query_list=query_list,
        time_range=time_range,
        language=language,
        logger=logger
    )
    
    detected_events_dict = {}
    to_detect_event_articles_dict = {}
    similar_articles_dict = {}
    events_dict = {}
    
    with connect_to_postgres() as conn:
        cursor = conn.cursor()
        for article_id, article in articles_dict.items():
            # check if articles related with events
            articles_dict[article_id], event_dicts = get_article_event(cursor, article)
            detected_events_dict.update(event_dicts)
            
            # only add articles without event_ids to the list for event detection
            if not article.event_ids:
                to_detect_event_articles_dict[article.id] = article
            
            # get event from similar articles
            similar_articles = get_similar_articles(cursor, article, threshold=0.2, top_k=5)
            
            if similar_articles:
                for similar_article in similar_articles:
                    article.simlilar_article_ids.add(similar_article.id)
                    # check if similar articles related with events
                    similar_articles_dict[similar_article.id], similar_event_dicts = get_article_event(cursor, similar_article)
                    events_dict.update(similar_event_dicts)
                
                    
    # group retrived articles
    group_result, ref_id_map = group_articles_by_event(
        articles_dict,
        article_event_grouping_model,
        article_event_grouping_model_source,
        article_event_grouping_model_api_key,
        logger=logger
    )
    
    # first pass event resolution, resolve events from articles with 
    for event_group in group_result['event_groups']:
        '''
        event_group = Dict({
            "group_id": "batch_event_001",
            "event_candidate_title": "A concise, neutral title supported by the grouped article titles",
            "article_refs": ["A_1", "A_2"],
            "grouping_evidence": "Briefly state the title details that support grouping these articles as the same specific event.",
            "confidence": 0.0
        })
        '''
        group_article_ids = [ref_id_map[ref] for ref in event_group['article_refs']]
        
        similar_article_ids = set()
        for article_id in group_article_ids:
            similar_article_ids.update(articles_dict[article_id].simlilar_article_ids)
        
        similar_event_ids = set()
        for similar_article_id in similar_article_ids:
            similar_article = similar_articles_dict.get(similar_article_id)
            if similar_article:
                similar_event_ids.update(similar_article.event_ids)
        
        
    
    
                    
        
                    
                
            
            
    

    
    # # detect events from the news articles
    # event_list, filtered_articles, uncertain_articles = event_detection_pipeline(articles_dict, api_key=article_summarizer_api_key, logger=logger)

    
    return news_list

