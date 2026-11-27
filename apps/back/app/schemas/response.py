from pydantic import BaseModel, Field
from uuid import UUID

class ArticleShow(BaseModel):
    title: str = Field(..., description="The title of the article")
    link: str = Field(..., description="The link to the article")
    snippet: str = Field(..., description="A snippet of the article")
    published_at: str = Field(..., description="The publication timestamp of the article")
    source: str = Field(..., description="The source of the article")

class KeywordShow(BaseModel):
    label: str = Field(..., description="The label of the keyword")
    path: list[str] = Field(..., description="The path of the keyword")

class EventShow(BaseModel):
    event_id: UUID = Field(..., description="The UUID of the event")
    title: str = Field(..., description="The title of the event")
    summary: str = Field(..., description="The summary of the event")
    published_at_range: tuple[str, str] = Field(..., description="The published range of the event")
    importance_score: float = Field(..., description="The importance score of the event")
    keywords: list[KeywordShow] = Field(..., description="The keywords and their paths associated with the event")
    articles: list[ArticleShow] = Field(..., description="The articles associated with the event")

class EventResponse(BaseModel):
    events: list[EventShow] = Field(..., description="The list of events returned in the response")