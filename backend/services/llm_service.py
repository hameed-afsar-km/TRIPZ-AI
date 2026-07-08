import json
import os
import re
import asyncio
import hashlib
import contextvars
import time
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from langchain_core.messages import SystemMessage, HumanMessage

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

logger = logging.getLogger("tripz.llm_service")

# ── Ensure .env is loaded (belt-and-suspenders — main.py may not have run) ─
_dotenv_loaded = False
for _dotenv_candidate in [
    Path(__file__).resolve().parent.parent.parent / ".env",  # project root
    Path.cwd() / ".env",                                      # CWD
]:
    if _dotenv_candidate.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(_dotenv_candidate)
            _dotenv_loaded = True
            logger.info("Loaded env from %s", _dotenv_candidate)
            break
        except Exception:
            pass

if not _dotenv_loaded:
    logger.warning("No .env file found — relying on OS environment variables")


# ── Streaming callback via contextvar (avoids modifying LangGraph state) ─
token_callback_var: contextvars.ContextVar = contextvars.ContextVar("token_callback", default=None)


# ── Simple LRU response cache ─────────────────────────────────────────────
_cache: Dict[str, Any] = {}
_cache_max = 64


def _is_valid_key(k: Optional[str]) -> bool:
    return bool(k and k.strip() and k.strip().lower() not in ("undefined", "null", "none", ""))


def resolve_provider(state: dict, agent_role: str) -> str:
    """Return the provider for `agent_role`, checking agent_providers first."""
    ap = state.get("agent_providers", {})
    return ap.get(agent_role, state.get("provider", "ollama"))

def _cache_key(prompt: str, system: Optional[str], provider: str, expect_json: bool, temperature: float) -> str:
    raw = f"{provider}|{system}|{prompt}|{expect_json}|{temperature}"
    return hashlib.md5(raw.encode()).hexdigest()


# ── Model Resolution ──────────────────────────────────────────────────────
def get_llm(provider: str, api_key: Optional[str], temperature: float = 0.3, expect_json: bool = False):
    # Normalise provider name (case-insensitive, common aliases)
    _normalised = provider.strip().lower()
    _aliases = {
        "google": "gemini",
        "gemini": "gemini",
        "google gemini": "gemini",
        "openai": "openai",
        "gpt": "openai",
        "gpt-4o": "openai",
        "gpt-4o-mini": "openai",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "groq": "groq",
        "llama": "groq",
        "openrouter": "openrouter",
    }
    provider = _aliases.get(_normalised, provider)

    if provider == "gemini":
        key = api_key if _is_valid_key(api_key) else os.getenv("GEMINI_API_KEY") or "missing-key"
    elif provider == "groq":
        key = api_key if _is_valid_key(api_key) else os.getenv("GROQ_API_KEY") or "missing-key"
    else:
        key = api_key if _is_valid_key(api_key) else "missing-key"

    # Graceful fallback: if key is missing, try the other well-known provider
    if (not _is_valid_key(key) or key == "missing-key") and provider != "groq":
        fallback_key = os.getenv("GROQ_API_KEY")
        if fallback_key:
            logger.warning("No valid API key for %s — falling back to Groq", provider)
            return get_llm("groq", None, temperature, expect_json)
    elif (not _is_valid_key(key) or key == "missing-key") and provider == "groq":
        fallback_key = os.getenv("GEMINI_API_KEY")
        if fallback_key:
            logger.warning("No valid API key for Groq — falling back to Gemini")
            return get_llm("gemini", None, temperature, expect_json)

    if provider == "openai":
        return ChatOpenAI(model="gpt-4o-mini", temperature=temperature, api_key=key)
    elif provider == "groq":
        kwargs = {"model": "llama-3.3-70b-versatile", "temperature": temperature, "api_key": key}
        if expect_json:
            kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
        return ChatGroq(**kwargs)
    elif provider == "anthropic":
        return ChatAnthropic(model="claude-3-haiku-20240307", temperature=temperature, api_key=key)
    elif provider == "gemini":
        kwargs: dict = {"model": "gemini-2.5-flash", "temperature": temperature, "api_key": key}
        if expect_json:
            kwargs["response_mime_type"] = "application/json"
        return ChatGoogleGenerativeAI(**kwargs)
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
            "num_predict": 4096,
            "client_kwargs": {"timeout": 300},
            "async_client_kwargs": {"timeout": 300},
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
    timeout: int = 60,
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
            async with asyncio.timeout(timeout):
                async for chunk in llm.astream(messages):
                    if hasattr(chunk, "content") and chunk.content:
                        await callback(chunk.content)
                        full_content += chunk.content
        else:
            response = await asyncio.wait_for(llm.ainvoke(messages), timeout=timeout)
            full_content = response.content
    except asyncio.TimeoutError:
        raise TimeoutError(f"LLM call timed out after {timeout}s ({role})")
    except Exception as e:
        msg = str(e).lower()
        is_invalid_key = ("api key not valid" in msg or 
                          "api_key_invalid" in msg or 
                          "invalid api key" in msg or 
                          "api key is invalid" in msg)
        is_unavailable = ("503" in msg or 
                          "service unavailable" in msg or 
                          "high demand" in msg or 
                          "temporarily" in msg or 
                          "unavailable" in msg)
        
        if is_invalid_key or is_unavailable:
            if is_unavailable:
                fallback_timeout = min(timeout, 45)
                logger.warning(
                    "Provider '%s' unavailable (503). Falling back to alternative provider (timeout=%ds).", 
                    provider, fallback_timeout
                )
                if provider == "gemini":
                    fallback_key = os.getenv("GROQ_API_KEY")
                    if fallback_key:
                        return await call_llm(
                            role=role, prompt=prompt, system=system,
                            expect_json=expect_json, temperature=temperature,
                            provider="groq", api_key=None,
                            use_cache=use_cache, timeout=fallback_timeout,
                        )
                elif provider == "groq":
                    fallback_key = os.getenv("GEMINI_API_KEY")
                    if fallback_key:
                        return await call_llm(
                            role=role, prompt=prompt, system=system,
                            expect_json=expect_json, temperature=temperature,
                            provider="gemini", api_key=None,
                            use_cache=use_cache, timeout=fallback_timeout,
                        )
            else:
                env_key = os.getenv(f"{provider.upper()}_API_KEY", "")
                is_same_key = bool(api_key and env_key and api_key.strip() == env_key.strip())

                if api_key and _is_valid_key(api_key) and not is_same_key:
                    # Custom user key failed and server env key is different — retry with env key.
                    # Use a shorter timeout (30s max) so Gemini's slowness doesn't cascade.
                    retry_timeout = min(timeout, 30)
                    logger.warning(
                        "Custom API key for provider '%s' failed validation. Retrying with server environment key (timeout=%ds).",
                        provider, retry_timeout
                    )
                    return await call_llm(
                        role=role, prompt=prompt, system=system,
                        expect_json=expect_json, temperature=temperature,
                        provider=provider, api_key=None,
                        use_cache=use_cache, timeout=retry_timeout,
                    )

                # Server environment key failed (or custom key is same as env key).
                # Fall back to a different provider with a shorter timeout.
                fallback_timeout = min(timeout, 45)
                if provider == "gemini":
                    fallback_key = os.getenv("GROQ_API_KEY")
                    if fallback_key:
                        logger.warning("Gemini API key failed validation. Falling back to Groq (timeout=%ds).", fallback_timeout)
                        return await call_llm(
                            role=role, prompt=prompt, system=system,
                            expect_json=expect_json, temperature=temperature,
                            provider="groq", api_key=None,
                            use_cache=use_cache, timeout=fallback_timeout,
                        )
                elif provider == "groq":
                    fallback_key = os.getenv("GEMINI_API_KEY")
                    if fallback_key:
                        logger.warning("Groq API key failed validation. Falling back to Gemini (timeout=%ds).", fallback_timeout)
                        return await call_llm(
                            role=role, prompt=prompt, system=system,
                            expect_json=expect_json, temperature=temperature,
                            provider="gemini", api_key=None,
                            use_cache=use_cache, timeout=fallback_timeout,
                        )

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


def _try_fix_json(raw: str) -> str:
    obj_depth = 0
    start = -1
    end = -1
    for i, ch in enumerate(raw):
        if ch == '{':
            if obj_depth == 0:
                start = i
            obj_depth += 1
        elif ch == '}':
            obj_depth -= 1
            if obj_depth == 0 and start != -1:
                end = i + 1
                break
            if obj_depth < 0:
                break
    if start != -1 and end != -1:
        raw = raw[start:end]
    elif start != -1 and end == -1:
        raw = raw[start:]
    raw = raw.strip()
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    raw = re.sub(r"(?<=[{,\s])'(?=\w)", '"', raw)
    raw = re.sub(r"(?<=\w)'(?=[},\s])", '"', raw)
    raw = re.sub(r"(?<!\\)'", '"', raw)

    def _fix_keys(m: re.Match) -> str:
        return f'"{m.group(1)}":'

    raw = re.sub(r'(?<=[{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', _fix_keys, raw)

    return raw


# ── JSON-targeted call with exponential backoff retries ───────────────────
async def call_llm_json(
    role: str,
    prompt: str,
    system: Optional[str] = None,
    retries: int = 0,
    provider: str = "ollama",
    api_key: Optional[str] = None,
    timeout: int = 60,
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
                timeout=timeout,
            )
            last_raw = raw
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                fixed = _try_fix_json(raw)
                return json.loads(fixed)
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
