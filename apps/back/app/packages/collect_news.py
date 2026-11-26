import cloudscraper
import requests
from datetime import datetime, timezone, timedelta
import trafilatura
import pandas as pd
from psycopg import Cursor
from psycopg.rows import dict_row
from typing import Literal, Optional, TypeAlias
from logging import Logger
from pydantic import validate_call
import time

from ..db.update_record import update_articles_record
from ..llm.embedding import embedding_articles
from ..packages import get_logger
from ..domain.entities import ArticleModel
from ..db.connect_db import connect_to_postgres
from ..db.insert_record import insert_articles_record

brave_search_country_type: TypeAlias = Literal['AR','AU','AT', 'BE','BR','CA','CL', 'DK', 'FI', 'FR', 'DE', 'GR', 'HK', 'IN', 'ID', 'IT', 'JP', 'KR', 'MY', 'MX', 'NL', 'NZ', 'NO', 'CN', 'PL', 'PT', 'PH', 'RU', 'SA', 'ZA', 'ES', 'SE', 'CH', 'TW', 'TR', 'GB', 'US', 'ALL']
brave_search_language_type: TypeAlias = Literal['ar','eu', 'bn', 'bg', 'ca', 'zh-hans', 'zh-hant', 'hr', 'cs', 'da', 'nl', 'en', 'en-gb', 'et', 'fi', 'fr', 'gl', 'de', 'el', 'gu', 'he', 'hi', 'hu', 'is', 'it', 'ja', 'jp', 'kn', 'ko', 'lv', 'lt', 'ms', 'ml', 'mr', 'nb', 'pl', 'pt-br', 'pt-pt', 'pa', 'ro', 'ru', 'sr', 'sk', 'sl', 'es', 'sv', 'ta', 'te', 'th', 'tr', 'uk', 'vi']



def convert_relative_date(delta_t: str, logger: Optional[Logger] =None):
    # Convert relative dates to absolute dates in the news list
    current_date = datetime.now(timezone.utc)
    published_at = None
    
    if delta_t.endswith('ago'):
        if 'second' in delta_t:
            seconds = int(delta_t.split()[0])
            published_at = (current_date - timedelta(seconds=seconds))
        elif 'minute' in delta_t:
            minutes = int(delta_t.split()[0])
            published_at = (current_date - timedelta(minutes=minutes))
        elif 'hour' in delta_t:
            hours = int(delta_t.split()[0])
            published_at = (current_date - timedelta(hours=hours))
        elif 'day' in delta_t:
            days = int(delta_t.split()[0])
            published_at = (current_date - timedelta(days=days))
        elif 'week' in delta_t:
            weeks = int(delta_t.split()[0])
            published_at = (current_date - timedelta(weeks=weeks))
        elif 'month' in delta_t:
            months = int(delta_t.split()[0])
            published_at = (current_date - timedelta(days=30*months))
        elif 'year' in delta_t:
            years = int(delta_t.split()[0])
            published_at = (current_date - timedelta(days=365*years))
        else:
            if logger:
                logger.warning(f"Invalid delta_t '{delta_t}' provided. Defaulting to null.")
    else:
        if logger:
            logger.warning(f"Invalid delta_t '{delta_t}' provided. Defaulting to null.")
        
    return published_at


def brave_search_result_interpretation(response: dict, logger: Optional[Logger] = None) -> list[ArticleModel]:
    articles = []
    results = response.get("results", [])
    article_type = response.get("type", None)
    if not results:
        if logger:
            logger.warning(f"No results found in the Brave Search response: {response}")
    
        return articles
    
    for result in results:
        published_at = convert_relative_date(result.get("age"), logger) if result.get("age") is not None else None
        
        snippets = [result.get("description", "")]
        snippets.extend(result.get("extra_snippets", []))
        snippet = "\n".join(snippets)

        meta_url = result.get("meta_url", {})
        source = meta_url.get("hostname", None)

        articles.append(ArticleModel(
            title=result.get("title"),
            link=result.get("url"),
            snippet= snippet,
            published_at= published_at,
            source=source,
            article_language=result.get("language"),
            article_type=article_type
        ))    
    return articles


def brave_search_article(
    brave_search_api_key: str,
    query: str,
    time_range: Literal["pd", "pw", "pm", "py"] = "pd", # pd = past day, pw = past week, pm = past month, py = past year
    language: brave_search_language_type = "en",
    logger: Optional[Logger] = None,
    try_time: int = 0,
    error_msg: str = "",
    search_limit: Optional[int] = None
):
    time.sleep(try_time * 2)  # Exponential backoff: wait longer with each retry
    try_time += 1
    if try_time > 5:
        if logger:
            logger.error(f"Failed to search articles for query '{query}' after 5 attempts. Last error: {error_msg}")
        return [] , error_msg
    
    search_params = {"q": query, "safesearch": "strict"}
    if time_range:
        search_params['freshness'] = time_range
    if language:
        search_params['search_lang'] = language
    if search_limit:
        search_params['count'] = search_limit
    

    # get news
    response = requests.get(
        "https://api.search.brave.com/res/v1/news/search",
        headers={
            "X-Subscription-Token": brave_search_api_key,
            "accept": "application/json"
            },
        params = search_params
    )

    if response.status_code != 200:
        error_message = f"Search request failed, status code : {response.status_code}, message: {response.text}, query: {query}, time_range: {time_range}, language: {language}"
        if logger:
            logger.error(error_message)
        return brave_search_article(
            brave_search_api_key=brave_search_api_key,
            query=query,
            time_range=time_range,
            language=language,
            logger=logger,
            try_time=try_time,
            error_msg=error_message,
            search_limit=search_limit
        )  # Retry the search with incremented try_time and error message
    
    articles = brave_search_result_interpretation(response.json(), logger)
    
    return articles , error_msg



def brave_search_articles(
    brave_search_api_key: str,
    queries: list[str],
    time_range: Literal["pd", "pw", "pm", "py"] = "pd", # pd = past day, pw = past week, pm = past month, py = past year
    language: brave_search_language_type = "en",
    logger: Optional[Logger] = None,
    search_limit: Optional[int] = None):
    
    article_list = []
    for query in queries:
        articles, _ = brave_search_article(
            brave_search_api_key=brave_search_api_key,
            query = query,
            time_range=time_range, 
            language=language, 
            logger=logger,
            search_limit=search_limit
        )
        article_list.extend(articles)
    
    return article_list

def remove_duplicates_missing(article_list: list[ArticleModel]):
    seen_links = set()
    new_article_list = []
    
    # check duplicates and missing url 
    for i, article in enumerate(article_list):
        link = article.link
        if not link or link in seen_links:
            continue  # Skip articles with missing or duplicate links

        seen_links.add(article.link)
        new_article_list.append(article)    
    
    return new_article_list

def fetch_article_content(
    url: str,
    scraper : cloudscraper.CloudScraper,
    logger: Optional[Logger] = None,
    try_time = 0,
    error_msg=""):
    
    time.sleep(try_time * 2)  # Exponential backoff: wait longer with each retry
    try_time += 1
    success = False
    if try_time > 5:
        if logger:
            logger.error(f"Failed to fetch article content from {url} after 5 attempts. Last error: {error_msg}")
        return error_msg, success
    
    try:
        response = scraper.get(url, timeout=15)
        response.raise_for_status()
        
        text = trafilatura.extract(response.text, include_comments=False, include_tables=False)
        
        # check if the content is empty try to fetch again
        if not text or len(text.strip()) == 0:
            return fetch_article_content(url, scraper, logger, try_time, error_msg="failed: Empty content fetched")
        
        success = True
        return text, success
    except (requests.RequestException, ConnectionError, TimeoutError, OSError) as e:
        # HTTP errors, refused connections, timeouts, and DNS failures are common when scraping.
        return fetch_article_content(url, scraper, logger, try_time, error_msg=f"failed: Error fetching article content from {url}: {e}")
    except Exception as e:
        return fetch_article_content(url, scraper, logger, try_time, error_msg=f"failed: Error extracting article content from {url}: {e}")




def collect_article_pipeline(
    search_api:str,
    search_api_key: str,
    query_list,
    time_range: Literal["pd", "pw", "pm", "py"] = "pd",
    language='en',
    logger: Optional[Logger]=None,
    search_limit=None):
    if logger is None:
        logger = get_logger(__name__)
    logger.info(f"Starting article collection pipeline with search_api: {search_api}, time_range: {time_range}, language: {language}, search_limit: {search_limit}")
    
    # search for articles based on the query list, time range, language, and region
    if search_api == "brave":
        article_list = brave_search_articles(
            brave_search_api_key= search_api_key,
            queries=query_list,
            time_range=time_range,
            language=language,
            logger=logger,
            search_limit=search_limit
        )
    else:
        raise ValueError(f"Unsupported search API: {search_api}")
    
    # remove duplicates based on url
    article_list = remove_duplicates_missing(article_list)

    logger.info(f"Collected {len(article_list)} unique articles after removing duplicates and missing URLs.")
    
    # fetch the full article content for each news item
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )    
    
    article_dicts = {}
    to_embedding_articles = []
    
    logger.info(f"Starting to fetch content for {len(article_list)} articles.")
    with connect_to_postgres() as conn:
        for article in article_list:                
            returned_article, inserted = insert_articles_record(conn, article, logger)                
            if returned_article is None:
                raise Exception(f"Failed to insert or retrieve article record for {article.link}")
            
            article.id = returned_article.id  # Update the article model with the ID from the database
            
            if (inserted 
                or returned_article.content is None 
                or returned_article.content_status != "completed"
                or (
                    returned_article.published_at and article.published_at 
                    and returned_article.published_at < article.published_at
                    )
                ):
                
                content, success = fetch_article_content(article.link, scraper, logger)
                if success:
                    if returned_article.content is None or returned_article.content != content:
                        article.content = content
                        article.content_status = "completed"
                        article.content_error = None
                        article.embedded = False  # Reset embedding to False to indicate that it needs to be re-embedded
                else:
                    article.content = returned_article.content  # Keep the existing content if fetching failed (None or outdated content)
                    article.content_status = "failed"
                    article.content_error = content
                    article.embedded = returned_article.embedded  # Keep the existing embedding status
            
            # if article is discarded, skip embedding and updating
            if returned_article.discarded:
                continue
            
            # save to article_dicts for later use
            article_dicts[article.id] = article
            
            # check if the article needs to be embedded
            if article.content and article.embedded is False:
                to_embedding_articles.append(article.id)
        
        # embed the articles that need embedding
        article_dicts = embedding_articles(article_dicts, to_embedding_articles)
        
        # update the articles in the database with the new content and embedding status
        for article_id in to_embedding_articles:
            article = article_dicts[article_id]
            _ = update_articles_record(conn, article, logger)

    logger.info(f"Completed article collection pipeline with {len(article_dicts)} articles.")
    return article_dicts
                
                    
                