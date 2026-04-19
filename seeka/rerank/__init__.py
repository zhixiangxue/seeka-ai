from .base import RerankBase
from .cross_encoder import CrossEncoderRerank
from .cohere import CohereRerank
from .bailian import BailianRerank


def create(model_uri: str = None, api_key: str = None) -> RerankBase:
    """Factory: return the right RerankBase impl for the given URI.

    Routing rules:
      - No URI                   → CrossEncoderRerank (default model)
      - provider=cross-encoder   → CrossEncoderRerank (custom model name)
      - provider=cohere          → CohereRerank
      - provider=bailian         → BailianRerank
    """
    if not model_uri:
        return CrossEncoderRerank()

    from ..utils.uri import parse as parse_uri
    parsed = parse_uri(model_uri)
    provider = parsed["provider"].lower()

    if provider == "cross-encoder":
        model_name = parsed.get("model")
        full_name = f"cross-encoder/{model_name}" if model_name else None
        return CrossEncoderRerank(model_name=full_name)

    if provider == "cohere":
        if not api_key:
            raise ValueError("api_key is required when rerank_uri is set (provider='cohere')")
        return CohereRerank(model_uri=model_uri, api_key=api_key)

    if provider == "bailian":
        if not api_key:
            raise ValueError("api_key is required when rerank_uri is set (provider='bailian')")
        return BailianRerank(model_uri=model_uri, api_key=api_key)

    raise ValueError(f"Unsupported rerank provider: {provider!r}")


__all__ = ["RerankBase", "CrossEncoderRerank", "CohereRerank", "BailianRerank", "create"]
