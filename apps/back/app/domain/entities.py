from typing import Literal, Optional, List, Any, Annotated
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator, BeforeValidator
from pydantic.dataclasses import dataclass
from datetime import datetime
import json

# This function is used to parse the embedding field from a string to a list of floats. It is used in the Pydantic models to ensure that the embedding field is always a list of floats, even if it is stored as a string in the database.
def _parse_embedding(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return [float(x) for x in v.strip("{}[]").split(",") if x.strip()]
    return v

Embedding = Annotated[List[float], BeforeValidator(_parse_embedding)]  # Define a type alias for embedding with a validator


@dataclass(slots=True, config=ConfigDict(extra="ignore"))  # Ignore extra fields not defined in the model
class Keyword:
    id: Optional[UUID] = Field(None, description="The UUID of the keyword")
    source_id: Optional[str] = Field(None, description="The source ID of the keyword")
    label: Annotated[str, Field(description="The label of the keyword")]
    definition: Optional[str] = Field(None, description="The definition of the keyword")
    parent_id: Optional[UUID] = Field(None, description="The parent UUID of the keyword")
    synonyms: Optional[list[str]] = Field(None, description="The synonyms of the keyword")
    type: Literal["iptc_media_topic", "location", "custom"] | None = Field(None, description="The type of the keyword")
    embedding: Optional[Embedding] = Field(None, description="The embedding of the keyword")
    path: Optional[str] = Field(None, description="The hierarchical path of the keyword in ltree format")
    created_at: Optional[datetime] = Field(None, description="The creation timestamp of the keyword")
    last_updated: Optional[datetime] = Field(None, description="The last updated timestamp of the keyword")
    embedded: bool = Field(False, description="Whether the keyword has been embedded")
    parent_source_id: Optional[str] = Field(None, description="The parent source ID of the keyword")
    children: list[UUID] | None = Field(None, description="The children UUIDs of the keyword")
    children_source_ids: list[str] | None = Field(None, description="The children source IDs of the keyword")
    ref_id: Optional[str] = Field(None, description="The reference ID of the keyword, e.g. 'K_1', 'K_2'")
    path_str: Optional[str] = Field(None, description="The hierarchical path of the keyword in human-readable format, e.g. 'Parent > Child > Subchild'")
    
@dataclass(slots=True, config=ConfigDict(extra="ignore"))  # Ignore extra fields not defined in the model
class Article:    
    id: Optional[UUID] = Field(None, description="The UUID of the article")
    title: Annotated[str, Field(description="The title of the article")]
    link: Annotated[str, Field(description="The link to the article")]
    snippet: Optional[str] = Field(None, description="A snippet of the article")
    published_at: Optional[datetime] = Field(None, description="The publication timestamp of the article")
    source: Optional[str] = Field(None, description="The source of the article")
    article_language: Optional[str] = Field(None, description="The language of the article")
    article_type: Optional[str] = Field(None, description="The type of the article")
    content: Optional[str] = Field(None, description="The full content of the article")
    content_status: Literal["pending", "completed", "failed"] | None = Field(None, description="The status of the requesting article content")
    content_error: Optional[str] = Field(None, description="The error message if the content request failed")
    embedding: Optional[Embedding] = Field(None, description="The embedding of the article")
    created_at: Optional[datetime] = Field(None, description="The creation timestamp of the article")
    last_updated: Optional[datetime] = Field(None, description="The last updated timestamp of the article")
    embedded: bool = Field(False, description="Whether the article has been embedded")
    event_ids: set[UUID] = Field(default_factory=set, description="The UUIDs of the events associated with the article")
    discarded: bool = Field(False, description="Whether the article has been discarded during event detection")
    discarded_reason: Optional[str] = Field(None, description="The reason why the article was discarded during event detection")
    ref_id: Optional[str] = Field(None, description="The reference ID of the article, e.g. 'A_1', 'A_2'")
    similar_article_ids: set[UUID] = Field(default_factory=set, description="The UUIDs of the similar articles associated with the article")
    
@dataclass(slots=True, config=ConfigDict(extra="ignore"))  # Ignore extra fields not defined in the model
class Event:    
    id: Optional[UUID] = Field(None, description="The UUID of the event")
    title: Annotated[str, Field(description="The title of the event")]
    summary: Optional[str] = Field(None, description="The summary of the event")
    published_at_range_start: Optional[datetime] = Field(None, description="The time of the event first published")
    published_at_range_end: Optional[datetime] = Field(None, description="The time of the event last published")
    confidence_score: Optional[float] = Field(None, description="The confidence score of the event")
    importance_score: Optional[float] = Field(None, description="The importance score of the event")
    embedding: Optional[Embedding] = Field(None, description="The embedding of the event")
    created_at: Optional[datetime] = Field(None, description="The creation timestamp of the event")
    last_updated: Optional[datetime] = Field(None, description="The last updated timestamp of the event")
    embedded: bool = Field(False, description="Whether the event has been embedded")
    article_ids: set[UUID] = Field(default_factory=set, description="The UUIDs of the articles associated with the event")
    ref_id: Optional[str] = Field(None, description="The reference ID of the event, e.g. 'E_1', 'E_2'")
    new_article_ids: set[UUID] = Field(default_factory=set, description="The UUIDs of the new articles assigned to the event")
    keyword_id_relevance_score_dict: dict[UUID, float] = Field(default_factory=dict, description="The UUIDs of the keywords associated with the event and their relevance scores")
    