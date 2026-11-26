
ARTICLE_TABLE_FIELDS = [
    "id", "title", "link", "snippet", "published_at", 
    "source", "article_language", "article_type", "content", "content_status",
    "content_error", "embedding", "created_at", "last_updated", "discarded"
]

EVENT_TABLE_FIELDS = [
    "id", "title", "summary", "published_at_range_start",
    "published_at_range_end", "confidence_score", "importance_score",
    "embedding", "created_at", "last_updated"
]

KEYWORD_TABLE_FIELDS = [
    "id", "source_id", "label", "definition", "parent_id",
    "synonyms", "keyword_type", "embedding", "path",
    "created_at", "last_updated"
]

EVENT_KEYWORD_RELATION_TABLE_FIELDS = [
    "event_id", "keyword_id", "relevance_score", "reason", "created_at",
    "last_updated"
]