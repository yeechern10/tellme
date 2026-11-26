from pydantic import BaseModel, Field
from typing import List


class MatchedKeyword(BaseModel):
    keyword_ref: str = Field(description="The reference ID of the matched keyword, e.g. 'K_1', 'K_2'")
    relevance_score: float = Field(ge=0.0, le=1.0, description="The relevance score of the matched keyword to the event, from 0.0 to 1.0")
    reason: str = Field(description="A brief explanation based on the event and keyword definition, e.g. 'directly mentioned in title', 'related to event summary'")

class EventKeywordMatchingResult(BaseModel):
    keyword_matches: List[MatchedKeyword] = Field(default_factory=list, description="A list of matched keywords with their reference IDs, relevance scores, and reasons for matching.")