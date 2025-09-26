#!/usr/bin/env python3
"""
Простая проверка MongoDB URI
"""
import re

def validate_mongodb_uri(uri):
    """Проверяет корректность MongoDB URI"""
    print(f"🔍 Анализируем URI: {uri}")
    
    # Паттерн для MongoDB Atlas URI
    pattern = r'mongodb\+srv://([^:]+):([^@]+)@([^/]+)/?(.+)?'
    match = re.match(pattern, uri)
    
    if match:
        username = match.group(1)
        password = match.group(2)[:5] + "***"  # Скрываем пароль
        cluster = match.group(3)
        params = match.group(4) or ""
        
        print(f"✅ URI структура корректна:")
        print(f"   👤 Пользователь: {username}")
        print(f"   🔐 Пароль: {password}")
        print(f"   🖥️  Кластер: {cluster}")
        print(f"   ⚙️  Параметры: {params}")
        
        # Проверяем кластер
        if "cluster.mongodb.net" in cluster:
            print("⚠️  ВНИМАНИЕ: Похоже на стандартный адрес Atlas")
            print("   Возможные проблемы:")
            print("   1. Кластер приостановлен (paused)")
            print("   2. Неправильный hostname кластера")
            print("   3. Кластер удален")
        
        return True
    else:
        print("❌ URI структура некорректна!")
        return False

# Проверяем URI
uri = "mongodb+srv://anaitore32_db_user:8bFaM8S9DrUP3Kot@cluster.mongodb.net/?retryWrites=true&w=majority"
validate_mongodb_uri(uri)

print("\n💡 РЕШЕНИЕ:")
print("1. Зайди в MongoDB Atlas: https://cloud.mongodb.com")
print("2. Проверь что кластер активен (не paused)")
print("3. Database → Connect → Connect your application")
print("4. Скопируй НОВЫЙ connection string")
print("5. Обнови MONGODB_URI в .env файле")