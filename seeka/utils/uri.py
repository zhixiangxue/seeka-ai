"""
URI utilities for seeka model URIs. Ported from chak-ai.

Supports two formats:
  Simple : provider/model
  Full   : provider@base_url:model?params  (use ~ for default base_url)

Examples:
    parse("openai/text-embedding-3-small")
    # {'provider': 'openai', 'base_url': None, 'model': 'text-embedding-3-small', 'params': {}}

    parse("openai@https://api.openai.com/v1:text-embedding-3-small")
    # {'provider': 'openai', 'base_url': 'https://api.openai.com/v1', 'model': '...', 'params': {}}
"""
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode


def parse(uri: str) -> Dict[str, Any]:
    """Parse a model URI into provider, base_url, model, params."""
    if not uri or not isinstance(uri, str):
        raise ValueError("URI must be a non-empty string")
    if "@" in uri:
        return _parse_full_format(uri)
    if "/" in uri:
        return _parse_simple_format(uri)
    raise ValueError(
        f"Invalid URI format: {uri}\n"
        f"Expected: 'provider/model' or 'provider@base_url:model'"
    )


def _parse_simple_format(uri: str) -> Dict[str, Any]:
    if "?" in uri:
        raise ValueError(f"Simple format URI cannot contain query parameters: {uri}")
    parts = uri.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid simple format URI: {uri}")
    provider, model = parts
    if any(c in provider for c in "@:~?#/"):
        raise ValueError(f"Invalid provider name: {provider}")
    return {"provider": provider, "base_url": None, "model": model, "params": {}}


def _parse_full_format(uri: str) -> Dict[str, Any]:
    query_string = None
    if "?" in uri:
        uri, query_string = uri.split("?", 1)

    if "@" not in uri:
        raise ValueError(f"Invalid URI format: missing '@' in {uri}")
    provider, rest = uri.split("@", 1)

    if ":" not in rest:
        raise ValueError(f"Invalid URI format: missing ':' in {uri}")

    base_url_part, model = _split_base_url_and_model(rest)
    base_url = None if base_url_part == "~" else base_url_part

    params: Dict[str, Any] = {}
    if query_string:
        parsed = parse_qs(query_string, keep_blank_values=False)
        params = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

    return {"provider": provider, "base_url": base_url, "model": model, "params": params}


def _split_base_url_and_model(rest: str):
    """Split 'base_url:model' handling HTTP URLs and host:port formats."""
    # Default base_url placeholder
    if rest.startswith("~:"):
        return "~", rest[2:]

    # Full HTTP(S) URL
    if rest.startswith("http://") or rest.startswith("https://"):
        protocol_end = rest.index("//") + 2
        after_protocol = rest[protocol_end:]
        for i, ch in enumerate(after_protocol):
            if ch == ":":
                next_part = after_protocol[i + 1: i + 10]
                if next_part and not next_part[0].isdigit() and next_part[0] != "/":
                    split = protocol_end + i
                    return rest[:split], rest[split + 1:]
        last = rest.rfind(":")
        return rest[:last], rest[last + 1:]

    # host:port:model  or  host:model
    first = rest.index(":")
    after_first = rest[first + 1:]
    if after_first and after_first[0].isdigit():
        port_end = first + 1
        while port_end < len(rest) and rest[port_end].isdigit():
            port_end += 1
        if port_end < len(rest) and rest[port_end] == ":":
            return rest[:port_end], rest[port_end + 1:]
        last = rest.rfind(":")
        return rest[:last], rest[last + 1:]

    return rest[:first], rest[first + 1:]
