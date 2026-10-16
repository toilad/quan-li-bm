"""Loaded first (pytest -p): the anthropic 1.x SDK uses httpx2, which respx would not see.
Aliasing makes `import httpx` resolve to httpx2 so every HTTP call — SDK included — is mocked."""
import httpx2

httpx2.alias_httpx()
