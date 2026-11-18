import pandas as pd
from typing import Optional, Literal
from logging import Logger
from tqdm import tqdm

from ..llm.detect_event import group_articles_by_event, first_pass_event_resolution
from ..db.retrieve import get_article_event, get_similar_articles
from ..db.connect_db import connect_to_postgres
from ..packages.collect_news import collect_article_pipeline
from ..packages.logger import get_logger


def articles_request_event_pipeline(
    search_api:str,
    search_api_key: str,
    query_list: list[str], 
    time_range: Literal["pd", "pw", "pm", "py"],
    language: str,
    article_event_grouping_model: str,
    article_event_grouping_model_source: str,
    article_event_grouping_model_api_key: str,
    first_pass_event_resolution_model: str,
    first_pass_event_resolution_model_source: str,
    first_pass_event_resolution_model_api_key: str,
    logger: Optional[Logger]=None):
    if logger is None:
        logger = get_logger(__name__)
    
    ARTICLES_DICT = {}
    EVENTS_DICT = {}
    print(f'pipeline started')
    
    
    retrieved_article_dict = collect_article_pipeline(
        search_api=search_api,
        search_api_key=search_api_key,
        query_list=query_list,
        time_range=time_range,
        language=language,
        logger=logger
    )
    
    
    ARTICLES_DICT.update(retrieved_article_dict)
    
    to_process_article_ids = set(retrieved_article_dict.keys())
    
    # generate ref_id_map for articles
    article_ref_id_map = {}
    for idx, article_id in enumerate(ARTICLES_DICT.keys(), start=1):
        ref = f"A_{idx}"
        article_ref_id_map[ref] = article_id
        ARTICLES_DICT[article_id].ref_id = ref

    same_batch_event_ids = set()
    
    logger.info(f"Collecting similar articles and related events from db.")
    with connect_to_postgres() as conn:
        cursor = conn.cursor()
        for article_id in to_process_article_ids:
            article = ARTICLES_DICT.get(article_id)
            if not article:
                logger.error(f"Article with ID {article_id} not found in ARTICLES_DICT.")
                continue
            # check if articles related with events
            existed_event_ids = get_article_event(cursor, article, EVENTS_DICT, logger=logger)
            
            same_batch_event_ids.update(existed_event_ids)

            # get event from similar articles
            similar_article_ids = get_similar_articles(cursor, article_id, ARTICLES_DICT, threshold=0.2, top_k=5, logger=logger)
            
            if similar_article_ids:
                for similar_article_id in similar_article_ids:
                    # check if similar articles related with events
                    get_article_event(
                        cursor,
                        ARTICLES_DICT.get(similar_article_id),
                        EVENTS_DICT,
                        logger=logger
                    )
    
    
    # generate ref and ref_id_map for events
    event_ref_id_map = {}
    for idx, event_id in enumerate(EVENTS_DICT.keys(), start=1):
        ref = f"E_{idx}"
        event_ref_id_map[ref] = event_id
        EVENTS_DICT[event_id].ref_id = ref
                 
    logger.info("Starting articles grouping...")
    # group retrived articles
    group_result = group_articles_by_event(
        to_process_article_ids,
        ARTICLES_DICT,
        article_event_grouping_model,
        article_event_grouping_model_source,
        article_event_grouping_model_api_key,
        logger=logger
    )
    
    event_groups = []
    for event_group in group_result['event_groups']:
        group_article_ids = []
        
        for ref in event_group['article_refs']:
            article_id = article_ref_id_map.get(ref)
            if article_id and not ARTICLES_DICT.get(article_id).event_ids:
                # add article_id to group_article_ids only if it has no existing event_ids
                group_article_ids.append(article_id)
                
        
        group_article_ids = [article_ref_id_map[ref] for ref in event_group['article_refs']]
        event_groups.append({
            "group_ref": event_group['group_ref'],
            "event_candidate_title": event_group['event_candidate_title'],
            "article_ids": group_article_ids,
            "grouping_evidence": event_group['grouping_evidence'],
            "confidence": event_group['confidence']
        })
    
    non_event_article_ids = set()
    if group_result.get('discarded_articles'):
        non_event_article_ids.update([article_ref_id_map[article['article_ref']] for article in group_result['discarded_articles']])
    
    uncertainty_article_ids = set()
    if group_result.get('uncertain_articles'):
        uncertainty_article_ids.update([article_ref_id_map[article['article_ref']] for article in group_result['uncertain_articles']])
                
    logger.info(f"Event grouping completed. {len(event_groups)} event groups, {len(non_event_article_ids)} non-event articles, {len(uncertainty_article_ids)} uncertain articles.")
    
    # first pass event resolution, resolve events from articles with 
    for event_group in tqdm(event_groups, desc="First Pass Event Resolution"):
        grouped_artilce_ids = event_group['article_ids']

        # get similar articles for the group articles
        similar_article_ids = set()
        for article_id in event_group['article_ids']:
            similar_article_ids.update(ARTICLES_DICT[article_id].simlilar_article_ids)
        
        # get event_ids from similar articles
        similar_event_ids = set()
        for similar_article_id in similar_article_ids:
            similar_article = ARTICLES_DICT.get(similar_article_id)
            if similar_article:
                similar_event_ids.update(similar_article.event_ids)
        
        # first pass event resolution
        first_pass_result = first_pass_event_resolution(
            grouped_article_ids=grouped_artilce_ids,
            similar_event_ids=similar_event_ids,
            same_batch_event_ids=same_batch_event_ids,
            articles_dict=ARTICLES_DICT,
            events_dict=EVENTS_DICT,
            model_name=first_pass_event_resolution_model,
            model_source=first_pass_event_resolution_model_source,
            api_key=first_pass_event_resolution_model_api_key,
            prompt_version="latest",
            logger=logger
        )
        

    logger.info("First pass event resolution completed.")
    
    return first_pass_result

