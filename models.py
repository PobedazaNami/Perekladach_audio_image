import logging
from datetime import datetime, timedelta
from database import (
    add_user, user_exists, add_authorized_user, remove_authorized_user,
    is_authorized, add_admin, remove_admin, get_all_admins,
    update_input_chars, update_output_chars, get_all_users, get_bot_stats,
    create_user_table, get_cached_translation, cache_translation
)

# Настройка логирования
logger = logging.getLogger(__name__)

def initialize_database():
    """Инициализирует базу данных MongoDB"""
    try:
        create_user_table()
        logger.info("База данных MongoDB успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}", exc_info=True)
        raise

def get_user_stats(user_id):
    """Получает статистику конкретного пользователя"""
    try:
        from database import get_db_connection
        db = get_db_connection()
        
        user_stats = db.usage_stats.find_one({"telegram_id": user_id})
        if user_stats:
            return {
                "input_chars": user_stats.get("input_chars", 0),
                "output_chars": user_stats.get("output_chars", 0),
                "created_at": user_stats.get("created_at"),
                "updated_at": user_stats.get("updated_at")
            }
        else:
            return {
                "input_chars": 0,
                "output_chars": 0,
                "created_at": None,
                "updated_at": None
            }
    except Exception as e:
        logger.error(f"Ошибка при получении статистики пользователя {user_id}: {e}", exc_info=True)
        return {"input_chars": 0, "output_chars": 0, "created_at": None, "updated_at": None}

def log_translation_request(user_id, source_text, target_lang, source_lang="auto"):
    """Логирует запрос на перевод"""
    try:
        update_input_chars(user_id, len(source_text))
        
        from database import get_db_connection
        db = get_db_connection()
        
        log_doc = {
            "user_id": user_id,
            "source_text_length": len(source_text),
            "source_lang": source_lang,
            "target_lang": target_lang,
            "timestamp": datetime.utcnow(),
            "type": "translation_request"
        }
        
        db.translation_logs.insert_one(log_doc)
        logger.info(f"Запрос на перевод от пользователя {user_id} записан в лог")
        
    except Exception as e:
        logger.error(f"Ошибка при логировании запроса перевода: {e}", exc_info=True)

def log_translation_response(user_id, translated_text):
    """Логирует ответ перевода"""
    try:
        update_output_chars(user_id, len(translated_text))
        
        from database import get_db_connection
        db = get_db_connection()
        
        log_doc = {
            "user_id": user_id,
            "translated_text_length": len(translated_text),
            "timestamp": datetime.utcnow(),
            "type": "translation_response"
        }
        
        db.translation_logs.insert_one(log_doc)
        logger.info(f"Ответ перевода для пользователя {user_id} записан в лог")
        
    except Exception as e:
        logger.error(f"Ошибка при логировании ответа перевода: {e}", exc_info=True)

def get_translation_from_cache(text, source_lang, target_lang):
    """Получает перевод из кеша"""
    return get_cached_translation(text, source_lang, target_lang)

def save_translation_to_cache(text, source_lang, target_lang, translated_text):
    """Сохраняет перевод в кеш"""
    cache_translation(text, source_lang, target_lang, translated_text)

def get_database_info():
    """Получает информацию о базе данных"""
    try:
        from database import get_db_connection
        db = get_db_connection()
        
        info = {
            "database_name": db.name,
            "collections": db.list_collection_names(),
            "users_count": db.users.count_documents({}),
            "authorized_users_count": db.authorized_users.count_documents({}),
            "admins_count": db.admins.count_documents({}),
            "cache_entries_count": db.translations_cache.count_documents({})
        }
        
        return info
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о базе данных: {e}", exc_info=True)
        return None

def get_user_mode(user_id):
    """Получает режим пользователя"""
    try:
        from database import get_db_connection
        db = get_db_connection()
        
        user = db.users.find_one({"telegram_id": user_id})
        if user:
            return user.get("current_mode", 1)
        return 1
        
    except Exception as e:
        logger.error(f"Ошибка при получении режима пользователя {user_id}: {e}", exc_info=True)
        return 1

def set_user_mode(user_id, mode):
    """Устанавливает режим пользователя"""
    try:
        from database import get_db_connection
        db = get_db_connection()
        
        result = db.users.update_one(
            {"telegram_id": user_id},
            {"$set": {"current_mode": mode, "updated_at": datetime.utcnow()}},
            upsert=False
        )
        
        if result.matched_count > 0:
            logger.info(f"Режим пользователя {user_id} установлен на {mode}")
            return True
        else:
            logger.warning(f"Пользователь {user_id} не найден для установки режима")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при установке режима пользователя {user_id}: {e}", exc_info=True)
        return False