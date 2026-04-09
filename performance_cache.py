"""
Multi-level translation cache.
"""

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import redis.asyncio as redis

from config import Config
from database import cache_translation, get_cached_translation

cache_logger = logging.getLogger("cache_performance")


class PerformanceCache:
    def __init__(self):
        self.redis_client = None
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.memory_cache_size = 1000
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_version = "v6"

    async def initialize_redis(self):
        try:
            redis_url = getattr(Config, "REDIS_URL", None)
            if redis_url:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                await self.redis_client.ping()
                cache_logger.info("Redis connected")
            else:
                cache_logger.info("Redis URL not configured, using MongoDB + memory cache")
        except Exception as exc:
            cache_logger.warning("Redis unavailable: %s", exc)
            self.redis_client = None

    def _normalize_text_for_cache(self, text: str) -> str:
        if not text:
            return ""

        normalized = re.sub(r"\s+", " ", text.strip()).lower()
        if len(normalized) <= 50:
            normalized = re.sub(r"[^\w\s]", "", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
        else:
            normalized = re.sub(r"[.!?]+\s*$", "", normalized)
        return normalized

    def _sanitize_translation(self, text: str) -> str:
        if not text:
            return ""

        result = (text or "").strip()
        lower = result.lower()
        for prefix in ("translation:", "translate:", "übersetzung:", "перевод:", "переклад:"):
            if lower.startswith(prefix):
                result = result[len(prefix) :].strip()
                break

        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in result.splitlines()]
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines).strip()

    def _generate_smart_key(
        self,
        text: str,
        user_mode: int,
        source_lang: str = "auto",
        target_lang: str = "auto",
    ) -> str:
        normalized_text = self._normalize_text_for_cache(text)
        route = f"{source_lang}->{target_lang}"

        if len(normalized_text) > 100:
            payload = (
                f"{self.cache_version}|mode={user_mode}|route={route}|text={normalized_text}"
            )
            text_hash = hashlib.md5(payload.encode()).hexdigest()[:24]
            return f"{self.cache_version}:t:{text_hash}"

        return (
            f"{self.cache_version}:text:{normalized_text}:"
            f"route:{route}:mode:{user_mode}"
        )

    async def get_translation(
        self,
        text: str,
        user_mode: int,
        user_id: int,
        source_lang: str = "auto",
        target_lang: str = "auto",
    ) -> Optional[str]:
        cache_key = self._generate_smart_key(text, user_mode, source_lang, target_lang)

        if cache_key in self.memory_cache:
            entry = self.memory_cache[cache_key]
            if datetime.now() < entry["expires"]:
                self.cache_hits += 1
                return entry["translation"]
            del self.memory_cache[cache_key]

        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    translation_data = json.loads(cached_data)
                    translation = self._sanitize_translation(translation_data.get("translation"))
                    if translation:
                        self._add_to_memory_cache(cache_key, translation)
                        self.cache_hits += 1
                        return translation
            except Exception as exc:
                cache_logger.warning("Redis get error: %s", exc)

        try:
            cached_translation = await asyncio.to_thread(
                get_cached_translation,
                text,
                source_lang,
                target_lang,
                self.cache_version,
            )
            if cached_translation:
                cached_translation = self._sanitize_translation(cached_translation)
                await self._cache_translation_multilevel(cache_key, cached_translation)
                self.cache_hits += 1
                return cached_translation
        except Exception as exc:
            cache_logger.warning("MongoDB cache get error: %s", exc)

        self.cache_misses += 1
        return None

    async def set_translation(
        self,
        text: str,
        translation: str,
        user_mode: int,
        user_id: int,
        source_lang: str = "auto",
        target_lang: str = "auto",
    ):
        cache_key = self._generate_smart_key(text, user_mode, source_lang, target_lang)
        clean = self._sanitize_translation(translation)
        self._add_to_memory_cache(cache_key, clean)

        tasks = []
        if self.redis_client:
            tasks.append(self._save_to_redis(cache_key, clean))
        tasks.append(
            asyncio.to_thread(
                cache_translation,
                text,
                clean,
                source_lang,
                target_lang,
                self.cache_version,
            )
        )

        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as exc:
                cache_logger.warning("Cache save error: %s", exc)

    def _add_to_memory_cache(self, cache_key: str, translation: str):
        if len(self.memory_cache) >= self.memory_cache_size:
            old_keys = sorted(
                self.memory_cache.keys(),
                key=lambda key: self.memory_cache[key]["created"],
            )[: int(self.memory_cache_size * 0.2)]
            for key in old_keys:
                del self.memory_cache[key]

        self.memory_cache[cache_key] = {
            "translation": translation,
            "created": datetime.now(),
            "expires": datetime.now() + timedelta(hours=1),
        }

    async def _save_to_redis(self, cache_key: str, translation: str):
        try:
            payload = {"translation": translation, "created": datetime.now().isoformat()}
            await self.redis_client.setex(cache_key, 86400, json.dumps(payload))
        except Exception as exc:
            cache_logger.warning("Redis save error: %s", exc)

    async def _cache_translation_multilevel(self, cache_key: str, translation: str):
        self._add_to_memory_cache(cache_key, translation)
        if self.redis_client:
            await self._save_to_redis(cache_key, translation)

    def get_cache_stats(self) -> Dict[str, Any]:
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "memory_cache_size": len(self.memory_cache),
            "redis_available": self.redis_client is not None,
        }

    async def preload_common_translations(self):
        cache_logger.info("Common translations preload skipped")

    async def clear_all(self) -> Dict[str, Any]:
        cleared = {"memory": len(self.memory_cache), "redis": 0}
        self.memory_cache.clear()

        if self.redis_client:
            try:
                cursor = 0
                total = 0
                while True:
                    cursor, keys = await self.redis_client.scan(
                        cursor=cursor,
                        match=f"{self.cache_version}:*",
                        count=500,
                    )
                    if keys:
                        await self.redis_client.delete(*keys)
                        total += len(keys)
                    if cursor == 0:
                        break
                cleared["redis"] = total
            except Exception as exc:
                cache_logger.warning("Redis clear error: %s", exc)

        cache_logger.info("Caches cleared: %s", cleared)
        return cleared


performance_cache = PerformanceCache()


async def get_optimized_translation(
    text: str,
    user_mode: int,
    user_id: int,
    source_lang: str = "auto",
    target_lang: str = "auto",
) -> Optional[str]:
    return await performance_cache.get_translation(
        text=text,
        user_mode=user_mode,
        user_id=user_id,
        source_lang=source_lang,
        target_lang=target_lang,
    )


async def cache_optimized_translation(
    text: str,
    translation: str,
    user_mode: int,
    user_id: int,
    source_lang: str = "auto",
    target_lang: str = "auto",
):
    await performance_cache.set_translation(
        text=text,
        translation=translation,
        user_mode=user_mode,
        user_id=user_id,
        source_lang=source_lang,
        target_lang=target_lang,
    )


async def initialize_performance_cache():
    await performance_cache.initialize_redis()
    await performance_cache.preload_common_translations()
    cache_logger.info("Performance cache initialized")


async def clear_all_caches() -> Dict[str, Any]:
    return await performance_cache.clear_all()
