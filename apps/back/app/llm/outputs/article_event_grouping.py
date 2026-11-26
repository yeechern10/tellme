from pydantic import BaseModel, Field, model_validator
from typing import List, Literal

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
