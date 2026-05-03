import os
import logging
import requests
import io
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot.types import InputMediaPhoto

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
PORT = int(os.environ.get("PORT", 10000))

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

SUPER_PROMPT = """Ты — контент-директор SUNKAR FINANCE, финтех-компании в Астане.

ГОЛОС БРЕНДА:
- Уверенный, экспертный, без лишней воды
- Мы не "помогаем" — мы ОДОБРЯЕМ
- Короткие мощные фразы, цифры, конкретика
- Стиль: "Банк отказал? Не беда — приходи к нам"

КОМПАНИЯ:
- Беззалоговые кредиты: до 10 млн (строго без текущих просрочек)
- Кредиты под залог недвижимости: до 50 млн
- Для ИП и ТОО: до 30 млн (от 6 месяцев деятельности)
- Ипотека: все банки, возможно без первоначального взноса
- Офис: г. Астана, пр. Абая 18, БЦ Шахар, каб. 102
- WhatsApp: wa.me/77052606667

ТЕМА: {topic}

Сгенерируй:

1. INSTAGRAM-КАРУСЕЛЬ (5 слайдов)
Слайд 1 - Обложка-боль КАПСОМ
Слайд 2 - Факт/цифра + анализ кредитной истории за 2 минуты
Слайд 3 - Решение: одобряем даже при высокой нагрузке, ОФОРМЛЕНИЕ ЗА 1 ДЕНЬ
Слайд 4 - Продукты: до 10 млн без залога, до 50 млн под залог, до 30 млн ИП. БЕЗ ПРЕДОПЛАТЫ
Слайд 5 - CTA: wa.me/77052606667, Астана Абая 18 БЦ Шахар. Строго без просрочек.

2. REELS / TIKTOK (15-20 сек)
Хук (3 сек) - удар по боли
Основная часть (10 сек) - мысль темы с цифрой
Концовка (5 сек) - Узнай шансы за 2 минуты: wa.me/77052606667

3. THREADS
Одно жёсткое предложение с цифрой + Пиши в WhatsApp (ссылка в профиле)

4. WHATSAPP-РАССЫЛКА
Приветствие - боль - решение - оффер - контакт. Эмодзи умеренно.

5. ПРОМПТЫ ДЛЯ КАРТИНОК
[IMAGE_PROMPTS]
1. Dark navy #060D1F background, neon green #00E676 glowing headline, fintech professional
2. Dark navy fintech infographic, large neon green statistic, gradient green-to-blue accents
3. Dark navy slide, APPROVED neon green text, 1 DAY green badge, modern fintech
4. Dark navy product cards, neon green loan amounts 10M 50M 30M tenge, fintech UI
5. Dark navy CTA slide, WhatsApp green button glowing, Astana Kazakhstan
"""


# ── HTTP-сервер для Render (держит порт открытым) ──
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"SUNKAR FINANCE BOT is running")

    def log_message(self, *args):
        pass  # отключаем логи HTTP


def run_http_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"HTTP сервер запущен на порту {PORT}")
    server.serve_forever()


# ── Gemini API ──
def ask_gemini(prompt: str) -> str:
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(GEMINI_URL, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


# ── Pollinations ──
def generate_image(prompt: str) -> bytes:
    encoded = requests.utils.quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=1080&height=1080&nologo=true&seed=42"
    )
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def parse_image_prompts(text: str) -> list:
    match = re.search(r'\[IMAGE_PROMPTS\](.*?)(?:\[|$)', text, re.DOTALL | re.IGNORECASE)
    block = match.group(1) if match else text
    prompts = []
    for line in block.strip().splitlines():
        line = line.strip()
        m = re.match(r'^\d+[\.\)]\s+(.+)', line)
        if m:
            prompts.append(m.group(1).strip())
    return prompts


# ── Команды бота ──
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message,
        "🦅 SUNKAR FINANCE — Генератор контента\n\n"
        "Напиши тему — получишь:\n"
        "📸 Карусель Instagram (5 слайдов)\n"
        "🎬 Сценарий Reels/TikTok\n"
        "🧵 Пост для Threads\n"
        "💬 WhatsApp-рассылку\n"
        "🖼 Промпты для картинок\n\n"
        "Примеры:\n"
        "• Кредит при высокой долговой нагрузке\n"
        "• Ипотека без первоначального взноса\n"
        "• Кредит для ИП без справок\n\n"
        "Для картинок: /image тема"
    )


@bot.message_handler(commands=['image'])
def image_command(message):
    topic = message.text.replace('/image', '').strip()
    if not topic:
        bot.reply_to(message, "Пример: /image Кредит под залог авто")
        return

    msg = bot.reply_to(message, "🎨 Создаю 5 картинок... (~30 сек)")
    try:
        raw = ask_gemini(
            f"Создай 5 image prompts на английском для карусели Instagram на тему: {topic}\n"
            "Стиль: dark navy #060D1F, neon green #00E676, blue #2979FF, bold fintech.\n"
            "Формат строго:\n[IMAGE_PROMPTS]\n1. ...\n2. ...\n3. ...\n4. ...\n5. ..."
        )
        prompts = parse_image_prompts(raw)

        if len(prompts) < 3:
            prompts = [
                f"Dark navy fintech slide, neon green headline about {topic}",
                f"Dark navy infographic, neon green statistic about {topic}",
                "Dark navy approval slide, APPROVED neon green, 1 DAY badge",
                "Dark navy product cards, neon green amounts 10M 50M 30M tenge",
                "Dark navy CTA slide, WhatsApp green button, Sunkar Finance"
            ]
        while len(prompts) < 5:
            prompts.append(prompts[-1])

        media = []
        for i, p in enumerate(prompts[:5]):
            img_bytes = generate_image(p)
            bio = io.BytesIO(img_bytes)
            bio.name = f"slide_{i+1}.png"
            caption = f"Карусель: {topic}" if i == 0 else None
            media.append(InputMediaPhoto(bio, caption=caption))

        bot.delete_message(message.chat.id, msg.message_id)
        bot.send_media_group(message.chat.id, media)
        bot.send_message(message.chat.id, "✅ Готово! Загружай в Instagram.")

    except Exception as e:
        logger.error(f"[image] {e}")
        bot.edit_message_text(f"❌ Ошибка: {str(e)[:200]}",
                              message.chat.id, msg.message_id)


@bot.message_handler(func=lambda m: True)
def handle_message(message):
    topic = message.text.strip()
    msg = bot.reply_to(message, "⏳ Генерирую контент для SUNKAR FINANCE...")
    try:
        result = ask_gemini(SUPER_PROMPT.format(topic=topic))
        bot.delete_message(message.chat.id, msg.message_id)
        for chunk in [result[i:i+4000] for i in range(0, len(result), 4000)]:
            bot.send_message(message.chat.id, chunk)
    except Exception as e:
        logger.error(f"[msg] {e}")
        bot.edit_message_text(f"❌ Ошибка: {str(e)[:200]}",
                              message.chat.id, msg.message_id)


# ── Запуск ──
if __name__ == "__main__":
    # HTTP сервер в отдельном потоке
    t = threading.Thread(target=run_http_server, daemon=True)
    t.start()

    logger.info("🦅 SUNKAR FINANCE BOT — запущен")
    bot.infinity_polling()
    
