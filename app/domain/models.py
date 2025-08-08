from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SearchProvider(str, Enum):
    GOOGLE = "google"
    BING = "bing"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    OPENROUTER = "openrouter"


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    snippet: Optional[str] = None
    provider: SearchProvider
    rank: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Page(BaseModel):
    url: HttpUrl
    status: int
    html: Optional[str] = None
    final_url: Optional[HttpUrl] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    fetch_time: Optional[datetime] = None


class ExtractedContent(BaseModel):
    url: HttpUrl
    text: str
    title: Optional[str] = None
    lang: Optional[str] = None
    word_count: Optional[int] = None
    author: Optional[str] = None
    publish_date: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LLMMessage(BaseModel):
    role: str  # system, user, assistant
    content: str


class LLMResponse(BaseModel):
    content: str
    tokens_used: Optional[int] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None


class QASource(BaseModel):
    id: int
    title: Optional[str]
    url: HttpUrl
    snippet: Optional[str] = None
    provider: SearchProvider


class QAResponse(BaseModel):
    answer: str
    sources: List[QASource]
    query: str
    tokens_used: Optional[int] = None
    processing_time: Optional[float] = None
    intermediate_steps: Optional[Dict[str, Any]] = None