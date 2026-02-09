import logging
import threading
import time
from typing import Callable

logger = logging.getLogger("dashboard")


class RefreshCache:
    def __init__(self, *, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._cache: dict[tuple[int, int], dict] = {}
        self._locks: dict[tuple[int, int], threading.Lock] = {}

    def clear(self) -> None:
        self._cache.clear()
        self._locks.clear()

    def get_entry(self, key: tuple[int, int]) -> dict:
        hit = self._cache.get(key)
        return dict(hit) if isinstance(hit, dict) else {}

    def _get_lock(self, key: tuple[int, int]) -> threading.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = threading.Lock()
            self._locks[key] = lock
        return lock

    def _refresh_cache(self, key: tuple[int, int], fetch_fn: Callable[[], list[dict]]) -> None:
        started = time.time()
        try:
            logger.info("Background refresh start for %s", key)
            try:
                rows = fetch_fn()
                err = None
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                rows = []
                logger.exception("Background refresh failed for %s", key)

            elapsed = round(time.time() - started, 2)
            logger.info(
                "Background refresh finished for %s in %ss. Rows=%s Error=%s",
                key,
                elapsed,
                len(rows),
                err,
            )

            self._cache[key] = {"ts": time.time(), "df": rows, "error": err, "refreshing": False}
        finally:
            hit = self._cache.get(key)
            if hit:
                hit["refreshing"] = False

    def kickoff_refresh(self, key: tuple[int, int], fetch_fn: Callable[[], list[dict]]) -> None:
        lock = self._get_lock(key)

        with lock:
            hit = self._cache.get(key)
            if hit and hit.get("refreshing"):
                return
            if hit is None:
                self._cache[key] = {"ts": 0.0, "df": [], "error": "warming_up", "refreshing": True}
            else:
                hit["refreshing"] = True

        t = threading.Thread(target=self._refresh_cache, args=(key, fetch_fn), daemon=True)
        t.start()

    def get_cached(self, key: tuple[int, int], fetch_fn: Callable[[], list[dict]]):
        now = time.time()
        hit = self._cache.get(key)
        if hit and (now - hit["ts"]) < self.ttl_seconds:
            if hit.get("error"):
                logger.warning("Cache hit with previous error for %s: %s", key, hit.get("error"))
            return hit["df"], hit.get("error")

        if hit:
            if not hit.get("refreshing"):
                self.kickoff_refresh(key, fetch_fn)
            return hit.get("df", []), hit.get("error") or "stale"

        self.kickoff_refresh(key, fetch_fn)
        return [], "warming_up"
