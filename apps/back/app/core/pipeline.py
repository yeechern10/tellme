import pandas as pd

from ..db.retrieve import get_article_event, get_similar_articles
from ..db.connect_db import connect_to_postgres
from ..packages.collect_news import collect_article_pipeline
from ..packages.logger import get_logger
from ..llm.summarize_article import summarize_articles
from ..llm.detect_event import event_detection_pipeline
from ..configuration import  ARTICLE_SUMMARIZER_BASE_URL

def articles_request_event_pipeline(query_list, time_range, serper_api_key, article_summarizer_api_key, keywords_list, language='en', region=None, logger=None):
    if logger is None:
        logger = get_logger(__name__)
    
    articles_dict = collect_article_pipeline(query_list, time_range, serper_api_key, language, region, logger)
    
    detected_events_dict = {}
    to_detect_event_articles_dict = {}
    similar_articles_dict = {}
    similar_article_events_dict = {}
    
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
                    similar_articles_dict[similar_article.id] = similar_article
                    # check if similar articles related with events
                    similar_articles_dict[similar_article.id], similar_event_dicts = get_article_event(cursor, similar_article)
                    similar_article_events_dict.update(similar_event_dicts)
                    
        
                    
                
            
            
    

    
    # # detect events from the news articles
    # event_list, filtered_articles, uncertain_articles = event_detection_pipeline(articles_dict, api_key=article_summarizer_api_key, logger=logger)

    
    return news_list

