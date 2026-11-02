from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class KeywordModel(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore extra fields not defined in the model
    
    id: Optional[UUID] = Field(None, description="The UUID of the keyword")
    source_id: Optional[str] = Field(None, description="The source ID of the keyword")
    label: str = Field(..., description="The label of the keyword")
    definition: Optional[str] = Field(None, description="The definition of the keyword")
    synonyms: Optional[list[str]] = Field(None, description="The synonyms of the keyword")
    type: Literal["iptc_media_topic", "location", "custom"] | None = Field(None, description="The type of the keyword")
    embedding: Optional[list[float]] = Field(None, description="The embedding of the keyword")
    created_at: Optional[datetime] = Field(None, description="The creation timestamp of the keyword")
    last_updated: Optional[datetime] = Field(None, description="The last updated timestamp of the keyword")
    embedded: bool = Field(False, description="Whether the keyword has been embedded")
    parent: Optional[UUID] = Field(None, description="The parent UUID of the keyword")
    parent_source_id: Optional[str] = Field(None, description="The parent source ID of the keyword")
    children: list[UUID] | None = Field(None, description="The children UUIDs of the keyword")
    children_source_ids: list[str] | None = Field(None, description="The children source IDs of the keyword")
    
class ArticleModel(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore extra fields not defined in the model
    
    id: Optional[UUID] = Field(None, description="The UUID of the article")
    title: str = Field(..., description="The title of the article")
    link: str = Field(..., description="The link to the article")
    snippet: Optional[str] = Field(None, description="A snippet of the article")
    published_at: Optional[datetime] = Field(None, description="The publication timestamp of the article")
    source: Optional[str] = Field(None, description="The source of the article")
    article_language: Optional[str] = Field(None, description="The language of the article")
    article_type: Optional[str] = Field(None, description="The type of the article")
    content: Optional[str] = Field(None, description="The full content of the article")
    content_status: Literal["pending", "completed", "failed"] | None = Field(None, description="The status of the requesting article content")
    content_error: Optional[str] = Field(None, description="The error message if the content request failed")
    embedding: list[float] | None = Field(None, description="The embedding of the article")
    created_at: Optional[datetime] = Field(None, description="The creation timestamp of the article")
    last_updated: Optional[datetime] = Field(None, description="The last updated timestamp of the article")
    embedded: bool = Field(False, description="Whether the article has been embedded")
    event_ids: set[UUID] = Field(default_factory=set, description="The UUIDs of the events associated with the article")
    filtered: bool = Field(False, description="Whether the article has been filtered out during event detection")

class EventModel(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore extra fields not defined in the model
    
    id: Optional[UUID] = Field(None, description="The UUID of the event")
    title: str = Field(..., description="The title of the event")
    summary: Optional[str] = Field(None, description="The summary of the event")
    published_at_range_start: Optional[datetime] = Field(None, description="The time of the event first published")
    published_at_range_end: Optional[datetime] = Field(None, description="The time of the event last published")
    confidence_score: Optional[float] = Field(None, description="The confidence score of the event")
    importance_score: Optional[int] = Field(None, description="The importance score of the event")
    embedding: list[float] | None = Field(None, description="The embedding of the event")
    created_at: Optional[datetime] = Field(None, description="The creation timestamp of the event")
    last_updated: Optional[datetime] = Field(None, description="The last updated timestamp of the event")
    embedded: bool = Field(False, description="Whether the event has been embedded")
    article_ids: set[UUID] = Field(default_factory=set, description="The UUIDs of the articles associated with the event")