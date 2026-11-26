import pandas as pd
from typing import Optional, Literal
from logging import Logger, INFO, DEBUG
from tqdm import tqdm
from uuid import UUID
from psycopg.rows import dict_row

from ..domain import Article, Event, Keyword
from ..llm.detect_event import group_articles_by_event, event_resolution, event_summary
from ..db.retrieve import get_article_event, get_similar_articles
from ..db.connect_db import connect_to_postgres
from ..packages import collect_article_pipeline, get_logger
from ..llm.match_keyword import match_keywords_to_event


def articles_request_event_pipeline(
    search_api:str,
    search_api_key: str,
    query_list: list[str], 
    time_range: Literal["pd", "pw", "pm", "py"],
    language: str,
    article_event_grouping_model: str,
    article_event_grouping_model_source: str,
    article_event_grouping_model_api_key: str,
    event_resolution_model: str,
    event_resolution_model_source: str,
    event_resolution_model_api_key: str,
    event_summary_model: str,
    event_summary_model_source: str,
    event_summary_model_api_key: str,
    event_summary_max_output_tokens: int,
    event_keyword_matching_model: str,
    event_keyword_matching_model_source: str,
    event_keyword_matching_model_api_key: str,
    log_level: int = INFO,
    logger: Optional[Logger]=None,
    ) -> list[Event]:
    if logger is None:
        logger = get_logger(__name__, log_level=log_level)
    
    ARTICLES_DICT : dict[UUID, Article] = {}
    EVENTS_DICT : dict[UUID, Event] = {}
    KEYWORDS_DICT : dict[UUID, Keyword] = {}
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
        cursor = conn.cursor( row_factory=dict_row )
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
    
    discarded_article_ids = set()
    if group_result.get('non_event_articles'):
        for discarded_article in group_result['non_event_articles']:
            article_id = article_ref_id_map.get(discarded_article['article_ref'])
            if article_id:
                discarded_article_ids.add(article_id)
                ARTICLES_DICT[article_id].discarded = True
                ARTICLES_DICT[article_id].discarded_reason = discarded_article.get('reason', 'Unknown')


    event_groups = []
    for event_group in group_result['event_groups']:
        group_article_ids = []
        
        for ref in event_group['article_refs']:
            article_id = article_ref_id_map.get(ref)
            if article_id and not ARTICLES_DICT.get(article_id).event_ids and article_id not in discarded_article_ids:
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
    
    
    uncertainty_article_ids = set()
    if group_result.get('uncertain_articles'):
        uncertainty_article_ids.update([article_ref_id_map[article['article_ref']] for article in group_result['uncertain_articles']])
                
    logger.info(f"Event grouping completed. {len(event_groups)} event groups, {len(group_result.get('discarded_articles',[]))} non-event articles, {len(uncertainty_article_ids)} uncertain articles.")
    
    updated_event_ids = set()
    new_event_ids = set()
    
    # Event resolution, resolve events from articles with similar content and same batch articles
    logger.info("Starting event resolution...")
    for event_group in tqdm(event_groups, desc="Event Resolution"):
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
        
        # event resolution
        resolution_result = event_resolution(
            grouped_article_ids=grouped_artilce_ids,
            similar_article_event_ids=similar_event_ids,
            same_batch_event_ids=same_batch_event_ids,
            articles_dict=ARTICLES_DICT,
            events_dict=EVENTS_DICT,
            model_name=event_resolution_model,
            model_source=event_resolution_model_source,
            api_key=event_resolution_model_api_key,
            prompt_version="latest",
            logger=logger
        )
        
        # update events_dict with new article_ids from match_candidate
        if resolution_result["match_candidate"]:
            for match in resolution_result["match_candidate"]:
                event_ref = match["event_ref"]
                event_id = event_ref_id_map.get(event_ref)
                if event_id:
                    updated_event_ids.add(event_id)
                    EVENTS_DICT[event_id].new_article_ids.update([article_ref_id_map[ref] for ref in match["article_refs"]])
                    
        # update events_dict with new article_ids from create_new
        if resolution_result["create_new"]:
            for new_event in resolution_result["create_new"]:
                new_event_id = f"new_event_{len(new_event_ids) + 1}"
                new_event_ids.add(new_event_id)
                
                EVENTS_DICT[new_event_id] = Event(**{
                    "title": new_event["event_title"],
                    "article_ids": set([article_ref_id_map[ref] for ref in new_event["article_refs"]]),
                    "new_article_ids": set( [article_ref_id_map[ref] for ref in new_event["article_refs"]] ),
                    "ref_id": new_event["temporary_event_id"]
                })
                
                # add new_event_id to same_batch_event_ids to prevent creating same event for other groups in the same batch
                same_batch_event_ids.add(new_event_id)
        
        # update uncertainty_article_ids with new uncertain articles
        if resolution_result["uncertain_articles"]:
            uncertainty_article_ids.update([article_ref_id_map[article["article_ref"]] for article in resolution_result["uncertain_articles"]])
            
    # resolve uncertainty articles, if any
    # if uncertainty_article_ids:
    #     for article_id in uncertainty_article_ids:
    # TODO: implement uncertainty article resolution logic here
            
            
            
    # Event Summary Agent
    logger.info("Starting event summary...")
    for event_id in tqdm(updated_event_ids| new_event_ids, desc="Event Summary"):
        event_summary(
            event_id=event_id,
            event_dict=EVENTS_DICT,
            articles_dict=ARTICLES_DICT,
            model_name=event_summary_model,
            model_source=event_summary_model_source,
            api_key=event_summary_model_api_key,
            prompt_version="latest",
            max_output_tokens=event_summary_max_output_tokens,
            logger=logger
        )

    logger.info("Event summary completed.")
    
    # Match keywords to events
    logger.info("Starting keyword matching to events...")
    for event_id in tqdm(updated_event_ids| new_event_ids, desc="Keyword Matching"):
        match_keywords_to_event(
            event_id=event_id,
            event_dict=EVENTS_DICT,
            keywords_dict=KEYWORDS_DICT,
            model_name=event_keyword_matching_model,
            model_source=event_keyword_matching_model_source,
            api_key=event_keyword_matching_model_api_key,
            prompt_version="latest",
            logger=logger
        )
    logger.info("Keyword matching to events completed.")
    
    # Return event
    event_output : list[Event] = []
    for event_id in existed_event_ids | updated_event_ids| new_event_ids:
        event_output.append(EVENTS_DICT.get(event_id))
    
    logger.info(f"Pipeline completed. {len(event_output)} events generated.")
    
    return event_output
    
        

    

