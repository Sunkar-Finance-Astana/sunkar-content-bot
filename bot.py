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

SUPER_PROMPT = """Ты — контент-директор SUNKAR FINANCE, финтех-компании в Астане.

ГОЛОС БРЕНДА:
- Уверенный, экспертный, без лишней воды
- Мы не "помогаем" — мы ОДОБРЯЕМ
- Короткие мощные фразы, цифры, конкретика
- Стиль: "Банк отказал? Не беда — приходи к нам"
- БЕЗ звёздочек, БЕЗ markdown разметки — только чистый текст

КОМПАНИЯ:
- Беззалоговые кредиты: до 10 млн (строго без текущих просрочек)
- Кредиты под залог недвижимости: до 50 млн
- Для ИП и ТОО: до 30 млн (от 6 месяцев деятельности)
- Ипотека: все банки, возможно без первоначального взноса
- Офис: г. Астана, пр. Абая 18, БЦ Шахар, каб. 102
- WhatsApp: wa.me/77052606667

ТЕМА: {topic}

Сгенерируй строго в таком формате (без звёздочек и markdown):

===КАРУСЕЛЬ===
Слайд 1: [обложка-боль КАПСОМ]
Слайд 2: [факт/цифра + анализ за 2 минуты]
Слайд 3: [одобряем даже при высокой нагрузке, за 1 день]
Слайд 4: [продукты: до 10 млн без залога, до 50 млн под залог, до 30 млн ИП, БЕЗ ПРЕДОПЛАТЫ]
Слайд 5: [CTA: wa.me/77052606667, Астана Абая 18 БЦ Шахар каб 102. Строго без просрочек.]
===КОНЕЦ КАРУСЕЛЬ===

===REELS===
[сценарий 15-20 сек: хук 3 сек, основная часть 10 сек, концовка 5 сек с wa.me/77052606667]
===КОНЕЦ REELS===

===THREADS===
[одно жёсткое предложение с цифрой + Пиши в WhatsApp — ссылка в профиле]
===КОНЕЦ THREADS===

===WHATSAPP===
[рассылка: приветствие — боль — решение — оффер — контакт. Эмодзи умеренно.]
===КОНЕЦ WHATSAPP===

===ПРОМПТЫ===
1. [промпт на английском для Pollinations.ai, стиль: dark navy #060D1F, neon green #00E676]
2. [промпт на английском]
3. [промпт на английском]
4. [промпт на английском]
5. [промпт на английском]
===КОНЕЦ ПРОМПТЫ===
"""


def ask_groq(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2500,
        "temperature": 0.8
    }
    for attempt in range(3):
        try:
            resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                logger.warning(f"Groq 429, жду {wait} сек...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Groq попытка {attempt+1}: {e}")
            if attempt < 2:
                time.sleep(3)
    raise Exception("Groq не отвечает. Попробуй через минуту.")


def extract_block(text: str, tag: str) -> str:
    pattern = rf"==={tag}===(.*?)===КОНЕЦ {tag}==="
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_image_prompts(text: str) -> list:
    block = extract_block(text, "ПРОМПТЫ")
    prompts = []
    for line in block.splitlines():
        m = re.match(r'^\d+[\.\)]\s+(.+)', line.strip())
        if m:
            prompts.append(m.group(1).strip())
    return prompts


def generate_image(prompt: str) -> bytes:
    encoded = requests.utils.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1080&nologo=true&seed=42"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def send_images(chat_id, prompts: list, topic: str):
    if not prompts:
        return
    media = []
    for i, p in enumerate(prompts[:5]):
        try:
            img_bytes = generate_image(p)
            bio = io.BytesIO(img_bytes)
            bio.name = f"slide_{i+1}.png"
            media.append(InputMediaPhoto(bio, caption=f"📸 Карусель: {topic}" if i == 0 else None))
        except Exception as e:
            logger.error(f"Картинка {i+1}: {e}")
    if media:
        bot.send_media_group(chat_id, media)


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
        "🖼 5 картинок автоматически\n\n"
        "Примеры:\n"
        "• Кредиты без залога\n"
        "• Ипотека без первоначального взноса\n"
        "• Кредит для ИП\n"
        "• Банк отказал"
    )


@bot.message_handler(func=lambda m: True)
def handle_message(message):
    topic = message.text.strip()
    msg = bot.reply_to(message, "⏳ Генерирую контент... (10-15 сек)")

    try:
        result = ask_groq(SUPER_PROMPT.format(topic=topic))
        bot.delete_message(message.chat.id, msg.message_id)

        # Извлекаем блоки
        carousel = extract_block(result, "КАРУСЕЛЬ")
        reels = extract_block(result, "REELS")
        threads = extract_block(result, "THREADS")
        whatsapp = extract_block(result, "WHATSAPP")
        prompts = extract_image_prompts(result)

        # Отправляем каждый блок отдельно
        if carousel:
            bot.send_message(message.chat.id, f"📸 INSTAGRAM-КАРУСЕЛЬ\n\n{carousel}")
        if reels:
            bot.send_message(message.chat.id, f"🎬 REELS / TIKTOK\n\n{reels}")
        if threads:
            bot.send_message(message.chat.id, f"🧵 THREADS\n\n{threads}")
        if whatsapp:
            bot.send_message(message.chat.id, f"💬 WHATSAPP-РАССЫЛКА\n\n{whatsapp}")

        # Генерируем картинки
        if prompts:
            bot.send_message(message.chat.id, "🎨 Генерирую картинки... (~30 сек)")
            send_images(message.chat.id, prompts, topic)
            bot.send_message(message.chat.id, "✅ Готово!")
        else:
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
