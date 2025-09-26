import logging
from datetime import datetime, timedelta
from pymongo.errors import DuplicateKeyError, PyMongoError
from config import get_mongodb_database, Config
import hashlib

logger = logging.getLogger(__name__)

def get_db_connection():
    """Возвращает объект базы данных MongoDB"""
    return get_mongodb_database()

# Функции для работы с пользователями
def add_user(user_id, username):
    """Добавляет или обновляет пользователя в MongoDB"""
    try:
        db = get_db_connection()
        user_doc = {
            "telegram_id": user_id,
            "username": username,
            "interface_language": "uk",  # Украинский по умолчанию
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Используем upsert для добавления или обновления
        result = db.users.update_one(
            {"telegram_id": user_id},
            {
                "$set": {
                    "username": username,
                    "updated_at": datetime.utcnow()
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        if result.upserted_id:
            logger.info(f"Новый пользователь {user_id} ({username}) добавлен в MongoDB")
        else:
            logger.info(f"Пользователь {user_id} ({username}) обновлен в MongoDB")
            
    except Exception as e:
        logger.error(f"Ошибка при добавлении/обновлении пользователя {user_id}: {e}", exc_info=True)
        raise

def user_exists(user_id):
    """Проверяет существование пользователя в MongoDB"""
    try:
        db = get_db_connection()
        user = db.users.find_one({"telegram_id": user_id})
        return user is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке существования пользователя {user_id}: {e}", exc_info=True)
        return False

# Функции для авторизованных пользователей
def add_authorized_user(user_id, approved_by_admin):
    """Добавляет пользователя в авторизованные"""
    try:
        db = get_db_connection()
        auth_doc = {
            "telegram_id": user_id,
            "date_authorized": datetime.utcnow(),
            "approved_by_admin": approved_by_admin
        }
        
        result = db.authorized_users.update_one(
            {"telegram_id": user_id},
            {
                "$set": auth_doc
            },
            upsert=True
        )
        
        logger.info(f"Пользователь {user_id} добавлен/обновлен в authorized_users")
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении авторизованного пользователя {user_id}: {e}", exc_info=True)
        raise

def remove_authorized_user(user_id):
    """Удаляет пользователя из авторизованных"""
    try:
        db = get_db_connection()
        result = db.authorized_users.delete_one({"telegram_id": user_id})
        
        if result.deleted_count > 0:
            logger.info(f"Пользователь {user_id} удален из authorized_users")
        else:
            logger.warning(f"Пользователь {user_id} не найден в authorized_users")
            
    except Exception as e:
        logger.error(f"Ошибка при удалении авторизованного пользователя {user_id}: {e}", exc_info=True)
        raise

def is_authorized(user_id):
    """Проверяет авторизацию пользователя"""
    try:
        db = get_db_connection()
        
        # Проверяем авторизованных пользователей
        if db.authorized_users.find_one({"telegram_id": user_id}):
            return True
            
        # Проверяем администраторов
        if db.admins.find_one({"telegram_id": user_id}):
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Ошибка при проверке авторизации пользователя {user_id}: {e}", exc_info=True)
        return False

# Функции для администраторов
def add_admin(user_id, role='admin'):
    """Добавляет администратора"""
    try:
        db = get_db_connection()
        
        # Добавляем в администраторы
        admin_doc = {
            "telegram_id": user_id,
            "role": role,
            "created_at": datetime.utcnow()
        }
        
        db.admins.update_one(
            {"telegram_id": user_id},
            {"$set": admin_doc},
            upsert=True
        )
        
        # Также добавляем в авторизованные пользователи
        add_authorized_user(user_id, user_id)  # Админ сам себя авторизует
        
        logger.info(f"Пользователь {user_id} добавлен как администратор с ролью {role}")
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении администратора {user_id}: {e}", exc_info=True)
        raise

def remove_admin(user_id):
    """Удаляет администратора"""
    try:
        db = get_db_connection()
        
        # Удаляем из администраторов
        admin_result = db.admins.delete_one({"telegram_id": user_id})
        
        # Также удаляем из авторизованных пользователей
        auth_result = db.authorized_users.delete_one({"telegram_id": user_id})
        
        logger.info(f"Пользователь {user_id} удален из администраторов и авторизованных пользователей")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении администратора {user_id}: {e}", exc_info=True)
        raise

def get_all_admins():
    """Получает список всех администраторов"""
    try:
        db = get_db_connection()
        admins = db.admins.find({}, {"telegram_id": 1})
        return [admin["telegram_id"] for admin in admins]
    except Exception as e:
        logger.error(f"Ошибка при получении списка администраторов: {e}", exc_info=True)
        return []

# Функции для статистики использования
def update_input_chars(user_id, count):
    """Обновляет количество входящих символов"""
    try:
        db = get_db_connection()
        
        db.usage_stats.update_one(
            {"telegram_id": user_id},
            {
                "$inc": {"input_chars": count},
                "$setOnInsert": {"created_at": datetime.utcnow()},
                "$set": {"updated_at": datetime.utcnow()}
            },
            upsert=True
        )
        
        logger.info(f"Обновлено количество входящих символов для пользователя {user_id} на {count}")
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении входящих символов для пользователя {user_id}: {e}", exc_info=True)

def update_output_chars(user_id, count):
    """Обновляет количество исходящих символов"""
    try:
        db = get_db_connection()
        
        db.usage_stats.update_one(
            {"telegram_id": user_id},
            {
                "$inc": {"output_chars": count},
                "$setOnInsert": {"created_at": datetime.utcnow()},
                "$set": {"updated_at": datetime.utcnow()}
            },
            upsert=True
        )
        
        logger.info(f"Обновлено количество исходящих символов для пользователя {user_id} на {count}")
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении исходящих символов для пользователя {user_id}: {e}", exc_info=True)

# Функции для получения статистики
def get_all_users():
    """Получает список всех авторизованных пользователей"""
    try:
        db = get_db_connection()
        users = db.authorized_users.find({}, {"telegram_id": 1})
        return [user["telegram_id"] for user in users]
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}", exc_info=True)
        return []

def get_bot_stats():
    """Получает статистику бота"""
    try:
        db = get_db_connection()
        
        stats = {}
        
        # Подсчет пользователей
        stats['Пользователи'] = db.users.count_documents({})
        stats['Авторизованные пользователи'] = db.authorized_users.count_documents({})
        stats['Администраторы'] = db.admins.count_documents({})
        
        # Подсчет символов
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_input": {"$sum": "$input_chars"},
                    "total_output": {"$sum": "$output_chars"}
                }
            }
        ]
        
        result = list(db.usage_stats.aggregate(pipeline))
        if result:
            stats['Всего входящих символов'] = result[0]['total_input'] or 0
            stats['Всего исходящих символов'] = result[0]['total_output'] or 0
        else:
            stats['Всего входящих символов'] = 0
            stats['Всего исходящих символов'] = 0
            
        return stats
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики бота: {e}", exc_info=True)
        return {}

def normalize_text_for_cache(text):
    """
    Нормализует текст для эффективного кэширования.
    Приводит 'привет', 'ПРИВЕТ', 'Привет' к одному виду.
    """
    if not text:
        return ""
    
    import re
    
    # Базовая очистка
    normalized = text.strip()
    
    # Убираем лишние пробелы
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Приводим к нижнему регистру
    normalized = normalized.lower()
    
    # Для коротких фраз убираем знаки пунктуации
    if len(normalized) <= 50:
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
    else:
        # Для длинных текстов убираем только концевые знаки
        normalized = re.sub(r'[.!?]+\s*$', '', normalized)
    
    return normalized

# Функции для кеша переводов
def get_cached_translation(text, source_lang="auto", target_lang="auto", cache_version: str | None = None):
    """Получает перевод из кеша с умной нормализацией.

    Если передан cache_version, сначала ищем по версионному ключу,
    затем (для совместимости) пробуем legacy-ключ без версии.
    """
    try:
        db = get_db_connection()
        
        # Нормализуем текст перед поиском
        normalized_text = normalize_text_for_cache(text)
        
        def _make_hash(prefix: str | None):
            if prefix:
                key = f"{prefix}:{normalized_text}_{source_lang}_{target_lang}"
            else:
                key = f"{normalized_text}_{source_lang}_{target_lang}"
            return hashlib.md5(key.encode()).hexdigest()

        cached = None
        if cache_version:
            v_hash = _make_hash(cache_version)
            cached = db.translations_cache.find_one({"source_text_hash": v_hash})
            if cached:
                logger.info(f"💾 Cache HIT(v{cache_version}) для: '{text}' -> '{normalized_text}'")
        if not cached:
            # Fallback на старый ключ
            legacy_hash = _make_hash(None)
            cached = db.translations_cache.find_one({"source_text_hash": legacy_hash})
        
        if cached:
            logger.info(f"💾 Cache HIT для: '{text}' -> '{normalized_text}'")
            return cached.get("translated_text")
        
        logger.debug(f"❌ Cache MISS для: '{text}' -> '{normalized_text}'")
            
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при получении кешированного перевода: {e}", exc_info=True)
        return None

def cache_translation(text, translated_text, source_lang="auto", target_lang="auto", cache_version: str | None = None):
    """Сохраняет перевод в кеш с умной нормализацией.

    При переданном cache_version хеш включает версию и поле cache_version
    сохраняется в документе.
    """
    try:
        db = get_db_connection()
        
        # Нормализуем исходный текст
        normalized_text = normalize_text_for_cache(text)
        
        if cache_version:
            hash_key = f"{cache_version}:{normalized_text}_{source_lang}_{target_lang}"
        else:
            hash_key = f"{normalized_text}_{source_lang}_{target_lang}"
        text_hash = hashlib.md5(hash_key.encode()).hexdigest()
        
        cache_doc = {
            "source_text_hash": text_hash,
            "source_text_original": text,  # Сохраняем оригинальный текст
            "source_text_normalized": normalized_text,  # И нормализованный
            "source_lang": source_lang,
            "target_lang": target_lang,
            "translated_text": translated_text,
            "cache_version": cache_version,
            "created_at": datetime.utcnow()
        }
        
        # Используем upsert для обновления или вставки
        result = db.translations_cache.update_one(
            {"source_text_hash": text_hash},
            {"$set": cache_doc},
            upsert=True
        )
        
        logger.info(f"💾 Cached: '{text}' -> '{normalized_text}' ({'updated' if result.matched_count > 0 else 'inserted'})")
        
        logger.info(f"Перевод сохранен в кеш с хешем {text_hash}")
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении перевода в кеш: {e}", exc_info=True)

# Legacy функции для обратной совместимости
def create_user_table():
    """Инициализирует коллекции MongoDB (заменяет создание таблиц MySQL)"""
    try:
        from config import initialize_mongodb_collections
        initialize_mongodb_collections()
        logger.info("MongoDB коллекции успешно инициализированы")
    except Exception as e:
        logger.error(f"Ошибка при инициализации MongoDB коллекций: {e}", exc_info=True)

def get_user_interface_language(user_id):
    """Получает язык интерфейса пользователя"""
    try:
        db = get_db_connection()
        user = db.users.find_one({"telegram_id": user_id})
        if user:
            return user.get("interface_language", "uk")  # Украинский по умолчанию
        return "uk"
        
    except Exception as e:
        logger.error(f"Ошибка при получении языка интерфейса пользователя {user_id}: {e}", exc_info=True)
        return "uk"

def set_user_interface_language(user_id, language):
    """Устанавливает язык интерфейса пользователя"""
    try:
        db = get_db_connection()
        result = db.users.update_one(
            {"telegram_id": user_id},
            {
                "$set": {
                    "interface_language": language,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        if result.modified_count > 0 or result.upserted_id:
            logger.info(f"Язык интерфейса пользователя {user_id} установлен на {language}")
            return True
        return False
        
    except Exception as e:
        logger.error(f"Ошибка при установке языка интерфейса пользователя {user_id}: {e}", exc_info=True)
        return False
        raise

# --- Maintenance utilities ---
def clear_database(preserve_admins: bool = True) -> dict:
    """Очищает данные в MongoDB. По умолчанию сохраняет администраторов.

    Возвращает словарь с количеством удалённых документов по коллекциям.
    """
    stats = {}
    try:
        db = get_db_connection()

        collections = [
            'translations_cache',
            'usage_stats',
            'authorized_users',
            'users',
            'admins',
        ]

        for name in collections:
            coll = getattr(db, name)
            if name == 'admins' and preserve_admins:
                # Пропускаем очистку админов
                stats[name] = 0
                continue
            res = coll.delete_many({})
            stats[name] = getattr(res, 'deleted_count', 0)

        # При необходимости восстановим админов из конфигурации
        if preserve_admins:
            try:
                from config import ADMIN_IDS
                restored = 0
                for admin_id in ADMIN_IDS:
                    try:
                        add_admin(admin_id)
                        restored += 1
                    except Exception:
                        pass
                stats['admins_restored'] = restored
            except Exception:
                stats['admins_restored'] = 0

        logger.info(f"База данных очищена: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Ошибка при очистке базы данных: {e}", exc_info=True)
        raise

# --- Saved words per user ---
def save_user_word(user_id: int, source_text: str, translated_text: str) -> bool:
    """Сохраняет слово/фразу пользователя в коллекцию saved_words (уникально по normalized)."""
    try:
        db = get_db_connection()
        normalized = normalize_text_for_cache(source_text)
        doc = {
            "telegram_id": user_id,
            "source_text_original": source_text,
            "source_text_normalized": normalized,
            "translated_text": translated_text,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        # upsert уникальной пары (telegram_id + normalized)
        result = db.saved_words.update_one(
            {"telegram_id": user_id, "source_text_normalized": normalized},
            {"$set": doc},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении слова: {e}", exc_info=True)
        return False

def list_user_words(user_id: int, limit: int = 50, offset: int = 0):
    """Возвращает список сохранённых слов пользователя."""
    try:
        db = get_db_connection()
        cursor = db.saved_words.find({"telegram_id": user_id}).sort("updated_at", -1).skip(offset).limit(limit)
        return list(cursor)
    except Exception as e:
        logger.error(f"Ошибка при получении сохранённых слов: {e}", exc_info=True)
        return []