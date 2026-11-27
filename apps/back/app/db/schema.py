TABLE_NAMES = {
    "users": "users",
    "articles": "articles",
    "events": "events",
    "keywords": "keywords",
    "user_keywords": "user_keywords",
    "user_article_interactions": "user_article_interactions",
    "user_event_interactions": "user_event_interactions",
    "event_article_relationships": "event_article_relationships",
    "event_keyword_relationships": "event_keyword_relationships",
}

TABLE_FIELDS = {
    "articles": [
    "id", "title", "link", "snippet", "published_at", 
    "source", "article_language", "article_type", "content", "content_status",
    "content_error", "embedding", "created_at", "last_updated", "discarded"
],
    "events": [
    "id", "title", "summary", "published_at_range_start",
    "published_at_range_end", "confidence_score", "importance_score",
    "embedding", "created_at", "last_updated"
],
    "keywords": [
    "id", "source_id", "label", "definition", "parent_id",
    "synonyms", "keyword_type", "embedding", "path",
    "created_at", "last_updated"
],
    "event_keyword_relationships": [
    "event_id", "keyword_id", "relevance_score", "reason", "created_at",
    "last_updated"
]
}