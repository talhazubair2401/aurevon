"""Small security primitives shared by every module: random tokens, hashing, client IP, rate limits."""

import hashlib
import hmac
import math
import secrets
import time
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest


def new_token(nbytes: int = 32) -> str:
    """A URL-safe random token. Only its hash is ever stored."""
    return secrets.token_urlsafe(nbytes)


def token_hash(token: str) -> str:
    """SHA-256 of a high-entropy token; safe to store and to look up by."""
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def client_ip(request: HttpRequest) -> str | None:
    """The caller's address. X-Forwarded-For is trusted only for the configured number of proxy hops."""
    hops: int = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    if hops > 0:
        forwarded = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if len(forwarded) >= hops:
            return str(forwarded[-hops])
    addr = request.META.get("REMOTE_ADDR")
    return str(addr) if addr else None


def user_agent(request: HttpRequest) -> str:
    return str(request.META.get("HTTP_USER_AGENT", ""))[:300]


@dataclass(frozen=True)
class Limit:
    """At most `count` events per `window` seconds."""

    count: int
    window: int


def _bucket_key(name: str, subject: str, window: int) -> str:
    bucket = int(time.time() // window)
    digest = hashlib.sha256(subject.encode()).hexdigest()[:32]  # never store raw emails or IPs as keys
    return f"rl:{name}:{digest}:{bucket}"


def hit(name: str, subject: str, limit: Limit) -> int:
    """Count one event for `subject` and return the count in the current window."""
    key = _bucket_key(name, subject, limit.window)
    cache.add(key, 0, timeout=limit.window + 5)
    try:
        return int(cache.incr(key))
    except ValueError:  # expired between add and incr
        cache.set(key, 1, timeout=limit.window + 5)
        return 1


def count(name: str, subject: str, limit: Limit) -> int:
    return int(cache.get(_bucket_key(name, subject, limit.window), 0))


def is_over(name: str, subject: str, limit: Limit) -> bool:
    return count(name, subject, limit) >= limit.count


def retry_after(limit: Limit) -> int:
    return max(1, limit.window - int(time.time() % limit.window))


def set_lock(name: str, subject: str, seconds: int) -> None:
    cache.set(_lock_key(name, subject), time.time() + seconds, timeout=seconds)


def lock_remaining(name: str, subject: str) -> int:
    until = cache.get(_lock_key(name, subject))
    if until is None:
        return 0
    return max(0, math.ceil(float(until) - time.time()))


def clear_lock(name: str, subject: str) -> None:
    cache.delete(_lock_key(name, subject))


def _lock_key(name: str, subject: str) -> str:
    return f"lock:{name}:{hashlib.sha256(subject.encode()).hexdigest()[:32]}"
