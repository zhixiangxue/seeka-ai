from .base import EmbeddingBase
from .sentence_transformer import SentenceTransformerEmbedding
from .openai import OpenAIEmbedding


def create(model_uri: str = None, api_key: str = None) -> EmbeddingBase:
    """Factory: return the right EmbeddingBase impl for the given URI.

    Routing rules:
      - No URI          → SentenceTransformerEmbedding (sentence-transformers, zero config)
      - provider=local  → SentenceTransformerEmbedding
      - anything else   → OpenAIEmbedding (covers openai / dashscope / deepseek /
                          any OpenAI-compatible endpoint via base_url)
    """
    if not model_uri:
        return SentenceTransformerEmbedding()

    from ..utils.uri import parse as parse_uri
    parsed = parse_uri(model_uri)
    provider = parsed["provider"].lower()

    if provider == "local":
        return SentenceTransformerEmbedding()

    if not api_key:
        raise ValueError(
            f"api_key is required when embedding_uri is set (provider={provider!r})"
        )

    return OpenAIEmbedding(model_uri=model_uri, api_key=api_key)


__all__ = ["EmbeddingBase", "SentenceTransformerEmbedding", "OpenAIEmbedding", "create"]
