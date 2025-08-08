import httpx
from typing import List, Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from app.domain.contracts import LLMClient
from app.domain.models import LLMMessage, LLMResponse
from app.core.errors import LLMError
from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class OpenRouterClient(LLMClient):
    """OpenRouter API client for accessing multiple LLM providers"""
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        base_url: str = "https://openrouter.ai/api/v1",
        default_model: str = "anthropic/claude-3-haiku"
    ):
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url
        self.default_model = default_model
        self.client = httpx.AsyncClient(timeout=settings.llm_timeout)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def complete(
        self, 
        messages: List[LLMMessage], 
        model: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion using OpenRouter API"""
        
        if not self.api_key:
            raise LLMError("OpenRouter API key not configured")
        
        model = model or self.default_model
        
        # Convert messages to OpenAI-compatible format
        openrouter_messages = [
            {"role": msg.role, "content": msg.content} 
            for msg in messages
        ]
        
        payload = {
            "model": model,
            "messages": openrouter_messages,
            "temperature": kwargs.get("temperature", 0.1),
            "max_tokens": kwargs.get("max_tokens", 2000),
            "top_p": kwargs.get("top_p", 1.0),
        }
        
        # Add optional parameters
        if "stop" in kwargs:
            payload["stop"] = kwargs["stop"]
        if "stream" in kwargs:
            payload["stream"] = kwargs["stream"]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://searchapi.example.com",  # Required by OpenRouter
            "X-Title": "SearchAPI"  # Required by OpenRouter
        }
        
        try:
            logger.info("Making OpenRouter completion request", model=model, messages_count=len(messages))
            
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "error" in data:
                raise LLMError(f"OpenRouter API error: {data['error']['message']}")
            
            choice = data["choices"][0]
            usage = data.get("usage", {})
            
            result = LLMResponse(
                content=choice["message"]["content"],
                tokens_used=usage.get("total_tokens"),
                model=data.get("model"),
                finish_reason=choice.get("finish_reason")
            )
            
            logger.info("OpenRouter completion successful", 
                       model=model, 
                       tokens_used=result.tokens_used,
                       finish_reason=result.finish_reason)
            
            return result
            
        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get("error", {}).get("message", "")
            except:
                pass
            
            logger.error("OpenRouter HTTP error", 
                        status_code=e.response.status_code, 
                        error_detail=error_detail)
            raise LLMError(f"OpenRouter API error {e.response.status_code}: {error_detail}")
            
        except httpx.RequestError as e:
            logger.error("OpenRouter request error", error=str(e))
            raise LLMError(f"OpenRouter request failed: {str(e)}")
        except Exception as e:
            logger.error("OpenRouter unexpected error", error=str(e))
            raise LLMError(f"OpenRouter completion failed: {str(e)}")
    
    async def is_available(self) -> bool:
        """Check if OpenRouter client is available"""
        return bool(self.api_key)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()