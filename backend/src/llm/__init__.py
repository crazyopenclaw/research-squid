"""
LLM client abstraction layer.

Wraps the OpenAI-compatible API behind a clean interface so any
provider (OpenAI, Anthropic via proxy, Ollama, etc.) works by
changing environment variables.
"""
