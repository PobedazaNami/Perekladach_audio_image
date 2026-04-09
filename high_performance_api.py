"""
High-performance helpers for OpenAI-backed translations.
"""

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import aiohttp
import openai
from langdetect import DetectorFactory, LangDetectException, detect
from openai import AsyncOpenAI

from config import Config

DetectorFactory.seed = 0

api_logger = logging.getLogger("api_performance")


@dataclass
class APIResponse:
    success: bool
    content: str = ""
    error: str = ""
    response_time: float = 0.0
    tokens_used: int = 0


@dataclass
class TranslationContext:
    source_lang: str
    target_lang: str
    interface_language: str
    model: str
    fallback_model: Optional[str]
    system_prompt: str
    temperature: float
    max_tokens: int


class HighPerformanceAPI:
    def __init__(self):
        self.openai_client: Optional[AsyncOpenAI] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_semaphore = asyncio.Semaphore(10)
        self.retry_delays = [0.1, 0.3, 0.8, 2.0]

        self.translation_model = os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-4o")
        self.translation_fallback_model = os.getenv(
            "OPENAI_TRANSLATION_FALLBACK_MODEL", "gpt-4o-mini"
        )
        self.practice_model = os.getenv("OPENAI_PRACTICE_MODEL", "gpt-4o-mini")

        self.total_requests = 0
        self.successful_requests = 0
        self.average_response_time = 0.0

    async def initialize(self):
        try:
            self.openai_client = AsyncOpenAI(
                api_key=Config.OPENAI_API_KEY,
                timeout=30.0,
                max_retries=3,
            )

            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=20,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=30,
            )

            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={"User-Agent": "TelegramBot/1.0"},
            )

            api_logger.info("High-performance API clients initialized")
        except Exception as exc:
            api_logger.error("API initialization failed: %s", exc)
            raise

    def build_translation_context(
        self,
        text: str,
        user_mode: int,
        interface_language: str = "uk",
    ) -> TranslationContext:
        interface_language = self._normalize_interface_language(interface_language)
        max_tokens = self._estimate_max_tokens(text)

        if user_mode == 4:
            target_lang = interface_language if interface_language in {"uk", "ru"} else "uk"
            return TranslationContext(
                source_lang=self._detect_language(text),
                target_lang=target_lang,
                interface_language=interface_language,
                model=self.practice_model,
                fallback_model=None,
                system_prompt=self._build_practice_prompt(target_lang),
                temperature=0.2,
                max_tokens=max_tokens,
            )

        source_lang = self._detect_language(text)
        target_lang = self._resolve_target_language(source_lang, interface_language)

        return TranslationContext(
            source_lang=source_lang,
            target_lang=target_lang,
            interface_language=interface_language,
            model=self.translation_model,
            fallback_model=self.translation_fallback_model,
            system_prompt=self._build_translation_prompt(source_lang, target_lang),
            temperature=0.0,
            max_tokens=max_tokens,
        )

    async def translate_text_optimized(
        self,
        text: str,
        user_mode: int,
        user_id: int,
        interface_language: str = "uk",
        translation_context: Optional[TranslationContext] = None,
    ) -> APIResponse:
        start_time = time.time()
        context = translation_context or self.build_translation_context(
            text=text,
            user_mode=user_mode,
            interface_language=interface_language,
        )

        async with self.request_semaphore:
            for attempt, delay in enumerate(self.retry_delays):
                try:
                    if attempt > 0:
                        await asyncio.sleep(delay)
                        api_logger.info("Retry attempt %s for user %s", attempt, user_id)

                    response = await self._create_completion(text=text, context=context)
                    raw = response.choices[0].message.content or ""
                    translation = self._postprocess_translation(raw)
                    response_time = time.time() - start_time
                    tokens_used = response.usage.total_tokens if response.usage else 0

                    self._update_stats(response_time, True)
                    api_logger.info(
                        "Translation success user=%s route=%s->%s model=%s time=%.2fs tokens=%s",
                        user_id,
                        context.source_lang,
                        context.target_lang,
                        getattr(response, "model", context.model),
                        response_time,
                        tokens_used,
                    )

                    return APIResponse(
                        success=True,
                        content=translation,
                        response_time=response_time,
                        tokens_used=tokens_used,
                    )
                except openai.RateLimitError:
                    api_logger.warning("Rate limit hit, waiting %.1fs", delay * 2)
                    await asyncio.sleep(delay * 2)
                    continue
                except openai.APITimeoutError:
                    if attempt < len(self.retry_delays) - 1:
                        api_logger.warning("Timeout, retrying in %.1fs", delay)
                        continue
                    self._update_stats(time.time() - start_time, False)
                    return APIResponse(success=False, error="Timeout after retries")
                except Exception as exc:
                    if attempt < len(self.retry_delays) - 1:
                        api_logger.warning("Error: %s, retrying in %.1fs", exc, delay)
                        continue
                    self._update_stats(time.time() - start_time, False)
                    return APIResponse(success=False, error=str(exc))

            self._update_stats(time.time() - start_time, False)
            return APIResponse(success=False, error="All retry attempts failed")

    async def batch_translate(
        self,
        texts: List[str],
        user_mode: int,
        user_id: int,
        interface_language: str = "uk",
    ) -> List[APIResponse]:
        api_logger.info("Batch translating %s texts for user %s", len(texts), user_id)
        tasks = [
            self.translate_text_optimized(
                text,
                user_mode,
                user_id,
                interface_language=interface_language,
            )
            for text in texts
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for index, result in enumerate(results):
            if isinstance(result, Exception):
                api_logger.error("Batch item %s failed: %s", index, result)
                processed_results.append(APIResponse(success=False, error=str(result)))
            else:
                processed_results.append(result)

        return processed_results

    async def _create_completion(self, text: str, context: TranslationContext):
        if not self.openai_client:
            raise RuntimeError("OpenAI client is not initialized")

        candidate_models = [context.model]
        if context.fallback_model and context.fallback_model not in candidate_models:
            candidate_models.append(context.fallback_model)

        last_error: Optional[Exception] = None
        for model_name in candidate_models:
            try:
                return await self.openai_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": context.system_prompt},
                        {"role": "user", "content": text},
                    ],
                    max_tokens=context.max_tokens,
                    temperature=context.temperature,
                    timeout=25.0,
                )
            except (openai.BadRequestError, openai.NotFoundError) as exc:
                last_error = exc
                api_logger.warning("Model %s failed, trying fallback: %s", model_name, exc)
                continue

        if last_error:
            raise last_error
        raise RuntimeError("No model candidates available")

    def _normalize_interface_language(self, language: str) -> str:
        language = (language or "uk").strip().lower()
        return language if language in {"uk", "ru", "de"} else "uk"

    def _detect_language(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return "unknown"

        heuristic = self._detect_language_heuristic(text)
        try:
            detected = detect(text)
        except LangDetectException:
            detected = "unknown"

        if detected.startswith("uk"):
            return "uk"
        if detected.startswith("ru"):
            return "ru"
        if detected.startswith("de"):
            return "de"
        if heuristic != "unknown":
            return heuristic
        return "unknown"

    def _detect_language_heuristic(self, text: str) -> str:
        if re.search(r"[іїєґІЇЄҐ]", text):
            return "uk"
        if re.search(r"[ёъыэЁЪЫЭ]", text):
            return "ru"
        if re.search(r"[а-яА-Я]", text):
            return "ru"
        if re.search(r"[A-Za-zÄÖÜäöüß]", text) and not re.search(r"[А-Яа-яІіЇїЄєҐґЁё]", text):
            return "de"
        return "unknown"

    def _resolve_target_language(self, source_lang: str, interface_language: str) -> str:
        if source_lang == "de":
            return interface_language if interface_language in {"uk", "ru"} else "uk"
        if source_lang in {"uk", "ru"}:
            return "de"
        if interface_language == "de":
            return "uk"
        return "de"

    def _build_translation_prompt(self, source_lang: str, target_lang: str) -> str:
        source_name = self._language_name(source_lang)
        target_name = self._language_name(target_lang)
        return (
            f"You are a professional translator from {source_name} to {target_name}.\n"
            "Translate the user's message faithfully and completely.\n"
            "- Keep meaning, tone, politeness, tense, modality, and uncertainty.\n"
            "- Do not summarize, simplify, explain, or answer the message.\n"
            "- Preserve line breaks, bullets, numbering, punctuation, and emoji when possible.\n"
            "- Keep names, brands, URLs, numbers, codes, and addresses unchanged unless translation is required.\n"
            "- If the input is a single word or short phrase, translate it directly.\n"
            "- Do not switch into dictionary mode.\n"
            "- Do not add articles, glosses, examples, or notes that are not in the source.\n"
            "- Return only the translation."
        )

    def _build_practice_prompt(self, target_lang: str) -> str:
        target_name = self._language_name(target_lang)
        return (
            "You are a German tutor for A2-B1 learners.\n"
            f"Always explain in {target_name}.\n"
            "If the user sends '+', create one short practical German exercise with a compact explanation.\n"
            "For any other message, explain the German, correct mistakes if needed, and provide a faithful translation.\n"
            "Keep the answer concise but useful."
        )

    def _language_name(self, language: str) -> str:
        names = {
            "uk": "Ukrainian",
            "ru": "Russian",
            "de": "German",
            "unknown": "the detected source language",
        }
        return names.get(language, language)

    def _estimate_max_tokens(self, text: str) -> int:
        estimated = len(text or "") // 2 + 256
        return max(256, min(2048, estimated))

    def _postprocess_translation(self, text: str) -> str:
        result = (text or "").strip()
        lower = result.lower()
        for prefix in ("translation:", "translate:", "übersetzung:", "перевод:", "переклад:"):
            if lower.startswith(prefix):
                result = result[len(prefix) :].strip()
                break

        quote_pairs = [('"', '"'), ("'", "'"), ("“", "”"), ("„", "“"), ("«", "»")]
        for left, right in quote_pairs:
            if result.startswith(left) and result.endswith(right) and len(result) >= 2:
                result = result[1:-1].strip()
                break

        cleaned_lines: List[str] = []
        blank_streak = False
        for line in result.splitlines():
            normalized_line = re.sub(r"[ \t]+", " ", line).strip()
            if not normalized_line:
                if not blank_streak and cleaned_lines:
                    cleaned_lines.append("")
                blank_streak = True
                continue
            cleaned_lines.append(normalized_line)
            blank_streak = False

        if cleaned_lines:
            return "\n".join(cleaned_lines).strip()
        return result

    def _update_stats(self, response_time: float, success: bool):
        self.total_requests += 1
        if success:
            self.successful_requests += 1

        alpha = 0.1
        if self.average_response_time == 0:
            self.average_response_time = response_time
        else:
            self.average_response_time = (
                (1 - alpha) * self.average_response_time + alpha * response_time
            )

    def get_performance_stats(self) -> Dict[str, Any]:
        success_rate = (
            self.successful_requests / self.total_requests * 100
            if self.total_requests > 0
            else 0
        )
        active_connections = 0
        if self.session and self.session.connector:
            active_connections = len(self.session.connector._conns)

        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "success_rate": f"{success_rate:.1f}%",
            "average_response_time": f"{self.average_response_time:.2f}s",
            "active_connections": active_connections,
        }

    async def close(self):
        if self.session:
            await self.session.close()
        if self.openai_client:
            await self.openai_client.close()


high_performance_api = HighPerformanceAPI()


async def initialize_high_performance_api():
    await high_performance_api.initialize()


async def get_optimized_translation_api(
    text: str,
    user_mode: int,
    user_id: int,
    interface_language: str = "uk",
) -> APIResponse:
    return await high_performance_api.translate_text_optimized(
        text=text,
        user_mode=user_mode,
        user_id=user_id,
        interface_language=interface_language,
    )


async def cleanup_api():
    await high_performance_api.close()
