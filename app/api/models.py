from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class SearchProvidersEnum(str, Enum):
    GOOGLE = "google"
    BING = "bing"


class LLMProvidersEnum(str, Enum):
    OPENAI = "openai"
    OPENROUTER = "openrouter"


# Request Models
class SearchRequest(BaseModel):
    q: str = Field(..., description="Search query")
    providers: List[SearchProvidersEnum] = Field(default=[SearchProvidersEnum.GOOGLE], description="Search providers to use")
    num: int = Field(default=10, ge=1, le=50, description="Number of results to return")
    lang: Optional[str] = Field(None, description="Language code (e.g., 'en')")
    country: Optional[str] = Field(None, description="Country code (e.g., 'US')")


class CrawlRequest(BaseModel):
    urls: List[HttpUrl] = Field(..., description="URLs to crawl")
    render_js: bool = Field(default=False, description="Whether to render JavaScript")
    max_concurrent: int = Field(default=5, ge=1, le=10, description="Maximum concurrent requests")


class SummarizeRequest(BaseModel):
    text: Optional[str] = Field(None, description="Text to summarize")
    url: Optional[HttpUrl] = Field(None, description="URL to extract and summarize")
    model: Optional[str] = Field(None, description="LLM model to use (e.g., 'openai:gpt-4o-mini')")
    max_length: int = Field(default=200, ge=50, le=1000, description="Maximum summary length in words")


class QARequest(BaseModel):
    query: str = Field(..., description="Question to answer")
    search_providers: List[SearchProvidersEnum] = Field(
        default=[SearchProvidersEnum.GOOGLE], 
        description="Search providers to use"
    )
    num_search_results: int = Field(default=8, ge=1, le=20, description="Number of search results to fetch")
    max_docs_to_crawl: int = Field(default=5, ge=1, le=10, description="Maximum documents to crawl")
    model: Optional[str] = Field(None, description="LLM model to use")
    render_js: bool = Field(default=False, description="Whether to render JavaScript when crawling")
    return_citations: bool = Field(default=True, description="Whether to return source citations")
    include_debug: bool = Field(default=False, description="Whether to include debug information")


# Response Models
class SearchResultResponse(BaseModel):
    title: str
    url: HttpUrl
    snippet: Optional[str] = None
    provider: SearchProvidersEnum
    rank: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    results: List[SearchResultResponse]
    query: str
    total_results: int
    providers_used: List[SearchProvidersEnum]
    processing_time: Optional[float] = None


class CrawlResultResponse(BaseModel):
    url: HttpUrl
    status: str
    text: str
    title: Optional[str] = None
    word_count: int
    language: Optional[str] = None
    author: Optional[str] = None
    publish_date: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CrawlResponse(BaseModel):
    results: List[CrawlResultResponse]
    total_urls: int
    successful_crawls: int
    processing_time: Optional[float] = None


class SummarizeResponse(BaseModel):
    summary: str
    original_length: int
    summary_length: int
    tokens_used: Optional[int] = None
    model: Optional[str] = None
    processing_time: Optional[float] = None


class QASourceResponse(BaseModel):
    id: int
    title: Optional[str]
    url: HttpUrl
    snippet: Optional[str] = None
    provider: SearchProvidersEnum


class QAResponse(BaseModel):
    answer: str
    sources: List[QASourceResponse]
    query: str
    tokens_used: Optional[int] = None
    processing_time: Optional[float] = None
    intermediate_steps: Optional[Dict[str, Any]] = None


# Error Response Models
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None