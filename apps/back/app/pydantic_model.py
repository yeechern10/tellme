from enum import Enum
from typing import Literal, Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, model_validator
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
    discarded: bool = Field(False, description="Whether the article has been discarded during event detection")
    discarded_reason: Optional[str] = Field(None, description="The reason why the article was discarded during event detection")
    ref_id: Optional[str] = Field(None, description="The reference ID of the article, e.g. 'A_1', 'A_2'")
    simlilar_article_ids: set[UUID] = Field(default_factory=set, description="The UUIDs of the similar articles associated with the article")

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
    ref_id: Optional[str] = Field(None, description="The reference ID of the event, e.g. 'E_1', 'E_2'")
    new_article_ids: set[UUID] = Field(default_factory=set, description="The UUIDs of the new articles assigned to the event")
    
    
### llm structured output models for event detection and grouping

## Article event grouping result models
class EventGroup(BaseModel):
    group_ref: str = Field(description="Unique temporary identifier for the event group, e.g. 'G_1', 'G_2', ...")
    event_candidate_title: str = Field(description="A concise, neutral title supported by the grouped article titles.")
    article_refs: List[str] = Field(description="References (e.g. 'A_1', 'A_2') of articles in this group.")
    grouping_evidence: str = Field(description="Briefly state the title details that support grouping these articles as the same specific event.")
    confidence: float = Field(ge=0.0,le=1.0,description="Confidence score between 0.0 and 1.0.")

class NonEventArticle(BaseModel):
    article_ref: str = Field(description="Reference of the article, e.g. 'A_3'.")
    reason: Literal[
        "opinion",
        "analysis_without_new_event",
        "evergreen",
        "service_or_how_to",
        "review_or_promotion",
        "no_identifiable_event",
    ] = Field(description="Category explaining why this article is not a reportable event.")

class UncertainArticle(BaseModel):
    article_ref: str = Field(description="Reference of the article, e.g. 'A_4'.")
    reason: str = Field(description="Briefly explain why the title alone is insufficient to identify or group the article.")

class EventGroupingResult(BaseModel):
    event_groups: List[EventGroup] = Field(
        default_factory=list,
        description="Groups of articles that report the same specific event.",
    )
    non_event_articles: List[NonEventArticle] = Field(
        default_factory=list,
        description="Articles determined not to describe an identifiable event.",
    )
    uncertain_articles: List[UncertainArticle] = Field(
        default_factory=list,
        description="Articles whose titles are insufficient to decide.",
    )

    @model_validator(mode="after")
    def _not_all_empty(self):
        if not (self.event_groups or self.non_event_articles or self.uncertain_articles):
            raise ValueError("model returned an empty result; likely failed to process input")
        return self



## LLM structured output model for first pass event resolution
class MatchCandidate(BaseModel):
    event_ref: str
    decision: Literal["match_similar_article_event", "match_same_batch"]
    article_refs: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str


class CreateNew(BaseModel):
    temporary_event_id: str
    event_title: str
    article_refs: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str


class UncertainArticle(BaseModel):
    article_ref: str
    reason: str


class FirstPassEventResolutionResult(BaseModel):
    match_candidate: List[MatchCandidate] = Field(default_factory=list)
    create_new: List[CreateNew] = Field(default_factory=list)
    uncertain_articles: List[UncertainArticle] = Field(default_factory=list)
    
    @model_validator(mode="after")
    def _not_all_empty(self):
        if not (self.match_candidate or self.create_new or self.uncertain_articles or self.discarded_articles):
            raise ValueError("model returned an empty result; likely failed to process input")
        return self


## LLM structured output model for event summary
class EventSummaryResult(BaseModel):
    event_title: str = Field(
        description="The supplied event title, preserved unless the articles clearly support a more accurate concise title.",
    )
    summary: str = Field(
        min_length=1,
        description="A concise, factual, self-contained summary of the event.",
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence from 0.0 to 1.0 that the summary is supported by the supplied evidence.",
    )
    importance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="General public significance of the event from 0.0 to 1.0, based only on the supplied evidence.",
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Limitations of the supplied evidence that may affect the summary, confidence, or importance scores.",
    )