"""
Async rate limiters + Groq key rotation.

Groq free tier limits (2025):
  llama-3.3-70b-versatile: 12k TPM, 100k TPD, 500 req/day
  llama-3.1-8b-instant:     6k TPM, 500k TPD, 14.4k req/day

Key rotation:
  Set GROQ_API_KEY=primary_key and GROQ_API_KEYS=key2,key3,... in .env.
  On any 429, we auto-rotate to the next key so the run continues.

Rate buckets:
  groq_acquire()       → 70b model (planner, synthesizer): 5s spacing
  fast_groq_acquire()  → 8b model (executor, critic):      10s spacing
"""
import asyncio
import time
from collections import defaultdict

# ─── Groq key pool ───────────────────────────────────────────────────────────

_groq_keys: list[str] = []
_current_key_idx: int = 0


def _init_keys() -> None:
    global _groq_keys
    try:
        from backend.config.settings import settings
        primary = (settings.GROQ_API_KEY or "").strip()
        extras  = (getattr(settings, "GROQ_API_KEYS", "") or "").strip()
        all_keys = [k.strip() for k in f"{primary},{extras}".split(",") if k.strip()]
        # deduplicate preserving order
        seen: set[str] = set()
        _groq_keys = [k for k in all_keys if not (k in seen or seen.add(k))]  # type: ignore[func-returns-value]
    except Exception as e:
        print(f"[rate_limiter] Key init failed: {e}")
        _groq_keys = []


def get_current_groq_key() -> str:
    """Return the API key that should be used for the next call."""
    if not _groq_keys:
        _init_keys()
    if not _groq_keys:
        return ""
    return _groq_keys[_current_key_idx % len(_groq_keys)]


def rotate_groq_key() -> bool:
    """
    Switch to the next available key after a 429.
    Returns True if we have another key to try, False if only one key.
    """
    global _current_key_idx
    if not _groq_keys:
        _init_keys()
    if len(_groq_keys) <= 1:
        return False
    old_idx = _current_key_idx
    _current_key_idx = (_current_key_idx + 1) % len(_groq_keys)
    key_preview = _groq_keys[_current_key_idx][-8:]
    print(f"[rate_limiter] Key rotated {old_idx + 1}→{_current_key_idx + 1}/{len(_groq_keys)} (…{key_preview})")
    return True


def get_total_keys() -> int:
    if not _groq_keys:
        _init_keys()
    return len(_groq_keys)


# ─── Quality model (llama-3.3-70b) ───────────────────────────────────────────

_quality_lock = asyncio.Lock()
_quality_last: float = 0.0
_quality_backoff_until: float = 0.0


def _quality_spacing() -> float:
    try:
        from backend.config.settings import settings
        return float(getattr(settings, "GROQ_MIN_SPACING_S", 5.0))
    except Exception:
        return 5.0


async def groq_acquire() -> None:
    """Wait for the quality-model token bucket (planner, synthesizer)."""
    global _quality_last, _quality_backoff_until
    async with _quality_lock:
        backoff_wait = _quality_backoff_until - time.monotonic()
        if backoff_wait > 0:
            await asyncio.sleep(backoff_wait)
        spacing = _quality_spacing()
        wait = _quality_last + spacing - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        _quality_last = time.monotonic()


def groq_record_429(retry_after: float = 65.0) -> None:
    """Record a 429 on the quality bucket and rotate key if possible."""
    global _quality_backoff_until
    rotated = rotate_groq_key()
    if rotated:
        # New key → shorter backoff (just the spacing)
        _quality_backoff_until = time.monotonic() + _quality_spacing() + 2
    else:
        _quality_backoff_until = time.monotonic() + retry_after


def get_quality_wait_estimate() -> float:
    """Return estimated seconds until next quality call can fire (for UI hints)."""
    remaining_backoff = max(0.0, _quality_backoff_until - time.monotonic())
    remaining_spacing = max(0.0, _quality_last + _quality_spacing() - time.monotonic())
    return max(remaining_backoff, remaining_spacing)


# ─── Fast model (llama-3.1-8b-instant) ───────────────────────────────────────

_fast_lock = asyncio.Lock()
_fast_last: float = 0.0
_fast_backoff_until: float = 0.0
FAST_MODEL_SPACING_S: float = 10.0


async def fast_groq_acquire() -> None:
    """Wait for the fast-model token bucket (executor, critic, contradiction)."""
    global _fast_last, _fast_backoff_until
    async with _fast_lock:
        backoff_wait = _fast_backoff_until - time.monotonic()
        if backoff_wait > 0:
            await asyncio.sleep(backoff_wait)
        wait = _fast_last + FAST_MODEL_SPACING_S - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        _fast_last = time.monotonic()


def fast_groq_record_429(retry_after: float = 30.0) -> None:
    """Record a 429 on the fast bucket and rotate key if possible."""
    global _fast_backoff_until
    rotated = rotate_groq_key()
    if rotated:
        _fast_backoff_until = time.monotonic() + FAST_MODEL_SPACING_S + 2
    else:
        _fast_backoff_until = time.monotonic() + retry_after


def get_fast_wait_estimate() -> float:
    """Return estimated seconds until next fast call can fire (for UI hints)."""
    remaining_backoff = max(0.0, _fast_backoff_until - time.monotonic())
    remaining_spacing = max(0.0, _fast_last + FAST_MODEL_SPACING_S - time.monotonic())
    return max(remaining_backoff, remaining_spacing)


# ─── Tavily session counter ───────────────────────────────────────────────────

_tavily_counts: dict[str, int] = defaultdict(int)
_tavily_lock = asyncio.Lock()


def _tavily_max() -> int:
    try:
        from backend.config.settings import settings
        return int(getattr(settings, "TAVILY_MAX_PER_SESSION", 8))
    except Exception:
        return 8


async def tavily_acquire(session_id: str) -> bool:
    async with _tavily_lock:
        if _tavily_counts[session_id] >= _tavily_max():
            return False
        _tavily_counts[session_id] += 1
        return True


def tavily_reset(session_id: str) -> None:
    _tavily_counts[session_id] = 0


def tavily_remaining(session_id: str) -> int:
    return max(0, _tavily_max() - _tavily_counts[session_id])
