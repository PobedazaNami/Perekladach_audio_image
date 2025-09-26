"""
Модуль для предварительной обработки сообщений и улучшения UX.
Включает typing indicators, предобработку файлов, и умную приоритизацию.
"""
import asyncio
import logging
import time
from typing import Optional, Dict, Any, Callable, Tuple
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from dataclasses import dataclass
import hashlib
from pathlib import Path

# Настройка логирования
ux_logger = logging.getLogger('ux_performance')

@dataclass 
class ProcessingTask:
    """Задача для обработки с приоритетом."""
    user_id: int
    task_type: str
    priority: int
    created_at: float
    data: Any
    callback: Callable

class SmartUXManager:
    """Умный менеджер пользовательского опыта для максимально быстрого отклика."""
    
    def __init__(self):
        self.active_typing: Dict[int, asyncio.Task] = {}
        self.processing_queue = asyncio.PriorityQueue()
        self.user_contexts: Dict[int, Dict[str, Any]] = {}
        self.file_cache: Dict[str, Any] = {}
        
        # Статистика производительности
        self.response_times: Dict[str, float] = {}
        self.user_satisfaction_score = 0.0
        
    async def start_typing_indicator(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   estimated_time: float = 5.0) -> asyncio.Task:
        """Запускает умный typing indicator с оценкой времени."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Останавливаем предыдущий typing если есть
        if user_id in self.active_typing:
            self.active_typing[user_id].cancel()
        
        async def typing_loop():
            """Цикл отправки typing indicator."""
            try:
                # Адаптивная частота в зависимости от оценочного времени
                interval = min(4.0, max(1.0, estimated_time / 3))
                
                while True:
                    await context.bot.send_chat_action(
                        chat_id=chat_id, 
                        action=ChatAction.TYPING
                    )
                    await asyncio.sleep(interval)
                    
            except asyncio.CancelledError:
                ux_logger.debug(f"Typing indicator stopped for user {user_id}")
            except Exception as e:
                ux_logger.warning(f"Typing indicator error: {e}")
        
        task = asyncio.create_task(typing_loop())
        self.active_typing[user_id] = task
        return task

    async def stop_typing_indicator(self, user_id: int):
        """Останавливает typing indicator для пользователя."""
        if user_id in self.active_typing:
            self.active_typing[user_id].cancel()
            del self.active_typing[user_id]

    async def preprocess_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        """Предварительная обработка сообщения для оптимизации."""
        user_id = update.effective_user.id
        start_time = time.time()
        
        result = {
            'user_id': user_id,
            'message_type': None,
            'estimated_processing_time': 1.0,
            'priority': 1,
            'preprocessing_data': {}
        }
        
        try:
            # Определяем тип сообщения и оценочное время обработки
            if update.message:
                msg = update.message
                
                if msg.text:
                    result['message_type'] = 'text'
                    result['estimated_processing_time'] = self._estimate_text_processing_time(msg.text)
                    result['preprocessing_data'] = {
                        'text_length': len(msg.text),
                        'language_detected': await self._quick_language_detect(msg.text),
                        'text_complexity': self._analyze_text_complexity(msg.text)
                    }
                    
                elif msg.voice:
                    result['message_type'] = 'voice'
                    result['estimated_processing_time'] = min(msg.voice.duration * 2 + 3, 30)
                    result['preprocessing_data'] = {
                        'duration': msg.voice.duration,
                        'file_size': msg.voice.file_size,
                        'mime_type': msg.voice.mime_type
                    }
                    
                elif msg.photo:
                    result['message_type'] = 'photo'
                    result['estimated_processing_time'] = 8.0
                    photo = msg.photo[-1]  # Берем самое высокое разрешение
                    result['preprocessing_data'] = {
                        'width': photo.width,
                        'height': photo.height,
                        'file_size': photo.file_size
                    }
                    
                elif msg.document:
                    result['message_type'] = 'document'
                    result['estimated_processing_time'] = 10.0
                    result['preprocessing_data'] = {
                        'file_name': msg.document.file_name,
                        'file_size': msg.document.file_size,
                        'mime_type': msg.document.mime_type
                    }
            
            # Определяем приоритет на основе истории пользователя
            result['priority'] = self._calculate_user_priority(user_id, result['message_type'])
            
            # Сохраняем контекст пользователя
            self._update_user_context(user_id, result)
            
            processing_time = time.time() - start_time
            ux_logger.debug(f"Preprocessing completed in {processing_time:.3f}s for user {user_id}")
            
        except Exception as e:
            ux_logger.error(f"Preprocessing error: {e}")
            result['estimated_processing_time'] = 10.0  # Fallback
            
        return result

    async def smart_file_download(self, file_id: str, context: ContextTypes.DEFAULT_TYPE) -> Tuple[Optional[str], Dict[str, Any]]:
        """Умная загрузка файлов с кэшированием и оптимизацией."""
        file_hash = hashlib.md5(file_id.encode()).hexdigest()
        
        # Проверяем кэш файлов
        if file_hash in self.file_cache:
            cache_entry = self.file_cache[file_hash]
            if time.time() - cache_entry['cached_at'] < 3600:  # Кэш на 1 час
                ux_logger.debug(f"📁 File cache HIT: {file_id}")
                return cache_entry['file_path'], cache_entry['metadata']
        
        try:
            start_time = time.time()
            
            # Получаем информацию о файле
            file = await context.bot.get_file(file_id)
            
            # Генерируем уникальный путь
            file_extension = Path(file.file_path).suffix
            local_filename = f"temp_{file_hash}{file_extension}"
            local_path = f"/tmp/{local_filename}"
            
            # Загружаем файл
            await file.download_to_drive(local_path)
            
            download_time = time.time() - start_time
            metadata = {
                'original_path': file.file_path,
                'local_path': local_path,
                'file_size': file.file_size,
                'download_time': download_time
            }
            
            # Кэшируем информацию о файле
            self.file_cache[file_hash] = {
                'file_path': local_path,
                'metadata': metadata,
                'cached_at': time.time()
            }
            
            ux_logger.info(f"📥 File downloaded: {download_time:.2f}s, {file.file_size} bytes")
            return local_path, metadata
            
        except Exception as e:
            ux_logger.error(f"File download error: {e}")
            return None, {}

    def _estimate_text_processing_time(self, text: str) -> float:
        """Оценивает время обработки текста."""
        base_time = 1.5
        length_factor = len(text) / 1000 * 0.5  # +0.5 сек на каждую 1000 символов
        return min(base_time + length_factor, 15.0)

    async def _quick_language_detect(self, text: str) -> str:
        """Быстрое определение языка без внешних библиотек."""
        # Упрощенная детекция по характерным символам
        if any(char in text for char in 'ёъэюяйцукенгшщзхъфывапролджэячсмитьбю'):
            return 'ru'
        elif any(char in text for char in 'їієґ'):
            return 'uk'
        elif any(char in text for char in 'äöüß'):
            return 'de'
        else:
            return 'unknown'

    def _analyze_text_complexity(self, text: str) -> str:
        """Анализирует сложность текста."""
        if len(text) < 50:
            return 'simple'
        elif len(text) < 500:
            return 'medium'
        else:
            return 'complex'

    def _calculate_user_priority(self, user_id: int, message_type: str) -> int:
        """Вычисляет приоритет пользователя."""
        # Базовый приоритет
        priority = 1
        
        # Учитываем историю пользователя
        if user_id in self.user_contexts:
            context = self.user_contexts[user_id]
            
            # Повышаем приоритет для быстрых пользователей
            avg_response = context.get('average_response_time', 5.0)
            if avg_response < 2.0:
                priority += 1
                
            # Понижаем приоритет для тяжелых типов сообщений
            if message_type in ['voice', 'document']:
                priority -= 1
                
        return max(1, priority)

    def _update_user_context(self, user_id: int, processing_info: Dict[str, Any]):
        """Обновляет контекст пользователя."""
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = {
                'total_messages': 0,
                'average_response_time': 5.0,
                'preferred_types': {},
                'last_activity': time.time()
            }
        
        context = self.user_contexts[user_id]
        context['total_messages'] += 1
        context['last_activity'] = time.time()
        
        # Обновляем статистику типов сообщений
        msg_type = processing_info['message_type']
        if msg_type:
            context['preferred_types'][msg_type] = context['preferred_types'].get(msg_type, 0) + 1

    async def cleanup_old_files(self):
        """Очистка старых временных файлов."""
        try:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self.file_cache.items():
                if current_time - entry['cached_at'] > 3600:  # 1 час
                    expired_keys.append(key)
                    
                    # Удаляем файл с диска
                    try:
                        import os
                        if os.path.exists(entry['file_path']):
                            os.remove(entry['file_path'])
                    except Exception as e:
                        ux_logger.warning(f"File cleanup error: {e}")
            
            # Удаляем из кэша
            for key in expired_keys:
                del self.file_cache[key]
                
            if expired_keys:
                ux_logger.info(f"🧹 Cleaned up {len(expired_keys)} old files")
                
        except Exception as e:
            ux_logger.error(f"Cleanup error: {e}")

    def get_ux_stats(self) -> Dict[str, Any]:
        """Возвращает статистику UX."""
        active_typing_count = len(self.active_typing)
        cached_files_count = len(self.file_cache)
        
        return {
            'active_typing_indicators': active_typing_count,
            'cached_files': cached_files_count,
            'user_contexts': len(self.user_contexts),
            'user_satisfaction_score': f"{self.user_satisfaction_score:.1f}/10"
        }

# Глобальный экземпляр
smart_ux = SmartUXManager()

async def start_smart_typing(update: Update, context: ContextTypes.DEFAULT_TYPE, estimated_time: float = 5.0):
    """Запуск умного typing indicator."""
    return await smart_ux.start_typing_indicator(update, context, estimated_time)

async def stop_smart_typing(user_id: int):
    """Остановка typing indicator."""
    await smart_ux.stop_typing_indicator(user_id)

async def smart_preprocess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    """Умная предобработка сообщения."""
    return await smart_ux.preprocess_message(update, context)

async def smart_download(file_id: str, context: ContextTypes.DEFAULT_TYPE):
    """Умная загрузка файлов."""
    return await smart_ux.smart_file_download(file_id, context)

# Периодическая очистка
async def start_cleanup_task():
    """Запуск задачи периодической очистки."""
    while True:
        await asyncio.sleep(1800)  # Каждые 30 минут
        await smart_ux.cleanup_old_files()