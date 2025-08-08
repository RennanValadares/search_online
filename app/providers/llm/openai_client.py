import httpx
from typing import List, Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from app.domain.contracts import LLMClient
from app.domain.models import LLMMessage, LLMResponse
from app.core.errors import LLMError
from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class OpenAIClient(LLMClient):
    """OpenAI API client"""
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4o-mini"
    ):
        self.api_key = api_key or settings.openai_api_key
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
        """Generate completion using OpenAI API"""
        
        if not self.api_key:
            raise LLMError("OpenAI API key not configured")
        
        model = model or self.default_model
        
        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content} 
            for msg in messages
        ]
        
        payload = {
            "model": model,
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", 0.1),
            "max_tokens": kwargs.get("max_tokens", 2000),
            "top_p": kwargs.get("top_p", 1.0),
            "frequency_penalty": kwargs.get("frequency_penalty", 0.0),
            "presence_penalty": kwargs.get("presence_penalty", 0.0),
        }
        
        # Add optional parameters
        if "stop" in kwargs:
            payload["stop"] = kwargs["stop"]
        if "stream" in kwargs:
            payload["stream"] = kwargs["stream"]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            logger.info("Making OpenAI completion request", model=model, messages_count=len(messages))
            
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "error" in data:
                raise LLMError(f"OpenAI API error: {data['error']['message']}")
            
            choice = data["choices"][0]
            usage = data.get("usage", {})
            
            result = LLMResponse(
                content=choice["message"]["content"],
                tokens_used=usage.get("total_tokens"),
                model=data.get("model"),
                finish_reason=choice.get("finish_reason")
            )
            
            logger.info("OpenAI completion successful", 
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
            
            logger.error("OpenAI HTTP error", 
                        status_code=e.response.status_code, 
                        error_detail=error_detail)
            raise LLMError(f"OpenAI API error {e.response.status_code}: {error_detail}")
            
        except httpx.RequestError as e:
            logger.error("OpenAI request error", error=str(e))
            raise LLMError(f"OpenAI request failed: {str(e)}")
        except Exception as e:
            logger.error("OpenAI unexpected error", error=str(e))
            raise LLMError(f"OpenAI completion failed: {str(e)}")
    
    async def is_available(self) -> bool:
        """Check if OpenAI client is available"""
        return bool(self.api_key)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()