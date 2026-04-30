"""LLM factory — supports OpenAI, Anthropic, and compatible endpoints."""

import os
import sys


def _service_label(model, base_url):
    """Determine the service name from model and base_url."""
    if "claude" in model.lower():
        anthropic_base = os.environ.get("ANTHROPIC_BASE_URL", "")
        if "anl.gov" in anthropic_base or "argo" in anthropic_base.lower():
            return "Argo"
        return "Anthropic"
    if base_url:
        if "anl.gov" in base_url or "argo" in base_url.lower():
            return "Argo"
        if "alcf" in base_url.lower():
            return "ALCF"
        return f"OpenAI-compatible ({base_url})"
    return "OpenAI"


def create_llm(model, base_url=None):
    """Create LLM — ChatAnthropic for Claude models, ChatOpenAI otherwise.

    Returns (llm, service_label).
    """
    service = _service_label(model, base_url)
    if "claude" in model.lower():
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            sys.exit("Error: pip install langchain-anthropic required for Claude models")
        anthropic_base = os.environ.get("ANTHROPIC_BASE_URL")
        return ChatAnthropic(
            model=model, base_url=anthropic_base or None, streaming=True,
        ), service
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model, base_url=base_url), service
