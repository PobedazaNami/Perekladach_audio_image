
import os
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
# import pymysql  # Временно отключен для режима только текстового перевода

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

class Config:
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # MongoDB Atlas Configuration
    MONGODB_URI = os.getenv("MONGODB_URI")
    MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "translation_bot")
    CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))
    
    # Redis Configuration
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Legacy MySQL Configuration (для совместимости)
    DATABASE_TYPE = os.getenv("DATABASE_TYPE", "mongodb")  # По умолчанию MongoDB
    DATABASE_HOST = os.getenv("DATABASE_HOST")
    DATABASE_PORT = os.getenv("DATABASE_PORT")
    DATABASE_NAME = os.getenv("DATABASE_NAME")
    DATABASE_USER = os.getenv("DATABASE_USER")
    DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
    
    # Дополнительное логирование для отладки
    if TELEGRAM_BOT_TOKEN:
        logger.info("TELEGRAM_BOT_TOKEN успешно загружен.")
    else:
        logger.critical("TELEGRAM_BOT_TOKEN не установлен! Установите токен в переменных окружения.")
        raise ValueError("TELEGRAM_BOT_TOKEN не может быть пустым")
    
    if OPENAI_API_KEY:
        logger.info("OPENAI_API_KEY успешно загружен.")
    else:
        logger.critical("OPENAI_API_KEY не установлен! Установите ключ в переменных окружения.")
        raise ValueError("OPENAI_API_KEY не может быть пустым")
    
    if MONGODB_URI:
        logger.info("MongoDB URI успешно загружен.")
    else:
        logger.critical("MONGODB_URI не установлен! Установите URI MongoDB в переменных окружения.")
        raise ValueError("MONGODB_URI не может быть пустым")

# Явное прописание ADMIN_IDS
ADMIN_IDS = [662790795]

if ADMIN_IDS:
    logger.info(f"ADMIN_IDS успешно установлены: {ADMIN_IDS}")
else:
    logger.warning("ADMIN_IDS пусты. Уведомления администраторам не будут отправлены.")

# MongoDB Connection
_mongodb_client = None
_mongodb_db = None

def get_mongodb_client():
    """Возвращает клиент MongoDB с singleton паттерном"""
    global _mongodb_client
    if _mongodb_client is None:
        try:
            _mongodb_client = MongoClient(
                Config.MONGODB_URI,
                serverSelectionTimeoutMS=5000,  # 5 секунд таймаут
                maxPoolSize=50,  # максимальное количество соединений в пуле
                minPoolSize=10,  # минимальное количество соединений в пуле
            )
            # Проверяем соединение
            _mongodb_client.admin.command('ping')
            logger.info("Успешное подключение к MongoDB Atlas")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.critical(f"Не удалось подключиться к MongoDB Atlas: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.critical(f"Неожиданная ошибка при подключении к MongoDB: {e}", exc_info=True)
            raise
    return _mongodb_client

def get_mongodb_database():
    """Возвращает объект базы данных MongoDB"""
    global _mongodb_db
    if _mongodb_db is None:
        client = get_mongodb_client()
        _mongodb_db = client[Config.MONGODB_DATABASE]
        logger.info(f"Подключение к базе данных MongoDB: {Config.MONGODB_DATABASE}")
    return _mongodb_db

def close_mongodb_connection():
    """Закрывает соединение с MongoDB"""
    global _mongodb_client, _mongodb_db
    if _mongodb_client:
        _mongodb_client.close()
        _mongodb_client = None
        _mongodb_db = None
        logger.info("Соединение с MongoDB закрыто")

# Legacy MySQL support для обратной совместимости
DB_HOST = os.getenv('DB_HOST', 'ke490456.mysql.tools')
DB_USER = os.getenv('DB_USER', 'ke490456_dolmether')
DB_PASSWORD = os.getenv('DB_PASSWORD', 't5@+HyrA98')
DB_NAME = os.getenv('DB_NAME', 'ke490456_dolmether')
DB_CHARSET = os.getenv('DB_CHARSET', 'utf8mb4')

# Временно отключено для режима только текстового перевода
# def get_db_connection():
#     """Возвращает новое соединение с базой данных (legacy MySQL)."""
#     try:
#         connection = pymysql.connect(
#             host=DB_HOST,
#             user=DB_USER,
#             password=DB_PASSWORD,
#             db=DB_NAME,
#             charset=DB_CHARSET,
#             cursorclass=pymysql.cursors.DictCursor
#         )
#         return connection
#     except pymysql.MySQLError as e:
#         logger.critical(f"Не удалось подключиться к MySQL базе данных: {e}", exc_info=True)
#         raise

# Функция для инициализации MongoDB коллекций
def initialize_mongodb_collections():
    """Создает необходимые коллекции и индексы в MongoDB"""
    try:
        db = get_mongodb_database()
        
        # Коллекция пользователей
        users_collection = db.users
        users_collection.create_index("telegram_id", unique=True)
        logger.info("Коллекция 'users' создана/проверена")
        
        # Коллекция авторизованных пользователей  
        authorized_users_collection = db.authorized_users
        authorized_users_collection.create_index("telegram_id", unique=True)
        logger.info("Коллекция 'authorized_users' создана/проверена")
        
        # Коллекция администраторов
        admins_collection = db.admins
        admins_collection.create_index("telegram_id", unique=True)
        logger.info("Коллекция 'admins' создана/проверена")
        
        # Коллекция статистики использования
        usage_stats_collection = db.usage_stats
        usage_stats_collection.create_index("telegram_id", unique=True)
        logger.info("Коллекция 'usage_stats' создана/проверена")
        
        # Коллекция для кеша переводов
        translations_cache_collection = db.translations_cache
        translations_cache_collection.create_index("source_text_hash", unique=True)
        translations_cache_collection.create_index("created_at", expireAfterSeconds=Config.CACHE_TTL_HOURS * 3600)
        logger.info("Коллекция 'translations_cache' создана/проверена с TTL индексом")

        # Коллекция для сохранённых слов пользователя
        saved_words_collection = db.saved_words
        saved_words_collection.create_index([("telegram_id", 1), ("source_text_normalized", 1)], unique=True)
        saved_words_collection.create_index("telegram_id")
        logger.info("Коллекция 'saved_words' создана/проверена")

        logger.info("Все MongoDB коллекции успешно инициализированы")

    except Exception as e:
        logger.error(f"Ошибка при инициализации MongoDB коллекций: {e}", exc_info=True)
        raise

# Инициализация при импорте модуля
if Config.MONGODB_URI:
    try:
        initialize_mongodb_collections()
    except Exception as e:
        logger.error(f"Не удалось инициализировать MongoDB: {e}")

