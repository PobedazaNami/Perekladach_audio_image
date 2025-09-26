"""
Модуль для многоязычной поддержки интерфейса бота.
Содержит переводы для украинского, русского и немецкого языков.
"""

# Словарь переводов для интерфейса бота
TRANSLATIONS = {
    # Приветствие и старт
    "welcome": {
        "uk": "🤖 **Ласкаво просимо до перекладача!**",
        "ru": "🤖 **Добро пожаловать в переводчик!**", 
        "de": "🤖 **Willkommen beim Übersetzer!**"
    },
    
    "high_performance": {
        "uk": "🚀 **Високопродуктивний бот з оптимізацією:**",
        "ru": "🚀 **Высокопроизводительный бот с оптимизацией:**",
        "de": "🚀 **Hochleistungsbot mit Optimierung:**"
    },
    
    "supported_formats": {
        "uk": "📝 **Підтримувані формати:**",
        "ru": "📝 **Поддерживаемые форматы:**", 
        "de": "📝 **Unterstützte Formate:**"
    },
    
    "text_messages": {
        "uk": "• 💬 Текстові повідомлення (режим 1)",
        "ru": "• 💬 Текстовые сообщения (режим 1)",
        "de": "• 💬 Textnachrichten (Modus 1)"
    },
    
    "image_messages": {
        "uk": "• 🖼️ Зображення з текстом (режим 2)",
        "ru": "• 🖼️ Изображения с текстом (режим 2)",
        "de": "• 🖼️ Bilder mit Text (Modus 2)"
    },
    
    "audio_messages": {
        "uk": "• 🎤 Голосові повідомлення (режим 3)",
        "ru": "• 🎤 Голосовые сообщения (режим 3)",
        "de": "• 🎤 Sprachnachrichten (Modus 3)"
    },
    
    "practice_mode": {
        "uk": "• 📚 Практика німецької (режим 4)",
        "ru": "• 📚 Практика немецкого (режим 4)",
        "de": "• 📚 Deutsche Praxis (Modus 4)"
    },
    
    "current_mode": {
        "uk": "🔄 **Поточний режим:** {mode_name}",
        "ru": "🔄 **Текущий режим:** {mode_name}",
        "de": "🔄 **Aktueller Modus:** {mode_name}"
    },
    
    "commands": {
        "uk": "**Команди:**",
        "ru": "**Команды:**",
        "de": "**Befehle:**"
    },
    
    "mode_command": {
        "uk": "• /mode - Вибрати режим перекладу",
        "ru": "• /mode - Выбрать режим перевода", 
        "de": "• /mode - Übersetzungsmodus wählen"
    },
    
    "language_command": {
        "uk": "• /language - Вибрати мову інтерфейсу",
        "ru": "• /language - Выбрать язык интерфейса",
        "de": "• /language - Interface-Sprache wählen"
    },
    
    "stats_command": {
        "uk": "• /stats - Статистика продуктивності",
        "ru": "• /stats - Статистика производительности",
        "de": "• /stats - Leistungsstatistiken"
    },
    
    "switch_mode_instruction": {
        "uk": "Для зміни режиму натисніть кнопку нижче 👇",
        "ru": "Для смены режима нажмите кнопку ниже 👇",
        "de": "Um den Modus zu wechseln, drücken Sie die Taste unten 👇"
    },
    
    # Режимы перевода
    "mode_1_name": {
        "uk": "📄 Режим текстового перекладу",
        "ru": "📄 Режим текстового перевода",
        "de": "📄 Textübersetzungsmodus"
    },
    
    "mode_2_name": {
        "uk": "🖼️ Режим перекладу зображень",
        "ru": "🖼️ Режим перевода изображений", 
        "de": "🖼️ Bildübersetzungsmodus"
    },
    
    "mode_3_name": {
        "uk": "🎤 Режим перекладу аудіо",
        "ru": "🎤 Режим перевода аудио",
        "de": "🎤 Audio-Übersetzungsmodus"
    },
    
    "mode_4_name": {
        "uk": "📚 Режим практики (Німецька A2-B1)",
        "ru": "📚 Режим практики (Німецька A2-B1)",
        "de": "📚 Übungsmodus (Deutsch A2-B1)"
    },
    
    # Сообщения режимов
    "mode_1_description": {
        "uk": "📄 Режим текстового перекладу. Відправляйте тексти для перекладу.",
        "ru": "📄 Режим текстового перевода. Отправляйте тексты для перевода.",
        "de": "📄 Textübersetzungsmodus. Senden Sie Texte zur Übersetzung."
    },
    
    "mode_2_description": {
        "uk": "🖼️ Режим перекладу зображень. Відправляйте зображення з текстом.",
        "ru": "🖼️ Режим перевода изображений. Отправляйте изображения с текстом.",
        "de": "🖼️ Bildübersetzungsmodus. Senden Sie Bilder mit Text."
    },
    
    "mode_3_description": {
        "uk": "🎤 Режим перекладу аудіо. Відправляйте голосові повідомлення.",
        "ru": "🎤 Режим перевода аудио. Отправляйте голосовые сообщения.",
        "de": "🎤 Audio-Übersetzungsmodus. Senden Sie Sprachnachrichten."
    },
    
    "mode_4_description": {
        "uk": "📚 Режим практики німецької. Відправте '+' для початку уроку.",
        "ru": "📚 Режим практики немецкого. Отправьте '+' для начала урока.", 
        "de": "📚 Deutsch-Übungsmodus. Senden Sie '+' um die Lektion zu starten."
    },
    
    # Кнопки
    "switch_mode": {
        "uk": "Змінити режим",
        "ru": "Switch Mode",
        "de": "Modus wechseln"
    },
    
    "choose_mode": {
        "uk": "Оберіть режим:",
        "ru": "Выберите режим:",
        "de": "Wählen Sie den Modus:"
    },

    # Кнопки главного меню
    "switch_mode_button": {
        "uk": "Змінити режим",
        "ru": "Сменить режим",
        "de": "Modus wechseln"
    },

    "language_button": {
        "uk": "Мова інтерфейсу",
        "ru": "Язык интерфейса",
        "de": "Interface-Sprache"
    },
    
    "choose_language": {
        "uk": "Оберіть мову інтерфейсу:",
        "ru": "Выберите язык интерфейса:",
        "de": "Wählen Sie die Interface-Sprache:"
    },
    
    # Режимы в кнопках
    "mode_1_button": {
        "uk": "1: Текстовий переклад",
        "ru": "1: Текстовый перевод",
        "de": "1: Textübersetzung"
    },
    
    "mode_2_button": {
        "uk": "2: Переклад зображень",
        "ru": "2: Перевод изображений",
        "de": "2: Bildübersetzung"
    },
    
    "mode_3_button": {
        "uk": "3: Переклад аудіо",
        "ru": "3: Перевод аудио", 
        "de": "3: Audio-Übersetzung"
    },
    
    "mode_4_button": {
        "uk": "4: Практика (Німецька A2-B1)",
        "ru": "4: Практика (Німецька A2-B1)",
        "de": "4: Übung (Deutsch A2-B1)"
    },
    
    # Языки в кнопках
    "ukrainian_language": {
        "uk": "🇺🇦 Українська",
        "ru": "🇺🇦 Українська", 
        "de": "🇺🇦 Ukrainisch"
    },
    
    "russian_language": {
        "uk": "🇷🇺 Російська",
        "ru": "🇷🇺 Русский",
        "de": "🇷🇺 Russisch"
    },
    
    "german_language": {
        "uk": "🇩🇪 Німецька",
        "ru": "🇩🇪 Немецкий",
        "de": "🇩🇪 Deutsch"
    },
    
    # Сообщения об ошибках
    "processing": {
        "uk": "🕒 Ваше повідомлення обробляється, будь ласка, зачекайте...",
        "ru": "🕒 Ваше сообщение обрабатывается, пожалуйста, подождите...",
        "de": "🕒 Ihre Nachricht wird verarbeitet, bitte warten..."
    },
    
    "error": {
        "uk": "❌ Сталася помилка. Спробуйте пізніше.",
        "ru": "❌ Произошла ошибка. Попробуйте позже.",
        "de": "❌ Ein Fehler ist aufgetreten. Versuchen Sie es später."
    },
    
    "mode_changed": {
        "uk": "Режим змінено на {mode}.",
        "ru": "Режим изменен на {mode}.",
        "de": "Modus geändert zu {mode}."
    },
    
    "language_changed": {
        "uk": "✅ Мову інтерфейсу змінено на українську!",
        "ru": "✅ Язык интерфейса изменен на русский!",
        "de": "✅ Interface-Sprache wurde auf Deutsch geändert!"
    }
}

# Ключи для словаря пользователя
TRANSLATIONS.update({
    "save_word_button": {
        "uk": "⭐ Зберегти слово",
        "ru": "⭐ Сохранить слово",
        "de": "⭐ Wort speichern"
    },
    "word_saved": {
        "uk": "✅ Додано до словника",
        "ru": "✅ Добавлено в словарь",
        "de": "✅ Zum Wörterbuch hinzugefügt"
    },
    "word_save_failed": {
        "uk": "❌ Не вдалося зберегти",
        "ru": "❌ Не удалось сохранить",
        "de": "❌ Speichern fehlgeschlagen"
    },
    "your_words_header": {
        "uk": "📒 Збережені слова:",
        "ru": "📒 Сохранённые слова:",
        "de": "📒 Gespeicherte Wörter:"
    },
    "no_words": {
        "uk": "Поки що немає збережених слів.",
        "ru": "Пока нет сохранённых слов.",
        "de": "Noch keine gespeicherten Wörter."
    }
})

# Дополнительные кнопки для работы со словарём без команд
TRANSLATIONS.update({
    "my_words_button": {
        "uk": "📒 Мої слова",
        "ru": "📒 Мои слова",
        "de": "📒 Meine Wörter"
    },
    "close_button": {
        "uk": "❌ Закрити",
        "ru": "❌ Закрыть",
        "de": "❌ Schließen"
    }
})

def get_text(key: str, language: str = "uk", **kwargs) -> str:
    """
    Получает переведенный текст для указанного языка.
    
    Args:
        key: Ключ перевода
        language: Код языка (uk, ru, de)
        **kwargs: Параметры для форматирования строки
        
    Returns:
        Переведенный текст
    """
    if key not in TRANSLATIONS:
        return f"[MISSING: {key}]"
        
    if language not in TRANSLATIONS[key]:
        language = "uk"  # Fallback на украинский
        
    text = TRANSLATIONS[key][language]
    
    # Форматирование строки если есть параметры
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass  # Игнорируем отсутствующие параметры
            
    return text