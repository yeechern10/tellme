from pydantic import BaseModel, Field
from typing import Literal

class EventRequest(BaseModel):
    query_list: list[str] = Field(..., min_length=1, max_length=20)
    time_range: Literal["pd", "pw", "pm", "py"] = "pd"          # past day
    language: str = "en"