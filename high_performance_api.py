"""
Высокопроизводительный модуль для асинхронной работы с внешними API.
Включает connection pooling, retry механизмы, и оптимизированную обработку.
"""
import asyncio
import aiohttp
import time
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import openai
from openai import AsyncOpenAI
import json
from config import Config

# Настройка логирования
api_logger = logging.getLogger('api_performance')

@dataclass
class APIResponse:
    """Структура для ответа API."""
    success: bool
    content: str = ""
    error: str = ""
    response_time: float = 0.0
    tokens_used: int = 0

class HighPerformanceAPI:
    """Высокопроизводительный класс для работы с внешними API."""
    
    def __init__(self):
        self.openai_client = None
        self.session = None
        self.request_semaphore = asyncio.Semaphore(10)  # Максимум 10 одновременных запросов
        self.retry_delays = [0.1, 0.3, 0.8, 2.0]  # Экспоненциальная задержка
        
        # Статистика
        self.total_requests = 0
        self.successful_requests = 0
        self.average_response_time = 0.0
        
    async def initialize(self):
        """Инициализация клиентов и connection pool."""
        try:
            # Настройка OpenAI с connection pool
            self.openai_client = AsyncOpenAI(
                api_key=Config.OPENAI_API_KEY,
                timeout=30.0,
                max_retries=3,
            )
            
            # Настройка aiohttp сессии с connection pool
            connector = aiohttp.TCPConnector(
                limit=100,  # Общий pool connections
                limit_per_host=20,  # Connections на хост
                ttl_dns_cache=300,  # DNS cache на 5 минут
                use_dns_cache=True,
                keepalive_timeout=30
            )
            
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={'User-Agent': 'TelegramBot/1.0'}
            )
            
            api_logger.info("🚀 High-performance API clients initialized")
            
        except Exception as e:
            api_logger.error(f"❌ API initialization failed: {e}")
            raise

    async def translate_text_optimized(self, text: str, user_mode: int, user_id: int) -> APIResponse:
        """Оптимизированный перевод текста с retry и метриками."""
        start_time = time.time()
        
        async with self.request_semaphore:
            for attempt, delay in enumerate(self.retry_delays):
                try:
                    if attempt > 0:
                        await asyncio.sleep(delay)
                        api_logger.info(f"🔄 Retry attempt {attempt} for user {user_id}")
                    
                    # Получаем промпт в зависимости от режима
                    prompt = self._get_prompt_for_mode(user_mode)
                    
                    response = await self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": text}
                        ],
                        max_tokens=512,
                        temperature=0.0,  # Максимально детерминированные результаты
                        timeout=25.0
                    )
                    
                    raw = response.choices[0].message.content or ""
                    translation = self._postprocess_translation(raw)
                    response_time = time.time() - start_time
                    tokens_used = response.usage.total_tokens if response.usage else 0
                    
                    # Обновляем статистику
                    self._update_stats(response_time, True)
                    
                    api_logger.info(f"✅ Translation success: {response_time:.2f}s, {tokens_used} tokens")
                    
                    return APIResponse(
                        success=True,
                        content=translation,
                        response_time=response_time,
                        tokens_used=tokens_used
                    )
                    
                except openai.RateLimitError as e:
                    api_logger.warning(f"⚠️ Rate limit hit, waiting {delay * 2}s...")
                    await asyncio.sleep(delay * 2)  # Увеличенная задержка для rate limit
                    continue
                    
                except openai.APITimeoutError as e:
                    if attempt < len(self.retry_delays) - 1:
                        api_logger.warning(f"⏱️ Timeout, retrying in {delay}s...")
                        continue
                    else:
                        self._update_stats(time.time() - start_time, False)
                        return APIResponse(success=False, error="Timeout after retries")
                        
                except Exception as e:
                    if attempt < len(self.retry_delays) - 1:
                        api_logger.warning(f"❌ Error: {e}, retrying in {delay}s...")
                        continue
                    else:
                        self._update_stats(time.time() - start_time, False)
                        return APIResponse(success=False, error=str(e))
            
            # Если все попытки неудачны
            self._update_stats(time.time() - start_time, False)
            return APIResponse(success=False, error="All retry attempts failed")

    async def batch_translate(self, texts: List[str], user_mode: int, user_id: int) -> List[APIResponse]:
        """Пакетная обработка переводов с контролем параллелизма."""
        api_logger.info(f"🔀 Batch translating {len(texts)} texts for user {user_id}")
        
        # Создаем задачи для параллельного выполнения
        tasks = [
            self.translate_text_optimized(text, user_mode, user_id) 
            for text in texts
        ]
        
        # Выполняем с контролем concurrency
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем исключения
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                api_logger.error(f"❌ Batch item {i} failed: {result}")
                processed_results.append(APIResponse(success=False, error=str(result)))
            else:
                processed_results.append(result)
                
        return processed_results

    def _get_prompt_for_mode(self, mode: int) -> str:
        """Возвращает оптимизированный промпт для режима."""
        prompts = {
            1: (
                "Ти перекладацький двигун (DE⇄UK/RU). Правила:\n"
                "• Якщо вхід українською або російською — переклади лише на німецьку.\n"
                "• Якщо вхід німецькою — переклади лише на українську.\n"
                "• ВІДПОВІДЬ МАЄ МІСТИТИ ТІЛЬКИ ПЕРЕКЛАД без пояснень/лапок/питань/додаткових речень.\n"
                "• НІЧОГО НЕ ОПУСКАЙ: збережи всю інформацію, модальність, ввічливі/вступні конструкції (типу ‘я хотів запитати…’), час і аспект. Не скорочуй і не перефразовуй сенс.\n"
                "• ТОЧНІСТЬ ЗМІСТУ: не замінюй слова на близькі за змістом або іншу семантику (напр., ‘помите’ ≠ ‘пошкоджене’). Зберігай полярність/стан/аспект. За неоднозначності обирай найбільш буквальний словниковий відповідник.\n"
                "• Імена власні й бренди зберігай як є; не перевіряй їх існування, не уточнюй і не коментуй.\n"
                "• ДОДАТКОВО для виходу німецькою (UK/RU → DE): якщо вхід — одне слово або коротка іменникова фраза (до 3 слів), поверни: правильний означений артикль + іменник — та український переклад в один рядок (напр.: ‘der Bahnhof — вокзал’). Якщо користувач вказав артикль невірно — виправ. Для множини використовуй ‘die’. Без пояснень.\n"
                "• Виняток: якщо вхід німецькою і це коротке іменникове словосполучення (з артиклем або без), поверни правильний артикль+іменник німецькою (а не переклад на українську).\n"
                "• Формат відповіді: лише переклад/форма однією лінією."
            ),
            2: (
                "Ти перекладацький двигун для зображень (DE⇄UK/RU). Переклад будь-якого введеного тексту:\n"
                "• UK/RU → DE; DE → UK.\n"
                "• Тільки переклад, без пояснень/лапок/додаткових фраз.\n"
                "• НІЧОГО НЕ ОПУСКАЙ: збережи вступні/ввічливі конструкції, модальність, час, аспект. Не скорочуй сенс.\n"
                "• ТОЧНІСТЬ ЗМІСТУ: не замінюй слова на близькі за змістом; за неоднозначності обирай буквальний відповідник.\n"
                "• Імена власні не змінюй і не коментуй.\n"
                "• ДОДАТКОВО: якщо вихід німецькою і вхід — одне слово або коротка іменникова фраза, поверни: правильний означений артикль + іменник — та український переклад в один рядок (напр.: ‘der Bahnhof — вокзал’). Для множини — ‘die’.\n"
                "Формат: лише переклад/форма однією лінією."
            ),
            3: (
                "Ти перекладацький двигун для аудіо (DE⇄UK/RU). Після розпізнавання тексту:\n"
                "• UK/RU → DE; DE → UK.\n"
                "• Відповідай тільки перекладом, без пояснень і уточнень.\n"
                "• НІЧОГО НЕ ОПУСКАЙ: збережи вступні/ввічливі конструкції (напр. ‘я хотів запитати…’), модальність, час, аспект.\n"
                "• ТОЧНІСТЬ ЗМІСТУ: не підмінюй значення (напр., ‘помите’ не ‘пошкоджене’); обирай буквальний відповідник.\n"
                "• Імена власні зберігай як є.\n"
                "• ДОДАТКОВО: якщо вихід німецькою і вхід — одне слово або коротка іменникова фраза, поверни: правильний означений артикль + іменник — та український переклад в один рядок (напр.: ‘der Bahnhof — вокзал’). Для множини — ‘die’.\n"
                "Формат: лише переклад/форма однією лінією."
            )
        }
        return prompts.get(mode, prompts[1])

    def _postprocess_translation(self, text: str) -> str:
        """Минимальная очистка ответа модели под формат: только перевод одной строкой."""
        s = (text or "").strip()
        # Удаляем технические префиксы вида "Переклад:", "Translation:", "Übersetzung:"
        lower = s.lower()
        for prefix in ("переклад:", "translation:", "übersetzung:", "перевод:"):
            if lower.startswith(prefix):
                s = s[len(prefix):].strip()
                break
        # Снимаем парные кавычки по краям
        pairs = [("\"", "\""), ("'", "'"), ("“", "”"), ("„", "“"), ("«", "»")]
        for lq, rq in pairs:
            if s.startswith(lq) and s.endswith(rq) and len(s) >= 2:
                s = s[1:-1].strip()
                break
        # Нормализуем тире-разделитель и убираем лишние точки по краям
        s = s.strip(" .")
        s = s.replace(" — - ", " — ").replace(" - ", " — ")
        # Однострочный ответ
        return " ".join(s.split())

    def _update_stats(self, response_time: float, success: bool):
        """Обновляет статистику производительности."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        
        # Скользящее среднее времени ответа
        alpha = 0.1  # Фактор сглаживания
        if self.average_response_time == 0:
            self.average_response_time = response_time
        else:
            self.average_response_time = (1 - alpha) * self.average_response_time + alpha * response_time

    def get_performance_stats(self) -> Dict[str, Any]:
        """Возвращает статистику производительности."""
        success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'success_rate': f"{success_rate:.1f}%",
            'average_response_time': f"{self.average_response_time:.2f}s",
            'active_connections': len(self.session.connector._conns) if self.session else 0
        }

    async def close(self):
        """Закрытие соединений."""
        if self.session:
            await self.session.close()
        if self.openai_client:
            await self.openai_client.close()

# Глобальный экземпляр
high_performance_api = HighPerformanceAPI()

async def initialize_high_performance_api():
    """Инициализация высокопроизводительного API."""
    await high_performance_api.initialize()

async def get_optimized_translation_api(text: str, user_mode: int, user_id: int) -> APIResponse:
    """Получение оптимизированного перевода."""
    return await high_performance_api.translate_text_optimized(text, user_mode, user_id)

async def cleanup_api():
    """Очистка ресурсов API."""
    await high_performance_api.close()