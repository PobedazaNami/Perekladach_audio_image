
import os
import logging
import asyncio
import shutil
import functools
import time
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    KeyboardButton,
    ReplyKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from dotenv import load_dotenv
import openai
# from google.cloud import vision, speech
# from google.cloud.vision_v1 import types as vision_types
# from PIL import Image
# import io
from langdetect import detect, LangDetectException

# from pydub import AudioSegment

import redis.asyncio as redis

# Импорты оптимизированных модулей (только доступные функции)
from performance_cache import (
    initialize_performance_cache, 
    get_optimized_translation,
    cache_optimized_translation,
    performance_cache
)
from high_performance_api import (
    initialize_high_performance_api,
    high_performance_api
)
from smart_ux import (
    start_cleanup_task,
    smart_ux
)

# Предполагается, что эти модули существуют и функции в models.py синхронные
from models import (
    create_user_table,
    add_user,
    user_exists,
    update_input_chars,
    update_output_chars,
    add_admin,
    remove_admin,
    add_authorized_user,
    remove_authorized_user,
    get_all_admins,
    get_all_users,
    get_bot_stats,
    is_authorized,
    get_user_mode,
    set_user_mode,
)

# Импорт модулей для многоязычности
from database import get_user_interface_language, set_user_interface_language, save_user_word, list_user_words
from translations import get_text, TRANSLATIONS
from config import logger as config_logger

# Настройка логирования для оптимизации
logger = logging.getLogger(__name__)

# --- Начало конфигурации ---

load_dotenv()

# Настройки для режима 4 (Практика)
PRACTICE_MODEL = "gpt-4o-mini"
PRACTICE_TEMPERATURE = 0.2

# --- Закомментировано для режима только текстового перевода ---
# # Проверка ffmpeg
# ffmpeg_exe = shutil.which('ffmpeg')
# ffprobe_exe = shutil.which('ffprobe')
# 
# if not ffmpeg_exe:
#     config_logger.critical("ffmpeg не найден в PATH.")
#     raise FileNotFoundError("ffmpeg не найден в PATH.")
# if not ffprobe_exe:
#     config_logger.critical("ffprobe не найден в PATH.")
#     raise FileNotFoundError("ffprobe не найден в PATH.")
# 
# AudioSegment.converter = ffmpeg_exe
# AudioSegment.ffprobe = ffprobe_exe

# --- Переменные окружения и клиенты API ---

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")  # Закомментировано - не нужно для режима 1
REDIS_URL = os.getenv('REDIS_URL')

def check_environment():
    """Проверка наличия необходимых переменных окружения."""
    # Закомментировано для работы только с режимом 1 (текстовый перевод)
    # if not all([TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, GOOGLE_APPLICATION_CREDENTIALS]):
    #     config_logger.critical("Одна или несколько ключевых переменных окружения отсутствуют (TELEGRAM, OPENAI, GOOGLE).")
    #     return False
    # if not os.path.exists(GOOGLE_APPLICATION_CREDENTIALS):
    #     config_logger.critical("Файл с учетными данными Google не найден.")
    #     return False
    if not all([TELEGRAM_BOT_TOKEN, OPENAI_API_KEY]):
        config_logger.critical("Одна или несколько ключевых переменных окружения отсутствуют (TELEGRAM, OPENAI).")
        return False
    config_logger.info("Все переменные окружения найдены.")
    return True

# Настройка клиентов API
openai.api_key = OPENAI_API_KEY
# ИСПОЛЬЗУЕМ АСИНХРОННЫЕ КЛИЕНТЫ - закомментировано для работы только с режимом 1
# vision_client = vision.ImageAnnotatorAsyncClient()
# speech_client = speech.SpeechAsyncClient()
redis_client = redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None

# --- Глобальные переменные и константы ---

try:
    ADMIN_IDS_str = os.getenv("ADMIN_IDS", "")
    ADMIN_IDS = {int(admin_id.strip()) for admin_id in ADMIN_IDS_str.split(",") if admin_id.strip()}
    config_logger.info(f"ADMIN_IDS загружены: {ADMIN_IDS}")
except (ValueError, AttributeError):
    ADMIN_IDS = set()
    config_logger.error("Ошибка парсинга ADMIN_IDS. Убедитесь, что это числа, разделенные запятыми.")

# Локализуемая клавиатура главного меню
def get_user_lang(user_id: int) -> str:
    try:
        lang = get_user_interface_language(user_id)
        return lang or "uk"
    except Exception:
        return "uk"

def build_main_keyboard(language: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(get_text("switch_mode_button", language))],
            [KeyboardButton(get_text("language_button", language))],
            [KeyboardButton(get_text("my_words_button", language))],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def build_quick_actions_inline(language: str) -> InlineKeyboardMarkup:
    """Инлайн-меню быстрых действий: режим, язык, мои слова."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(get_text("switch_mode_button", language), callback_data="open_mode"),
                InlineKeyboardButton(get_text("language_button", language), callback_data="open_language"),
            ],
            [InlineKeyboardButton(get_text("my_words_button", language), callback_data="list_words")],
        ]
    )

processing_users = set()
processing_lock = asyncio.Lock()


# --- Декораторы ---

def log_execution_time(func):
    """Декоратор для логирования времени выполнения асинхронных функций."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        config_logger.debug(f"Начало выполнения: {func.__name__}")
        start_time = time.time()
        try:
            return await func(*args, **kwargs)
        finally:
            duration = time.time() - start_time
            config_logger.debug(f"Функция {func.__name__} завершена за {duration:.2f} сек.")
    return wrapper

def admin_only(func):
    """Декоратор для ограничения доступа к командам только для администраторов."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id in ADMIN_IDS:
            return await func(update, context, *args, **kwargs)
        else:
            await update.message.reply_text("У вас нет доступа к этой команде.")
            config_logger.warning(f"Пользователь {user_id} попытался использовать админ-команду: {func.__name__}")
    return wrapper


# --- Основная логика перевода ---

# Утилита: удалить сообщение через задержку (для скрытия технических сообщений)
async def _delete_message_later(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay_sec: float = 2.0):
    try:
        await asyncio.sleep(delay_sec)
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        # Игнорируем возможные ошибки удаления (например, уже удалено)
        pass

def get_openai_prompt(mode: int) -> dict:
    """Возвращает системный промпт, модель и температуру в зависимости от режима."""
    prompts = {
        1: 'Ти перекладацький двигун (DE⇄UK/RU). Якщо вхід українською або російською — переклади лише на німецьку. Якщо вхід німецькою — переклади лише на українську. Відповідь має містити тільки переклад без пояснень, без лапок, без списків і без уточнювальних запитань. Формат: лише переклад.',
        
        2: 'Ти перекладач для тексту з зображень (DE⇄UK/RU). UK/RU → DE; DE → UK. Поверни тільки переклад без пояснень і зайвих символів.',
        
        3: 'Ти перекладач для розпізнаного аудіо (DE⇄UK/RU). UK/RU → DE; DE → UK. У відповіді лише переклад без пояснень.',
        
        4: 'Ти — сучасний репетитор з німецької мови для україномовних студентів рівня A2-B1. Твоя мета — допомогти користувачам вивчати німецьку через інтерактивні вправи, пояснення граматики та практичні діалоги. Коли користувач надсилає "+", створи для нього практичну вправу з німецької мови з поясненнями українською. Завжди відповідай українською мовою з поясненнями німецьких конструкцій. Для будь-якого іншого тексту - поясни граматику і дай переклад з детальними поясненнями.'
    }
    
    system_prompt = prompts.get(mode, 'Переведи следующий текст.')
    model = "gpt-4o-mini"
    temperature = 0.2 if mode == 4 else 0.1

    return {"model": model, "temperature": temperature, "system_prompt": system_prompt}

async def stream_and_update_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_to_edit_id: int, stream):
    """
    Асинхронно обрабатывает стрим от OpenAI и обновляет сообщение в Telegram.
    Устойчив к удалению сообщения пользователем.
    """
    full_response = ""
    last_sent_text = ""
    last_update_time = time.time()
    message_is_deleted = False

    async for chunk in stream:
        if message_is_deleted:
            break

        content = chunk.choices[0].delta.get("content")
        if content:
            full_response += content

        if (time.time() - last_update_time > 1.5) and (full_response != last_sent_text):
            try:
                await context.bot.edit_message_text(
                    text=full_response + " ✍️",
                    chat_id=chat_id,
                    message_id=message_to_edit_id
                )
                last_sent_text = full_response
                last_update_time = time.time()
            except BadRequest as e:
                if "Message can't be edited" in e.message:
                    config_logger.warning("Сообщение для редактирования было удалено пользователем.")
                    message_is_deleted = True
                    break
                elif "Message is not modified" not in e.message:
                    config_logger.warning(f"Ошибка при обновлении сообщения: {e}")

    if not message_is_deleted and full_response != last_sent_text:
        try:
            await context.bot.edit_message_text(
                text=full_response,
                chat_id=chat_id,
                message_id=message_to_edit_id
            )
        except BadRequest as e:
            if "Message can't be edited" not in e.message:
                 config_logger.error(f"Ошибка при отправке финального сообщения: {e}")
    
    return full_response

@log_execution_time
async def translate_text_streaming(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Оптимизированная функция для перевода с многоуровневым кэшированием."""
    start_time = time.time()
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    logger.info(f"🚀 Processing translation for user {username} ({user_id})")
    
    try:
        # Получаем режим пользователя
        mode = get_user_mode(user_id)
        user_lang = get_user_lang(user_id)
        translation_context = high_performance_api.build_translation_context(
            text=text,
            user_mode=mode,
            interface_language=user_lang,
        )
        
        # Уведомляем пользователя о начале обработки с typing indicator
        await smart_ux.start_typing_indicator(update, context)
        
        # Пытаемся получить из оптимизированного кэша
        cached_result = await get_optimized_translation(
            text,
            mode,
            user_id,
            translation_context.source_lang,
            translation_context.target_lang,
        )
        if cached_result:
            # Добавляем кнопку сохранения слова
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(get_text("save_word_button", user_lang), callback_data="save_word")]])
            await update.message.reply_text(cached_result, reply_markup=kb)
            # Запоминаем последнюю пару для сохранения
            context.user_data['last_source_text'] = text
            context.user_data['last_translation'] = cached_result
            
            processing_time = time.time() - start_time
            logger.info(f"✅ Message processed in {processing_time:.2f}s for user {user_id}")
            return

        # Если не в кэше, делаем новый перевод
        # Не переоткрываем нижнее меню на каждое сообщение
        processing_notification = await update.message.reply_text("🕒 Обробка запиту...")
        # Получаем промпт конфигурацию
        # Prompt selection is centralized inside high_performance_api.
        
        # Используем оптимизированный API клиент
        response = await high_performance_api.translate_text_optimized(
            text=text,
            user_mode=mode,
            user_id=user_id,
            interface_language=user_lang,
            translation_context=translation_context
        )
        
        translated_text = response.content if response.success else None

        if translated_text:
            # Обновляем сообщение финальным переводом
            try:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(get_text("save_word_button", user_lang), callback_data="save_word")]])
                await context.bot.edit_message_text(
                    text=translated_text,
                    chat_id=user_id,
                    message_id=processing_notification.message_id,
                    reply_markup=kb,
                )
                # Запоминаем последнюю пару для сохранения
                context.user_data['last_source_text'] = text
                context.user_data['last_translation'] = translated_text
            except BadRequest as e:
                if "Message can't be edited" in str(e):
                    logger.warning(f"Message was deleted by user {user_id}, sending new message")
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton(get_text("save_word_button", user_lang), callback_data="save_word")]])
                    await update.message.reply_text(
                        translated_text,
                        reply_markup=kb
                    )
                    # Запоминаем последнюю пару для сохранения
                    context.user_data['last_source_text'] = text
                    context.user_data['last_translation'] = translated_text
                else:
                    logger.error(f"Error editing message: {e}")
                    raise e
            
            # Сохраняем в оптимизированный кэш
            await cache_optimized_translation(
                text,
                translated_text,
                mode,
                user_id,
                translation_context.source_lang,
                translation_context.target_lang,
            )
            
            # Обновляем статистику
            await asyncio.to_thread(update_input_chars, user_id, len(text))
            await asyncio.to_thread(update_output_chars, user_id, len(translated_text))

        processing_time = time.time() - start_time
        logger.info(f"✅ Message processed in {processing_time:.2f}s for user {user_id}")

    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

        processing_time = time.time() - start_time
        logger.error(f"❌ Failed to process in {processing_time:.2f}s for user {user_id}")
    finally:
        # Завершаем typing indicator, чтобы не висела анимация "пишет..."
        try:
            await smart_ux.stop_typing_indicator(user_id)
        except Exception:
            pass

async def handle_message_optimized(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Оптимизированный обработчик всех входящих сообщений."""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        user_lang = get_user_lang(user_id)
        
        # Проверяем авторизацию
        if not is_authorized(user_id):
            await update.message.reply_text('У вас нет доступа к боту. Ожидайте одобрения.')
            return
            
        # Обрабатываем нажатия кнопок главной клавиатуры (локализованных)
        if update.message.text:
            text_lower = update.message.text.strip().lower()
            switch_label = get_text("switch_mode_button", user_lang).lower()
            language_label = get_text("language_button", user_lang).lower()
            my_words_label = get_text("my_words_button", user_lang).lower()
            if text_lower in {"switch mode", switch_label}:
                await switch_mode(update, context)
                return
            if text_lower in {"/language", language_label}:
                await language_command(update, context)
                return
            if text_lower == my_words_label:
                # Показать сохранённые слова без команды
                words = await asyncio.to_thread(list_user_words, user_id, 50, 0)
                if not words:
                    await update.message.reply_text(get_text("no_words", user_lang))
                    return
                lines = [get_text("your_words_header", user_lang)]
                for w in words[:50]:
                    src = w.get("source_text_original") or w.get("source_text_normalized")
                    dst = w.get("translated_text", "")
                    lines.append(f"• {src} → {dst}")
                await update.message.reply_text("\n".join(lines))
                return

        # Обрабатываем текстовые сообщения
        if update.message.text:
            await translate_text_streaming(update, context, update.message.text)
        
        # Режимы 2 и 3 временно отключены для деплоя без Google Cloud
        # Обрабатываем голосовые сообщения (только режим 3)
        # elif update.message.voice and get_user_mode(user_id) == 3:
        #     await handle_audio(update, context)
            
        # Обрабатываем изображения (только режим 2)  
        # elif update.message.photo and get_user_mode(user_id) == 2:
        #     await handle_image(update, context)
            
        else:
            mode = get_user_mode(user_id)
            if mode == 2:
                await update.message.reply_text("🖼️ Режим обработки изображений временно недоступен. Используйте режим 1 для перевода текста.")
            elif mode == 3:
                await update.message.reply_text("🎤 Режим обработки аудио временно недоступен. Используйте режим 1 для перевода текста.")
            elif mode != 1:
                await update.message.reply_text("💬 Отправьте текст для перевода или переключитесь на режим 1.")
            
    except Exception as e:
        logger.error(f"❌ Error in message handler: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке сообщения.")


# --- Вспомогательные функции для обработки файлов (закомментированы) ---

# Закомментировано - режимы 2 и 3 временно отключены для деплоя без Google Cloud
# def _process_audio_sync(audio_bytes: bytearray) -> bytes:
#     """Синхронная функция для конвертации аудио."""
#     with io.BytesIO(audio_bytes) as audio_io:
#         audio_segment = AudioSegment.from_file(audio_io)
#         processed_segment = audio_segment.set_sample_width(2).set_frame_rate(16000).set_channels(1)
#         with io.BytesIO() as wav_io:
#             processed_segment.export(wav_io, format="wav")
#             return wav_io.getvalue()
# 
# def _process_image_sync(image_bytes: bytearray) -> bytes:
#     """Синхронная функция для оптимизации изображения."""
#     with Image.open(io.BytesIO(image_bytes)) as image:
#         image.thumbnail((1024, 1024))
#         with io.BytesIO() as optimized_image_io:
#             image.save(optimized_image_io, format='JPEG', quality=85)
#             return optimized_image_io.getvalue()


# --- Обработчики команд ---

@log_execution_time
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.full_name
    config_logger.info(f"Пользователь {user_id} ({username}) начал взаимодействие.")
    
    # Получаем язык интерфейса пользователя
    user_language = await asyncio.to_thread(get_user_interface_language, user_id)
    if not user_language:
        user_language = "uk"  # по умолчанию украинский
    
    if await asyncio.to_thread(user_exists, user_id):
        is_auth = await asyncio.to_thread(is_authorized, user_id)
        if is_auth:
            # Получаем текущий режим пользователя
            user_mode = await asyncio.to_thread(get_user_mode, user_id)
            mode_name_key = f"mode_{user_mode}_name"
            current_mode_text = get_text("current_mode", user_language, 
                                       mode_name=get_text(mode_name_key, user_language))
            
            welcome_message = "\n".join([
                get_text("welcome", user_language),
                current_mode_text,
            ])
            
            await update.message.reply_text(welcome_message, reply_markup=build_quick_actions_inline(user_language), parse_mode='Markdown')
        else:
            await update.message.reply_text("Ваш запрос на доступ еще на рассмотрении. Пожалуйста, ожидайте.")
        return

    await asyncio.to_thread(add_user, user_id, username)
    await update.message.reply_text("Ваш запрос на доступ к боту отправлен администратору. Вы получите уведомление после одобрения.")
    
    notification_text = f"Новый запрос на доступ от пользователя {username} (ID: {user_id})."
    keyboard = [[InlineKeyboardButton("Одобрить", callback_data=f"approve_{user_id}"), InlineKeyboardButton("Отклонить", callback_data=f"reject_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=notification_text, reply_markup=reply_markup)
        except Exception as e:
            config_logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

@log_execution_time
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    help_text = (
        "Доступные команды:\n"
        "/start - Начало взаимодействия\n"
        "/help - Показать это сообщение\n"
        "/language - Выбрать язык интерфейса\n"
        "/mode - Выбрать режим перевода\n\n"
        "Для перевода просто отправьте текст, фото или голосовое сообщение. "
        "Для смены режима работы используйте кнопку 'Switch Mode'."
    )
    if user_id in ADMIN_IDS:
        help_text += (
            "\n\n👑 *Команды администратора:*\n"
            "/addadmin `[user_id]` - Добавить администратора\n"
            "/removeadmin `[user_id]` - Удалить администратора\n"
            "/stats - Показать статистику бота\n"
            "/broadcast `[сообщение]` - Отправить сообщение всем\n"
            "/listadmins - Показать список администраторов"
        )
    await update.message.reply_text(help_text, reply_markup=build_quick_actions_inline(get_user_lang(update.effective_user.id)), parse_mode='Markdown')

@admin_only
@log_execution_time
async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(context.args[0])
        await asyncio.to_thread(add_admin, user_id)
        ADMIN_IDS.add(user_id)
        await update.message.reply_text(f"Пользователь {user_id} назначен администратором.")
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /addadmin <user_id>")

@admin_only
@log_execution_time
async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(context.args[0])
        await asyncio.to_thread(remove_admin, user_id)
        ADMIN_IDS.discard(user_id)
        await update.message.reply_text(f"Пользователь {user_id} удалён из администраторов.")
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /removeadmin <user_id>")

@admin_only
@log_execution_time
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = await asyncio.to_thread(get_bot_stats)
    await update.message.reply_text(f"📊 *Статистика бота:*\n{stats}", parse_mode='Markdown')

@admin_only
@log_execution_time
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = " ".join(context.args)
    if not message_text:
        await update.message.reply_text("Использование: /broadcast <текст>")
        return

    users = await asyncio.to_thread(get_all_users)
    sent_count, failed_count = 0, 0
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            sent_count += 1
            await asyncio.sleep(0.1)
        except Exception:
            failed_count += 1
    await update.message.reply_text(f"📢 Рассылка завершена.\nОтправлено: {sent_count}\nНе удалось: {failed_count}")

@admin_only
@log_execution_time
async def list_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins = await asyncio.to_thread(get_all_admins)
    await update.message.reply_text(f"Список администраторов:\n{', '.join(map(str, admins))}")

@log_execution_time
async def words_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает сохранённые слова пользователя."""
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    words = await asyncio.to_thread(list_user_words, user_id, 50, 0)
    if not words:
        await update.message.reply_text(get_text("no_words", lang))
        return
    lines = [get_text("your_words_header", lang)]
    for w in words[:50]:
        src = w.get("source_text_original") or w.get("source_text_normalized")
        dst = w.get("translated_text", "")
        lines.append(f"• {src} → {dst}")
    await update.message.reply_text("\n".join(lines))

@log_execution_time 
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для выбора языка интерфейса"""
    user_id = update.effective_user.id
    user_language = await asyncio.to_thread(get_user_interface_language, user_id)
    if not user_language:
        user_language = "uk"
    
    keyboard = [
        [InlineKeyboardButton(get_text("ukrainian_language", user_language), callback_data="lang_uk")],
        [InlineKeyboardButton(get_text("russian_language", user_language), callback_data="lang_ru")],
        [InlineKeyboardButton(get_text("german_language", user_language), callback_data="lang_de")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    sent = await update.message.reply_text(
        get_text("choose_language", user_language),
        reply_markup=reply_markup
    )
    asyncio.create_task(_delete_message_later(context, user_id, sent.message_id, 20))


# --- Обработчики сообщений ---

@log_execution_time
async def translate_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await asyncio.to_thread(is_authorized, user_id):
        await update.message.reply_text('У вас нет доступа к боту. Ожидайте одобрения.')
        return
        
    # Поддержка локализованной кнопки "Сменить режим"
    switch_label = get_text("switch_mode_button", get_user_lang(user_id)).lower()
    if update.message.text and update.message.text.lower() in {"switch mode", switch_label}:
        await switch_mode(update, context)
        return

    # Специальная обработка для режима практики (режим 4)
    user_mode = await asyncio.to_thread(get_user_mode, user_id)
    if user_mode == 4 and update.message.text.strip() == "+":
        practice_exercises = [
            "Переведите на немецкий: 'Добрый день, как дела?'",
            "Wie sagt man auf Ukrainisch: 'Ich möchte einen Kaffee bestellen'?",
            "Создайте предложение со словом 'arbeiten'",
            "Объясните разницу между 'der', 'die', 'das'"
        ]
        import random
        exercise = random.choice(practice_exercises)
        await update.message.reply_text(
            f"📚 **Практическое задание:**\n\n{exercise}\n\nОтправьте '+' для нового задания.",
            parse_mode='Markdown'
        )
        return

    async with processing_lock:
        if user_id in processing_users:
            await update.message.reply_text("⚠️ Пожалуйста, дождитесь завершения предыдущего запроса.")
            return
        processing_users.add(user_id)
    try:
        await translate_text_streaming(update, context, update.message.text)
    finally:
        async with processing_lock:
            processing_users.discard(user_id)

# Закомментировано - режимы 2 и 3 временно отключены для деплоя без Google Cloud
# @log_execution_time
# async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     if not await asyncio.to_thread(is_authorized, user_id) or await asyncio.to_thread(get_user_mode, user_id) != 2:
#         await update.message.reply_text("Обработка изображений доступна только в режиме 2.")
#         return
# 
#     async with processing_lock:
#         if user_id in processing_users:
#             await update.message.reply_text("⚠️ Обработка предыдущего запроса еще не завершена.")
#             return
#         processing_users.add(user_id)
#     
#     try:
#         file = await update.message.photo[-1].get_file()
#         image_bytes = await file.download_as_bytearray()
#         optimized_bytes = await asyncio.to_thread(_process_image_sync, image_bytes)
#         response = await vision_client.text_detection(image=vision_types.Image(content=optimized_bytes))
#         
#         if not (extracted_text := response.text_annotations[0].description.strip() if response.text_annotations else ""):
#             await update.message.reply_text("Не удалось распознать текст.")
#             return
#         
#         await translate_text_streaming(update, context, extracted_text)
#     finally:
#         async with processing_lock:
#             processing_users.discard(user_id)

# @log_execution_time
# async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     if not await asyncio.to_thread(is_authorized, user_id) or await asyncio.to_thread(get_user_mode, user_id) != 3:
#         await update.message.reply_text("Обработка аудио доступна только в режиме 3.")
#         return
#         
#     async with processing_lock:
#         if user_id in processing_users:
#             await update.message.reply_text("⚠️ Обработка предыдущего запроса еще не завершена.")
#             return
#         processing_users.add(user_id)
#         
#     try:
#         audio_file = update.message.voice or update.message.audio
#         file = await audio_file.get_file()
#         wav_bytes = await asyncio.to_thread(_process_audio_sync, await file.download_as_bytearray())
# 
#         config = speech.RecognitionConfig(
#             encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
#             sample_rate_hertz=16000,
#             language_code="de-DE",
#             alternative_language_codes=["uk-UA"],
#             enable_automatic_punctuation=True,
#         )
#         response = await speech_client.recognize(config=config, audio=speech.RecognitionAudio(content=wav_bytes))
#         
#         if not (transcript := response.results[0].alternatives[0].transcript if response.results else ""):
#             await update.message.reply_text("Не удалось распознать речь.")
#             return
#         
#         await update.message.reply_text(f"📝 Распознано: *{transcript}*", parse_mode=ParseMode.MARKDOWN_V2)
#         await translate_text_streaming(update, context, transcript)
#     finally:
#         async with processing_lock:
#             processing_users.discard(user_id)


# --- Обработчики кнопок и режимов ---

@log_execution_time
async def switch_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Получаем язык интерфейса пользователя
    user_language = await asyncio.to_thread(get_user_interface_language, user_id)
    if not user_language:
        user_language = "uk"

    keyboard = [
        [InlineKeyboardButton(get_text("mode_1_button", user_language), callback_data='mode_1')],
        [InlineKeyboardButton("📷 Режим 2 (временно недоступен)", callback_data='mode_unavailable')],
        [InlineKeyboardButton("🎤 Режим 3 (временно недоступен)", callback_data='mode_unavailable')],
        [InlineKeyboardButton(get_text("mode_4_button", user_language), callback_data='mode_4')],
    ]
    sent = await update.message.reply_text(
        get_text("choose_mode", user_language),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    # Удаляем вспомогательное сообщение через пару секунд
    asyncio.create_task(_delete_message_later(context, user_id, sent.message_id, 10))

@log_execution_time
async def set_user_mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    user_id = query.from_user.id
    mode = int(data.split('_')[1])
    
    # Получаем язык интерфейса пользователя
    user_language = await asyncio.to_thread(get_user_interface_language, user_id)
    if not user_language:
        user_language = "uk"
    
    # Блокируем недоступные режимы
    if mode == 2:
        await query.edit_message_text("⚠️ Режим обработки изображений временно недоступен. Используйте режим 1 для перевода текста.")
        return
    elif mode == 3:
        await query.edit_message_text("⚠️ Режим обработки аудио временно недоступен. Используйте режим 1 для перевода текста.")
        return
    
    await asyncio.to_thread(set_user_mode, user_id, mode)
    
    # Получаем текст описания режима на языке пользователя
    mode_description_key = f"mode_{mode}_description"
    mode_text = get_text(mode_description_key, user_language)
    
    mode_change_text = get_text("mode_changed", user_language, mode=str(mode))
    edited = await query.edit_message_text(mode_change_text)
    asyncio.create_task(_delete_message_later(context, query.message.chat_id, edited.message_id, 8))
    sent = await context.bot.send_message(
        chat_id=user_id,
        text=mode_text,
    )
    asyncio.create_task(_delete_message_later(context, user_id, sent.message_id, 30))

@log_execution_time
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    admin_id = query.from_user.id

    if data == "mode_unavailable":
        await query.edit_message_text("⚠️ Этот режим временно недоступен. Используйте режим 1 для перевода текста.")
        return
    elif data.startswith("mode_"):
        await set_user_mode_handler(update, context, data)
    elif data.startswith("lang_"):
        # Обработка смены языка интерфейса
        user_id = query.from_user.id
        language_code = data.split("_")[1]  # uk, ru, de
        
        # Сохраняем выбор языка в базе данных
        await asyncio.to_thread(set_user_interface_language, user_id, language_code)
        
        # Отправляем подтверждение на выбранном языке
        confirmation_text = get_text("language_changed", language_code)
        edited = await query.edit_message_text(text=confirmation_text)
        asyncio.create_task(_delete_message_later(context, query.message.chat_id, edited.message_id, 5))
        
        # Отправляем обновленное приветствие на новом языке
        user_mode = await asyncio.to_thread(get_user_mode, user_id)
        mode_name_key = f"mode_{user_mode}_name"
        current_mode_text = get_text("current_mode", language_code, 
                                   mode_name=get_text(mode_name_key, language_code))
        
        welcome_message = "\n".join([
            get_text("welcome", language_code),
            current_mode_text,
        ])
        
        welcome = await context.bot.send_message(
            chat_id=user_id, 
            text=welcome_message, 
            reply_markup=build_quick_actions_inline(language_code), 
            parse_mode='Markdown'
        )
        asyncio.create_task(_delete_message_later(context, user_id, welcome.message_id, 30))
    elif data.startswith("approve_"):
        user_id = int(data.split("_")[1])
        await asyncio.to_thread(add_authorized_user, user_id, admin_id)
        edited = await query.edit_message_text(text=f"✅ Пользователь {user_id} одобрен.")
        asyncio.create_task(_delete_message_later(context, query.message.chat_id, edited.message_id, 10))
        info = await context.bot.send_message(
            chat_id=user_id,
            text="Ваш доступ одобрен!",
        )
        asyncio.create_task(_delete_message_later(context, user_id, info.message_id, 30))
    elif data.startswith("reject_"):
        user_id = int(data.split("_")[1])
        await asyncio.to_thread(remove_authorized_user, user_id)
        edited = await query.edit_message_text(text=f"❌ Пользователь {user_id} отклонен.")
        asyncio.create_task(_delete_message_later(context, query.message.chat_id, edited.message_id, 10))
        info = await context.bot.send_message(chat_id=user_id, text="Ваш запрос на доступ отклонен.")
        asyncio.create_task(_delete_message_later(context, user_id, info.message_id, 30))
    elif data == "save_word":
        try:
            user_id = query.from_user.id
            src = context.user_data.get('last_source_text') or (query.message.text or "")
            dst = context.user_data.get('last_translation') or (query.message.text or "")
            ok = await asyncio.to_thread(save_user_word, user_id, src, dst)
            lang = get_user_lang(user_id)
            confirmation = get_text("word_saved", lang) if ok else get_text("word_save_failed", lang)
            # Короткое всплывающее подтверждение
            await query.answer(text=confirmation, show_alert=False)
            # Визуальная фиксация в самом сообщении: меняем кнопку на "✅ ..."
            try:
                saved_label = get_text("word_saved", lang)
                new_markup = InlineKeyboardMarkup([[InlineKeyboardButton(saved_label, callback_data="saved_word")]])
                await query.edit_message_reply_markup(reply_markup=new_markup)
            except Exception:
                # Если сообщение нельзя редактировать — просто игнорируем
                pass
        except Exception:
            await query.answer(text="Error", show_alert=False)
    elif data == "saved_word":
        # Ничего не делаем, просто подтверждаем, что уже сохранено
        try:
            lang = get_user_lang(query.from_user.id)
            await query.answer(text=get_text("word_saved", lang), show_alert=False)
        except Exception:
            pass
    elif data == "open_mode":
        user_id = query.from_user.id
        language = get_user_lang(user_id)
        keyboard = [
            [InlineKeyboardButton(get_text("mode_1_button", language), callback_data='mode_1')],
            [InlineKeyboardButton(get_text("mode_2_button", language), callback_data='mode_2')],
            [InlineKeyboardButton(get_text("mode_3_button", language), callback_data='mode_3')],
            [InlineKeyboardButton(get_text("mode_4_button", language), callback_data='mode_4')],
        ]
        sent = await context.bot.send_message(
            chat_id=user_id,
            text=get_text("choose_mode", language),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        asyncio.create_task(_delete_message_later(context, user_id, sent.message_id, 15))
    elif data == "open_language":
        user_id = query.from_user.id
        language = get_user_lang(user_id)
        keyboard = [
            [InlineKeyboardButton(get_text("ukrainian_language", language), callback_data="lang_uk")],
            [InlineKeyboardButton(get_text("russian_language", language), callback_data="lang_ru")],
            [InlineKeyboardButton(get_text("german_language", language), callback_data="lang_de")]
        ]
        sent = await context.bot.send_message(
            chat_id=user_id,
            text=get_text("choose_language", language),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        asyncio.create_task(_delete_message_later(context, user_id, sent.message_id, 15))
    elif data == "list_words":
        user_id = query.from_user.id
        lang = get_user_lang(user_id)
        try:
            words = await asyncio.to_thread(list_user_words, user_id, 50, 0)
            if not words:
                await context.bot.send_message(chat_id=user_id, text=get_text("no_words", lang))
            else:
                lines = [get_text("your_words_header", lang)]
                for w in words[:50]:
                    src = w.get("source_text_original") or w.get("source_text_normalized")
                    dst = w.get("translated_text", "")
                    lines.append(f"• {src} → {dst}")
                await context.bot.send_message(chat_id=user_id, text="\n".join(lines))
        except Exception:
            await context.bot.send_message(chat_id=user_id, text=get_text("word_save_failed", lang))


# --- Обработчик ошибок ---

@log_execution_time
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    config_logger.error(msg="Exception while handling an update:", exc_info=context.error)


# --- Запуск бота ---

async def main():
    """Основная асинхронная функция запуска бота."""
    logger.info("🚀 Starting optimized bot...")
    if not check_environment():
        return

    # Инициализация БД
    await asyncio.to_thread(create_user_table)
    
    # Инициализация оптимизаций
    logger.info("🚀 Initializing bot optimizations...")
    
    try:
        # Инициализация кэша
        await initialize_performance_cache()
        
        # Инициализация API
        await initialize_high_performance_api()
        
        # Запуск задачи очистки
        asyncio.create_task(start_cleanup_task())
        
        logger.info("✅ All optimizations initialized successfully!")
        
    except Exception as e:
        logger.error(f"❌ Optimization initialization failed: {e}")
        
    logger.info("✅ Bot optimizations initialized successfully!")
    
    if redis_client:
        try:
            await redis_client.ping()
            config_logger.info("Успешное подключение к Redis!")
        except redis.RedisError as e:
            config_logger.error(f"Не удалось подключиться к Redis: {e}")
            
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("mode", switch_mode))
    application.add_handler(CommandHandler("language", language_command))
    application.add_handler(CommandHandler("addadmin", add_admin_command))
    application.add_handler(CommandHandler("removeadmin", remove_admin_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("listadmins", list_admins_command))
    application.add_handler(CommandHandler("words", words_command))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_optimized))
    # Режимы 2 и 3 временно отключены для деплоя без Google Cloud
    # application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    # application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_error_handler(error_handler)

    config_logger.info("Бот инициализирован, запуск...")

    try:
        await application.initialize()
        
        # Устанавливаем команды меню бота
        bot_commands = [
            BotCommand("start", "Початок роботи / Start"),
            BotCommand("help", "Допомога / Help"), 
            BotCommand("mode", "Вибрати режим / Choose mode"),
            BotCommand("language", "Мова інтерфейсу / Interface language"),
            BotCommand("words", "Збережені слова / Saved words"),
        ]
        await application.bot.set_my_commands(bot_commands)
        config_logger.info("Команды меню установлены")
        
        await application.start()
        await application.updater.start_polling()
        await asyncio.Event().wait()
    finally:
        config_logger.info("Остановка бота...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        if redis_client:
            await redis_client.close()
        config_logger.info("Бот успешно остановлен.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        config_logger.info("Бот остановлен вручную (Ctrl+C).")
    except Exception as e:
        config_logger.critical(f"Критическая ошибка при запуске: {e}", exc_info=True)
