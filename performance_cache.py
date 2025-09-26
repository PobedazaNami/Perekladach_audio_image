"""
Оптимизированная система кэширования для максимальной производительности бота.
Поддерживает как Redis, так и MongoDB с умными стратегиями кэширования.
"""
import hashlib
import json
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import redis.asyncio as redis
from database import get_cached_translation, cache_translation
from config import Config

# Настройка логирования
cache_logger = logging.getLogger('cache_performance')

class PerformanceCache:
    """Высокопроизводительная система кэширования с множественными уровнями."""
    
    def __init__(self):
        self.redis_client = None
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.memory_cache_size = 1000  # Максимум записей в памяти
        self.cache_hits = 0
        self.cache_misses = 0
        # Версионирование кэша, чтобы не использовать старые ответы с другим форматом
        self.cache_version = "v5"
        
    async def initialize_redis(self):
        """Инициализация подключения к Redis если доступен."""
        try:
            redis_url = getattr(Config, 'REDIS_URL', None)
            if redis_url:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                await self.redis_client.ping()
                cache_logger.info("✅ Redis подключен успешно")
            else:
                cache_logger.info("⚠️ Redis URL не найден, используем только MongoDB + память")
        except Exception as e:
            cache_logger.warning(f"⚠️ Redis недоступен: {e}, используем MongoDB + память")
            self.redis_client = None

    def _normalize_text_for_cache(self, text: str) -> str:
        """
        Умная нормализация текста для эффективного кэширования.
        Приводит разные варианты написания к одному виду.
        """
        if not text:
            return ""
        
        # Базовая нормализация
        normalized = text.strip()
        
        # Убираем лишние пробелы
        import re
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Приводим к нижнему регистру для кэширования
        normalized = normalized.lower()
        
        # Убираем знаки пунктуации в конце для лучшего кэширования
        normalized = re.sub(r'[.!?]+\s*$', '', normalized)
        
        # Специальная обработка для коротких фраз (до 50 символов)
        if len(normalized) <= 50:
            # Убираем все знаки пунктуации для коротких фраз
            normalized = re.sub(r'[^\w\s]', '', normalized)
            # Убираем лишние пробелы снова
            normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized

    def _generate_smart_key(self, text: str, user_mode: int, user_id: int = None) -> str:
        """Генерирует умный ключ для кэширования с учетом контекста."""
        # Умная нормализация текста для лучшего кэширования
        normalized_text = self._normalize_text_for_cache(text)
        
        # Хэш для длинных текстов
        if len(normalized_text) > 100:
            text_hash = hashlib.md5(normalized_text.encode()).hexdigest()[:16]
            cache_key = f"{self.cache_version}:t:{text_hash}:m{user_mode}"
        else:
            # Короткие тексты кэшируем напрямую
            cache_key = f"{self.cache_version}:text:{normalized_text}:mode{user_mode}"
            
        return cache_key

    def _sanitize_translation(self, text: str) -> str:
        """Очищает ответ под формат: только перевод, без префиксов/лапок/пояснений."""
        if not text:
            return ""
        s = (text or "").strip()
        lower = s.lower()
        for prefix in ("переклад:", "translation:", "übersetzung:", "перевод:"):
            if lower.startswith(prefix):
                s = s[len(prefix):].strip()
                break
        # Снимаем парные кавычки
        pairs = [("\"", "\""), ("'", "'"), ("“", "”"), ("„", "“"), ("«", "»")]
        for lq, rq in pairs:
            if s.startswith(lq) and s.endswith(rq) and len(s) >= 2:
                s = s[1:-1].strip()
                break
        # Берем только первый абзац/строку, чтобы отрезать возможные пояснения
        if "\n\n" in s:
            s = s.split("\n\n", 1)[0].strip()
        if "\n" in s:
            s = s.split("\n", 1)[0].strip()
        return " ".join(s.split())

    async def get_translation(self, text: str, user_mode: int, user_id: int) -> Optional[str]:
        """Получает перевод из многоуровневого кэша."""
        cache_key = self._generate_smart_key(text, user_mode, user_id)
        
        # 1. Проверяем кэш в памяти (самый быстрый)
        if cache_key in self.memory_cache:
            cache_entry = self.memory_cache[cache_key]
            if datetime.now() < cache_entry['expires']:
                self.cache_hits += 1
                cache_logger.debug(f"🚀 Memory cache HIT: {cache_key[:20]}...")
                return cache_entry['translation']
            else:
                # Удаляем устаревшую запись
                del self.memory_cache[cache_key]

        # 2. Проверяем Redis (быстрый)
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    translation_data = json.loads(cached_data)
                    translation = self._sanitize_translation(translation_data.get('translation'))
                    if translation:
                        # Добавляем в memory cache для следующего раза
                        self._add_to_memory_cache(cache_key, translation)
                        self.cache_hits += 1
                        cache_logger.debug(f"⚡ Redis cache HIT: {cache_key[:20]}...")
                        return translation
            except Exception as e:
                cache_logger.warning(f"Redis get error: {e}")

        # 3. Проверяем MongoDB (медленнее, но надежнее)
        try:
            # Пробуем получить из Mongo по нормализованному ключу (совместимость)
            cached_translation = await asyncio.to_thread(get_cached_translation, text, "auto", "auto", self.cache_version)
            if cached_translation:
                cached_translation = self._sanitize_translation(cached_translation)
                # Добавляем в оба вышестоящих кэша
                await self._cache_translation_multilevel(cache_key, cached_translation)
                self.cache_hits += 1
                cache_logger.debug(f"💾 MongoDB cache HIT: {cache_key[:20]}...")
                return cached_translation
        except Exception as e:
            cache_logger.warning(f"MongoDB cache get error: {e}")

        self.cache_misses += 1
        cache_logger.debug(f"❌ Cache MISS: {cache_key[:20]}...")
        return None

    async def set_translation(self, text: str, translation: str, user_mode: int, user_id: int):
        """Сохраняет перевод во все уровни кэша."""
        cache_key = self._generate_smart_key(text, user_mode, user_id)
        
        # Параллельное сохранение в разные кэши
        tasks = []
        
        # Санитизируем перед сохранением
        clean = self._sanitize_translation(translation)
        # Memory cache
        self._add_to_memory_cache(cache_key, clean)
        
        # Redis cache
        if self.redis_client:
            tasks.append(self._save_to_redis(cache_key, clean))
            
        # MongoDB cache
        tasks.append(asyncio.to_thread(cache_translation, text, clean, "auto", "auto", self.cache_version))
        
        # Выполняем параллельно
        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                cache_logger.warning(f"Cache save error: {e}")

    def _add_to_memory_cache(self, cache_key: str, translation: str):
        """Добавляет запись в memory cache с управлением размером."""
        # Очищаем кэш если он переполнен
        if len(self.memory_cache) >= self.memory_cache_size:
            # Удаляем 20% самых старых записей
            old_keys = sorted(self.memory_cache.keys(), 
                            key=lambda k: self.memory_cache[k]['created'])[:int(self.memory_cache_size * 0.2)]
            for key in old_keys:
                del self.memory_cache[key]
                
        self.memory_cache[cache_key] = {
            'translation': translation,
            'created': datetime.now(),
            'expires': datetime.now() + timedelta(hours=1)  # Memory cache на 1 час
        }

    async def _save_to_redis(self, cache_key: str, translation: str):
        """Сохраняет в Redis с TTL."""
        try:
            data = {'translation': translation, 'created': datetime.now().isoformat()}
            await self.redis_client.setex(cache_key, 86400, json.dumps(data))  # 24 часа TTL
        except Exception as e:
            cache_logger.warning(f"Redis save error: {e}")

    async def _cache_translation_multilevel(self, cache_key: str, translation: str):
        """Кэширует в memory и Redis."""
        self._add_to_memory_cache(cache_key, translation)
        if self.redis_client:
            await self._save_to_redis(cache_key, translation)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Возвращает статистику кэширования."""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'memory_cache_size': len(self.memory_cache),
            'redis_available': self.redis_client is not None
        }

    async def preload_common_translations(self):
        """Предзагружает популярные переводы в memory cache."""
        try:
            # Можно добавить логику загрузки популярных переводов из БД
            cache_logger.info("🔄 Preloading common translations...")
            # Здесь можно добавить предзагрузку самых популярных фраз
        except Exception as e:
            cache_logger.warning(f"Preload error: {e}")

    async def clear_all(self) -> Dict[str, Any]:
        """Полностью очищает кэши: память, Redis."""
        cleared = {'memory': len(self.memory_cache), 'redis': 0}
        # Clear memory cache
        self.memory_cache.clear()
        # Clear redis keys for our namespace patterns
        if self.redis_client:
            try:
                # Using SCAN to avoid blocking
                ns = self.cache_version
                patterns = [f"{ns}:t:*:m*", f"{ns}:text:*:mode*"]
                total = 0
                for pattern in patterns:
                    cursor = 0
                    while True:
                        cursor, keys = await self.redis_client.scan(cursor=cursor, match=pattern, count=500)
                        if keys:
                            await self.redis_client.delete(*keys)
                            total += len(keys)
                        if cursor == 0:
                            break
                cleared['redis'] = total
            except Exception as e:
                cache_logger.warning(f"Redis clear error: {e}")
        cache_logger.info(f"Кэши очищены: {cleared}")
        return cleared

# Глобальный экземпляр кэша
performance_cache = PerformanceCache()

async def get_optimized_translation(text: str, user_mode: int, user_id: int) -> Optional[str]:
    """Высокоуровневая функция для получения оптимизированного перевода."""
    return await performance_cache.get_translation(text, user_mode, user_id)

async def cache_optimized_translation(text: str, translation: str, user_mode: int, user_id: int):
    """Высокоуровневая функция для сохранения оптимизированного перевода."""
    await performance_cache.set_translation(text, translation, user_mode, user_id)

async def initialize_performance_cache():
    """Инициализация системы кэширования."""
    await performance_cache.initialize_redis()
    await performance_cache.preload_common_translations()
    cache_logger.info("🚀 Performance cache initialized")

async def clear_all_caches() -> Dict[str, Any]:
    """Высокоуровневая функция очистки всех кэшей."""
    return await performance_cache.clear_all()