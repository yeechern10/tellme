from pydantic import BaseModel, Field
from typing import List

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

class MatchedKeyword(BaseModel):
    keyword_ref: str = Field(description="The reference ID of the matched keyword, e.g. 'K_1', 'K_2'")
    relevance_score: float = Field(ge=0.0, le=1.0, description="The relevance score of the matched keyword to the event, from 0.0 to 1.0")
    reason: str = Field(description="A brief explanation based on the event and keyword definition, e.g. 'directly mentioned in title', 'related to event summary'")

class EventKeywordMatchingResult(BaseModel):
    keyword_matches: List[MatchedKeyword] = Field(default_factory=list, description="A list of matched keywords with their reference IDs, relevance scores, and reasons for matching.")