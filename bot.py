import os
import logging
import requests
import io
import re
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot.types import InputMediaPhoto

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
PORT = int(os.environ.get("PORT", 10000))

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
processed_messages = set()

SYSTEM_MSG = "Ты помощник копирайтер. Отвечай только на русском языке. Пиши коротко, конкретно, без лишних слов. Без звёздочек и markdown."

# Шаблоны с жёстко зашитыми правильными фразами
# Groq только генерирует: боль клиента, факт по теме, описание подхода — всё остальное фиксировано

CAROUSEL_PROMPT = """Тема: {topic}

Напиши для каждого слайда ТОЛЬКО указанное. Без заголовков, без пояснений, только текст слайда.

Слайд 1: Короткий заголовок КАПСЛОКОМ — боль клиента по теме "{topic}". Максимум 6 слов. Только текст, без слова "Слайд 1".

Слайд 2: Один факт или цифра по теме "{topic}" + "За 2 минуты узнаешь свои шансы на одобрение." Только текст.

Слайд 3: Одно предложение — как SUNKAR FINANCE помогает получить одобрение по теме "{topic}". Используй фразы типа "знаем как подать заявку", "помогаем получить одобрение", "там где банк отказал — мы знаем как зайти". Только текст.

Напиши три строки подряд, каждая с новой строки. Без нумерации."""

def ask_groq(system: str, user: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "max_tokens": 800,
        "temperature": 0.7
    }
    for attempt in range(3):
        try:
            resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
            if resp.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Groq попытка {attempt+1}: {e}")
            if attempt < 2:
                time.sleep(3)
    raise Exception("Groq не отвечает. Попробуй через минуту.")


def build_content(topic: str) -> dict:
    # Groq генерирует только 3 переменных слайда
    raw = ask_groq(SYSTEM_MSG, CAROUSEL_PROMPT.format(topic=topic))
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    
    slide1 = lines[0] if len(lines) > 0 else f"БАНК ОТКАЗАЛ ПО ТЕМЕ {topic.upper()}?"
    slide2 = lines[1] if len(lines) > 1 else f"Многие сталкиваются с отказом по теме {topic}. За 2 минуты узнаешь свои шансы на одобрение."
    slide3 = lines[2] if len(lines) > 2 else f"Знаем как подать заявку правильно — помогаем получить одобрение даже в сложных случаях."

    # Карусель — фиксированная структура, только слайды 1-3 от Groq
    carousel = f"""Слайд 1: {slide1}

Слайд 2: {slide2}

Слайд 3: {slide3} Результат — за 1 день.

Слайд 4: Помогаем получить:
— До 10 млн без залога
— До 50 млн под залог недвижимости  
— До 30 млн для ИП и ТОО
БЕЗ ПРЕДОПЛАТЫ

Слайд 5: Узнай свои шансы прямо сейчас
wa.me/77052606667
Астана, пр. Абая 18, БЦ Шахар, каб. 102
Строго без текущих просрочек."""

    # Reels — фиксированный, только хук от Groq
    reels = f"""Хук (0-3 сек): {slide1}

Основная (4-14 сек): {slide3} Помогаем получить до 10 млн без залога — там где банк отказал, мы знаем как зайти.

Концовка (15-20 сек): Узнай шансы за 2 минуты — wa.me/77052606667"""

    # Threads — фиксированный
    threads = f"""Банк отказал по теме "{topic}"? Знаем как получить одобрение — помогли уже сотням клиентов. До 10 млн без залога. Пиши в WhatsApp — ссылка в профиле."""

    # WhatsApp — фиксированный
    whatsapp = f"""Добрый день! 💬

{slide1}

Не беда. SUNKAR FINANCE знает как получить одобрение там где банк отказал.

Помогаем получить:
✅ До 10 млн — без залога
✅ До 50 млн — под залог недвижимости
✅ До 30 млн — для ИП и ТОО
✅ Ипотека — все банки и программы

Без предоплаты. Результат за 1 день.
Строго без текущих просрочек.

Узнай шансы за 2 минуты 👇
wa.me/77052606667"""

    return {
        "carousel": carousel,
        "reels": reels,
        "threads": threads,
        "whatsapp": whatsapp
    }


IMAGE_PROMPTS = [
    "Abstract dark navy blue background, neon green glowing geometric lines forming rectangle frames, green light streaks, no text, professional fintech poster background",
    "Dark navy background, large glowing neon green circle in center, green to blue gradient ring, floating light particles, no text, modern finance aesthetic",
    "Dark navy background, neon green checkmark icon large and glowing, green ripple light effect spreading outward, clean minimal design, no text",
    "Dark navy background, three vertical glowing neon green pillars side by side, blue accent floor glow, symmetric layout, no text, modern UI concept",
    "Dark navy background, glowing green smartphone with light rays, green bokeh lights, professional clean layout, no text, contact concept"
]

def generate_image(prompt: str, seed: int = 42) -> bytes:
    encoded = requests.utils.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1080&nologo=true&seed={seed}&model=flux"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def send_images(chat_id, topic: str):
    media = []
    for i, p in enumerate(IMAGE_PROMPTS):
        try:
            img_bytes = generate_image(p, seed=i * 17 + 3)
            bio = io.BytesIO(img_bytes)
            bio.name = f"slide_{i+1}.png"
            media.append(InputMediaPhoto(bio, caption="🖼 Фоны для карусели — добавь текст в Canva" if i == 0 else None))
        except Exception as e:
            logger.error(f"Картинка {i+1}: {e}")
    if media:
        bot.send_media_group(chat_id, media)
        bot.send_message(chat_id, "💡 Открой Canva → загрузи фон → наложи текст из карусели выше.")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"SUNKAR FINANCE BOT is running")
    def log_message(self, *args):
        pass

def run_http_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"HTTP сервер на порту {PORT}")
    server.serve_forever()


@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message,
        "🦅 SUNKAR FINANCE — Генератор контента\n\n"
        "Напиши тему — получишь:\n"
        "📸 Карусель Instagram (5 слайдов)\n"
        "🎬 Сценарий Reels/TikTok\n"
        "🧵 Пост для Threads\n"
        "💬 WhatsApp-рассылку\n"
        "🖼 5 фонов для карусели\n\n"
        "Примеры:\n"
        "• Кредиты без залога\n"
        "• Ипотека без первоначального взноса\n"
        "• Кредит для ИП\n"
        "• Банк отказал"
    )


@bot.message_handler(func=lambda m: True)
def handle_message(message):
    if message.message_id in processed_messages:
        return
    processed_messages.add(message.message_id)
    if len(processed_messages) > 1000:
        processed_messages.clear()

    topic = message.text.strip()
    msg = bot.reply_to(message, "⏳ Генерирую контент... (10-15 сек)")

    try:
        content = build_content(topic)
        bot.delete_message(message.chat.id, msg.message_id)

        bot.send_message(message.chat.id, f"📸 INSTAGRAM-КАРУСЕЛЬ\n\n{content['carousel']}")
        bot.send_message(message.chat.id, f"🎬 REELS / TIKTOK\n\n{content['reels']}")
        bot.send_message(message.chat.id, f"🧵 THREADS\n\n{content['threads']}")
        bot.send_message(message.chat.id, f"💬 WHATSAPP-РАССЫЛКА\n\n{content['whatsapp']}")

        bot.send_message(message.chat.id, "🎨 Генерирую фоны... (~30 сек)")
        send_images(message.chat.id, topic)
        bot.send_message(message.chat.id, "✅ Готово!")

    except Exception as e:
        logger.error(f"[msg] {e}")
        bot.edit_message_text(f"❌ {str(e)[:200]}", message.chat.id, msg.message_id)


if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    threading.Thread(target=run_http_server, daemon=True).start()
    logger.info("🦅 SUNKAR FINANCE BOT — запущен на Groq")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
