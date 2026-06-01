import json
import re
import asyncio
import hashlib
import contextvars
import time
from typing import Any, Callable, Dict, Optional

from langchain_core.messages import SystemMessage, HumanMessage

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama


# ── Streaming callback via contextvar (avoids modifying LangGraph state) ─
token_callback_var: contextvars.ContextVar = contextvars.ContextVar("token_callback", default=None)


# ── Simple LRU response cache ─────────────────────────────────────────────
_cache: Dict[str, Any] = {}
_cache_max = 64

def _cache_key(prompt: str, system: Optional[str], provider: str, expect_json: bool, temperature: float) -> str:
    raw = f"{provider}|{system}|{prompt}|{expect_json}|{temperature}"
    return hashlib.md5(raw.encode()).hexdigest()


# ── Model Resolution ──────────────────────────────────────────────────────
def get_llm(provider: str, api_key: Optional[str], temperature: float = 0.3, expect_json: bool = False):
    key = api_key if api_key and api_key.strip() else "missing-key"

    if provider == "openai":
        return ChatOpenAI(model="gpt-4o-mini", temperature=temperature, api_key=key)
    elif provider == "groq":
        return ChatGroq(model="llama-3.3-70b-versatile", temperature=temperature, api_key=key)
    elif provider == "anthropic":
        return ChatAnthropic(model="claude-3-haiku-20240307", temperature=temperature, api_key=key)
    elif provider == "gemini":
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=temperature, api_key=key)
    elif provider == "openrouter":
        return ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key,
            model="meta-llama/llama-3.1-8b-instruct:free",
            temperature=temperature
        )
    else:
        kwargs = {
            "model": "qwen2.5:1.5b",
            "temperature": temperature,
            "base_url": "http://localhost:11434",
        }
        if expect_json:
            kwargs["format"] = "json"
        return ChatOllama(**kwargs)


# ── Core LLM call with streaming + timeout ────────────────────────────────
async def call_llm(
    role: str,
    prompt: str,
    system: Optional[str] = None,
    expect_json: bool = False,
    temperature: float = 0.3,
    provider: str = "ollama",
    api_key: Optional[str] = None,
    use_cache: bool = True,
) -> str:
    ckey = _cache_key(prompt, system, provider, expect_json, temperature)
    if use_cache and ckey in _cache:
        return _cache[ckey]

    # Lower temperature for JSON calls → fewer malformed responses
    effective_temp = 0.1 if expect_json else temperature
    llm = get_llm(provider, api_key, effective_temp, expect_json=expect_json)

    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))

    callback = token_callback_var.get()
    full_content = ""

    try:
        if callback and not expect_json:
            async for chunk in asyncio.wait_for(llm.astream(messages), timeout=120):
                if hasattr(chunk, "content") and chunk.content:
                    await callback(chunk.content)
                    full_content += chunk.content
        else:
            response = await asyncio.wait_for(llm.ainvoke(messages), timeout=120)
            full_content = response.content
    except asyncio.TimeoutError:
        raise TimeoutError(f"LLM call timed out after 120s ({role})")
    except Exception as e:
        err_type = _classify_llm_error(e)
        raise RuntimeError(f"[{err_type}] LLM call failed ({role}): {e}")

    if expect_json:
        full_content = _extract_json(full_content)

    # Cache result
    if use_cache:
        if len(_cache) >= _cache_max:
            _cache.pop(next(iter(_cache)))
        _cache[ckey] = full_content

    return full_content


# ── Error classification ─────────────────────────────────────────────────
_ERROR_QUOTA_PATTERNS = [
    "rate limit", "rate_limit", "quota", "insufficient_quota",
    "429", "resource_exhausted", "too many requests",
    "you exceeded your current quota", "exceeded your",
    "credit balance is too low", "insufficient funds",
]
_ERROR_TOKEN_PATTERNS = [
    "token limit", "token_limit", "maximum context length",
    "context length", "too many tokens", "max_tokens",
    "tokens limit", "input too long", "maximum prompt length",
]

def _classify_llm_error(e: Exception) -> str:
    msg = str(e).lower()
    for pat in _ERROR_QUOTA_PATTERNS:
        if pat in msg:
            return "quota_exceeded"
    for pat in _ERROR_TOKEN_PATTERNS:
        if pat in msg:
            return "token_limit_exceeded"
    return "api_error"


def _extract_json(text: str) -> str:
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.replace("```", "").strip()
    return cleaned


# ── JSON-targeted call with exponential backoff retries ───────────────────
async def call_llm_json(
    role: str,
    prompt: str,
    system: Optional[str] = None,
    retries: int = 2,
    provider: str = "ollama",
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    last_raw = ""
    backoff = 0.05

    for attempt in range(retries + 1):
        try:
            raw = await call_llm(
                role=role,
                prompt=prompt,
                system=system,
                expect_json=True,
                provider=provider,
                api_key=api_key,
            )
            last_raw = raw
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError) as e:
            if attempt == retries:
                return {"error": f"JSON parse failed after {retries+1} attempts: {str(e)}", "raw": last_raw}
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 1.0)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            err_type = "api_error"
            msg = str(e)
            if msg.startswith("[") and "]" in msg:
                err_type = msg[1:msg.index("]")]
                msg = msg[msg.index("]") + 1:].strip()
            if attempt == retries:
                return {"error": msg, "error_type": err_type}
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 1.0)

    return {}
