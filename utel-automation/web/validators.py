from pydantic import BaseModel, Field
from typing import Optional


class RunRequestValidator(BaseModel):
    country: str = Field(..., min_length=2, max_length=50)
    mexico_flow: str = Field(default="")
    sheet_id: str = Field(default="")
    sheet_tab: str = Field(default="")
