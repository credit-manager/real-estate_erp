from pathlib import Path

p = Path("routes/auth.py")
text = p.read_text(encoding="utf-8")
original = text

text = text.replace("import time\nimport threading\n", "import hashlib\nimport time\nimport threading\n")

old = '''_LOGIN_FAILURES = {}        # key -> {"count": int, "lock_until": float}\n_cleanup_lock = threading.Lock()\n'''
new = '''_LOGIN_FAILURES = {}        # development/Desktop fallback only\n_cleanup_lock = threading.Lock()\n_REDIS_CLIENT = None\n_REDIS_UNAVAILABLE = False\n\n\ndef _redis_login_store():\n    global _REDIS_CLIENT, _REDIS_UNAVAILABLE\n    if _REDIS_CLIENT is not None:\n        return _REDIS_CLIENT\n    if _REDIS_UNAVAILABLE:\n        return None\n    env = str(os.environ.get("DYNAMICPRO_ENV", "")).lower()\n    if env not in {"production", "prod"}:\n        return None\n    uri = os.environ.get("REDIS_URL") or os.environ.get("RATELIMIT_STORAGE_URI")\n    if not uri:\n        raise RuntimeError("Production login protection requires REDIS_URL or RATELIMIT_STORAGE_URI.")\n    try:\n        import redis\n        _REDIS_CLIENT = redis.Redis.from_url(uri, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)\n        _REDIS_CLIENT.ping()\n        return _REDIS_CLIENT\n    except Exception as exc:\n        _REDIS_UNAVAILABLE = True\n        raise RuntimeError("Production login protection cannot connect to Redis.") from exc\n\n\ndef _redis_key(prefix, key):\n    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()\n    return f"dynamicpro:login:{prefix}:{digest}"\n'''
if old not in text:
    raise SystemExit("login failure state block not found")
text = text.replace(old, new, 1)

start = text.index("def _check_login_lock(key):")
end = text.index("\n\ndef login_required", start)
replacement = '''def _check_login_lock(key):\n    """Return remaining lock seconds, using Redis for production."""\n    store = _redis_login_store()\n    if store is not None:\n        lock_key = _redis_key("lock", key)\n        remaining = store.ttl(lock_key)\n        return max(int(remaining), 0)\n    rec = _LOGIN_FAILURES.get(key)\n    if not rec:\n        return 0\n    lock_until = rec.get("lock_until") or 0\n    remaining = int(lock_until - time.time())\n    if remaining > 0:\n        return remaining\n    if lock_until:\n        _LOGIN_FAILURES.pop(key, None)\n    return 0\n\n\ndef _register_login_failure(key):\n    """Register a failed login atomically in Redis for production."""\n    store = _redis_login_store()\n    if store is not None:\n        count_key = _redis_key("count", key)\n        count = store.incr(count_key)\n        if count == 1:\n            store.expire(count_key, LOGIN_LOCK_SECONDS)\n        if count >= MAX_LOGIN_ATTEMPTS:\n            store.set(_redis_key("lock", key), "1", ex=LOGIN_LOCK_SECONDS)\n        if count >= 3:\n            time.sleep(min(0.3 * (count - 2), 2.0))\n        return\n    rec = _LOGIN_FAILURES.setdefault(key, {"count": 0, "lock_until": 0})\n    rec["count"] += 1\n    if rec["count"] >= MAX_LOGIN_ATTEMPTS:\n        rec["lock_until"] = time.time() + LOGIN_LOCK_SECONDS\n    if rec["count"] >= 3:\n        time.sleep(min(0.3 * (rec["count"] - 2), 2.0))\n\n\ndef _reset_login_failures(key):\n    store = _redis_login_store()\n    if store is not None:\n        store.delete(_redis_key("count", key), _redis_key("lock", key))\n        return\n    _LOGIN_FAILURES.pop(key, None)\n'''
text = text[:start] + replacement + text[end:]

if text == original:
    raise SystemExit("no auth guard patch applied")
p.write_text(text, encoding="utf-8")
print("distributed login guard applied")
