import re
import tiktoken
from typing import List, Optional
from urllib.parse import urlparse


def clean_text(text: str) -> str:
    """Clean and normalize text content"""
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove common unwanted patterns
    text = re.sub(r'\[.*?\]', '', text)  # Remove [bracketed] content
    text = re.sub(r'\(.*?\)', '', text)  # Remove (parenthetical) content
    
    # Clean up punctuation
    text = re.sub(r'[^\w\s\.\,\!\?\;\:\-]', '', text)
    
    return text.strip()


def truncate_text(text: str, max_tokens: int = 1000, model: str = "gpt-3.5-turbo") -> str:
    """Truncate text to fit within token limit"""
    if not text:
        return ""
    
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to cl100k_base for unknown models
        encoding = tiktoken.get_encoding("cl100k_base")
    
    tokens = encoding.encode(text)
    
    if len(tokens) <= max_tokens:
        return text
    
    # Truncate tokens and decode back to text
    truncated_tokens = tokens[:max_tokens]
    return encoding.decode(truncated_tokens)


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens in text for a given model"""
    if not text:
        return 0
    
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to cl100k_base for unknown models
        encoding = tiktoken.get_encoding("cl100k_base")
    
    return len(encoding.encode(text))


def extract_domain(url: str) -> str:
    """Extract domain from URL"""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks"""
    if not text:
        return []
    
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        chunk = ' '.join(chunk_words)
        chunks.append(chunk)
        
        # Break if we've reached the end
        if i + chunk_size >= len(words):
            break
    
    return chunks


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extract keywords from text (simple implementation)"""
    if not text:
        return []
    
    # Simple keyword extraction based on word frequency
    # In production, you might want to use more sophisticated NLP
    
    # Remove common stop words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
        'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'
    }
    
    # Extract words
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    
    # Filter stop words and count frequency
    word_freq = {}
    for word in words:
        if word not in stop_words:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Sort by frequency and return top keywords
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, freq in sorted_words[:max_keywords]]


def format_citations(text: str, sources: List[dict]) -> str:
    """Format text with proper citations"""
    # This is a simple implementation
    # In production, you might want more sophisticated citation formatting
    
    citation_map = {str(i + 1): source for i, source in enumerate(sources)}
    
    # Replace [1], [2], etc. with proper citations
    def replace_citation(match):
        num = match.group(1)
        if num in citation_map:
            source = citation_map[num]
            return f"[{num}: {source.get('title', 'Unknown')}]"
        return match.group(0)
    
    return re.sub(r'\[(\d+)\]', replace_citation, text)