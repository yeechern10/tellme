from pydantic import BaseModel, Field, model_validator
from typing import List, Literal

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