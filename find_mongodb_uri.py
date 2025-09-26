#!/usr/bin/env python3
"""
Тест различных MongoDB URI для поиска правильного hostname
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import sys

# Возможные варианты hostname кластера
possible_hostnames = [
    "cluster0.mongodb.net",
    "cluster0.xxxxx.mongodb.net", 
    "cluster1.mongodb.net",
    "cluster.mongodb.net",
    "reddit.mongodb.net",
    "cluster0.abcde.mongodb.net",
    "cluster0.12345.mongodb.net"
]

username = "anaitore32_db_user"
password = "8bFaM8S9DrUP3Kot"

async def test_connection(hostname):
    """Тестирует подключение с данным hostname"""
    uri = f"mongodb+srv://{username}:{password}@{hostname}/?retryWrites=true&w=majority"
    
    try:
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        print(f"✅ УСПЕХ: {hostname}")
        client.close()
        return uri
    except Exception as e:
        print(f"❌ {hostname}: {str(e)[:50]}...")
        return None

async def find_correct_uri():
    """Найти правильный URI"""
    print("🔍 Поиск правильного MongoDB URI...")
    print("=" * 50)
    
    for hostname in possible_hostnames:
        print(f"⏳ Тестирую: {hostname}")
        correct_uri = await test_connection(hostname)
        if correct_uri:
            print(f"\n🎉 НАЙДЕН ПРАВИЛЬНЫЙ URI!")
            print(f"📝 Обнови .env файл:")
            print(f"MONGODB_URI={correct_uri}")
            return correct_uri
        await asyncio.sleep(1)
    
    print("\n❌ Ни один вариант не сработал")
    print("💡 Нужно получить точный connection string из MongoDB Atlas")
    return None

if __name__ == "__main__":
    asyncio.run(find_correct_uri())