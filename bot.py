import os
import logging
import requests
import io
import re
import google.generativeai as genai
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токены — Render подставит их из Environment Variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7666404800:AAGu50Hpe4eCudLPR7_zwTvYN2B8G57cwy4")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCJVD8Y8dv238ABzRH0SbiiLvVyPcwCmh8")

# Настройка Gemini
genai.configure(api_key=GEMINI_KEY)
text_model = genai.GenerativeModel("gemini-2.0-flash")

# ─────────────────────────────────────────────
#  SUPER-ПРОМПТ — голос SUNKAR FINANCE
#  Стиль взят из реальных постов и сайта бренда
# ─────────────────────────────────────────────
SUPER_PROMPT = """Ты — контент-директор SUNKAR FINANCE, финтех-компании в Астане.

ГОЛОС БРЕНДА:
• Уверенный, экспертный, без лишней воды
• Мы не "помогаем" — мы ОДОБРЯЕМ
• Короткие мощные фразы, цифры, конкретика
• Без банальщины типа "мечта стала реальностью"
• Стиль реальных постов: "Банк отказал? Не беда — приходи к нам"

КОМПАНИЯ:
• Беззалоговые кредиты: до 10 млн ₸ (строго без текущих просрочек)
• Кредиты под залог недвижимости: до 50 млн ₸
• Для ИП и ТОО: до 30 млн ₸ (от 6 месяцев деятельности)
• Ипотека: все банки, возможно без первоначального взноса
• Офис: г. Астана, пр. Абая 18, БЦ Шахар, каб. 102
• WhatsApp: wa.me/77052606667
• Сайт: https://sunkar-finance-astana.github.io/KZ/index.html
• Бот: https://t.me/SunkarFinance_bot

СТИЛЬ ДИЗАЙНА (для промптов):
Цвет фона: тёмно-синий #060D1F / #0A1428
Акцент: неоновый зелёный #00E676
Второй акцент: синий #2979FF
Шрифт: жирный sans-serif (Unbounded/Nunito)
Эффекты: свечение, градиент зелёный→синий, тёмные карточки

ТЕМА ДЛЯ ГЕНЕРАЦИИ: {topic}

━━━━━━━━━━━━━━━━━━━━━━
Сгенерируй следующий контент:

1. 📸 INSTAGRAM-КАРУСЕЛЬ (5 слайдов)

*Слайд 1 — Обложка-боль (КАПС):*
Заголовок-крючок о проблеме клиента

*Слайд 2 — Факт/статистика:*
Цифра или инсайт + упомянуть "анализ кредитной истории за 2 минуты"

*Слайд 3 — Решение:*
Мы одобряем даже при высокой нагрузке. ОФОРМЛЕНИЕ ЗА 1 ДЕНЬ.

*Слайд 4 — Продукты:*
До 10 млн ₸ без залога | До 50 млн ₸ под залог | До 30 млн ₸ для ИП. БЕЗ ПРЕДОПЛАТЫ.

*Слайд 5 — CTA:*
Напиши в WhatsApp: wa.me/77052606667
Офис: Астана, Абая 18, БЦ Шахар, каб. 102
Строго без текущих просрочек.

2. 🎬 REELS / TIKTOK (15–20 сек)

Хук (3 сек): удар по боли — «Банк отказал? Не подавай новую заявку!»
Основная часть (10 сек): главная мысль темы, конкретная цифра
Концовка (5 сек): «Узнай шансы за 2 минуты → wa.me/77052606667»

3. 🧵 THREADS

Одно жёсткое предложение с цифрой или болью.
+ «Пиши в WhatsApp — ссылка в профиле»

4. 💬 WHATSAPP-РАССЫЛКА

Короткий текст как в реальных рассылках: приветствие → боль → решение → оффер → контакт.
Эмодзи умеренно. Без лишней воды.

5. 🖼️ ПРОМПТЫ ДЛЯ КАРТИНОК

Выведи строго в формате [IMAGE_PROMPTS] (все на английском):
[IMAGE_PROMPTS]
1. Dark navy blue background #060D1F, neon green #00E676 glowing text, slide cover with bold pain-point headline, fintech style, Sunkar Finance logo placeholder top-left, dramatic lighting, professional
2. Dark navy fintech slide, large glowing green statistic/number center, small text below, gradient green-to-blue accent lines, dark card UI elements
3. Dark navy slide, bold "APPROVED" or solution message in neon green, "1 DAY" badge with green glow, modern fintech design
4. Dark navy slide, 3 product cards with green-blue gradient borders, loan amounts in large neon green text, professional fintech layout
5. Dark navy CTA slide, WhatsApp button with green glow, office address, Sunkar Finance eagle logo, "NO PREPAYMENT" badge
"""

# ─────────────────────────────────────────────
#  Генерация изображения через Pollinations
# ─────────────────────────────────────────────
def generate_image(prompt: str) -> bytes:
    """Генерирует изображение через бесплатный Pollinations API."""
    encoded = requests.utils.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1080&nologo=true&seed=42"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def parse_image_prompts(text: str) -> list[str]:
    """
    Надёжно парсит промпты из блока [IMAGE_PROMPTS].
    Работает даже если Gemini добавил лишний текст.
    """
    # Ищем блок после [IMAGE_PROMPTS]
    match = re.search(r'\[IMAGE_PROMPTS\](.*?)(?:\[|$)', text, re.DOTALL | re.IGNORECASE)
    block = match.group(1) if match else text

    prompts = []
    for line in block.strip().splitlines():
        line = line.strip()
        # Строки вида "1. ..." или "1) ..."
        m = re.match(r'^\d+[\.\)]\s+(.+)', line)
        if m:
            prompts.append(m.group(1).strip())

    return prompts


# ─────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🦅 *SUNKAR FINANCE — Генератор контента*\n\n"
        "Напиши тему — получишь:\n"
        "📸 Карусель Instagram (5 слайдов)\n"
        "🎬 Сценарий Reels/TikTok\n"
        "🧵 Пост для Threads\n"
        "💬 WhatsApp-рассылку\n"
        "🖼️ 5 промптов для картинок\n\n"
        "*Примеры тем:*\n"
        "• _Кредит при высокой долговой нагрузке_\n"
        "• _Ипотека без первоначального взноса_\n"
        "• _Кредит для ИП без справок_\n\n"
        "Для генерации картинок: /image тема"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─────────────────────────────────────────────
#  Обработка текстового сообщения → контент
# ─────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    if not topic:
        return

    msg = await update.message.reply_text("⏳ Генерирую контент для SUNKAR FINANCE...")

    try:
        full_prompt = SUPER_PROMPT.format(topic=topic)
        response = text_model.generate_content(full_prompt)
        result_text = response.text

        await msg.delete()

        # Разбиваем на чанки по 4000 символов (лимит Telegram)
        chunks = [result_text[i:i + 4000] for i in range(0, len(result_text), 4000)]
        for chunk in chunks:
            # Используем HTML вместо Markdown — меньше проблем со спецсимволами
            await update.message.reply_text(chunk)

    except Exception as e:
        logger.error(f"[handle_message] Ошибка: {e}")
        await msg.edit_text(
            f"❌ Ошибка генерации текста.\n"
            f"Попробуй ещё раз или напиши другую тему.\n\n"
            f"Детали: {str(e)[:200]}"
        )


# ─────────────────────────────────────────────
#  /image → генерация 5 картинок карусели
# ─────────────────────────────────────────────
async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = ' '.join(context.args).strip()
    if not topic:
        await update.message.reply_text(
            "Укажи тему после команды.\n"
            "Пример: /image Кредит под залог авто"
        )
        return

    msg = await update.message.reply_text("🎨 Создаю 5 картинок для карусели... (~30 сек)")

    try:
        # Получаем промпты от Gemini
        gemini_prompt = (
            f"Создай 5 image prompts на английском для карусели Instagram на тему: {topic}\n\n"
            "Бренд SUNKAR FINANCE — финтех Астана.\n"
            "Стиль: dark navy blue background #060D1F, neon green #00E676 accents, "
            "blue #2979FF secondary accents, bold sans-serif font, professional fintech, glowing effects.\n\n"
            "Выведи СТРОГО в формате:\n"
            "[IMAGE_PROMPTS]\n"
            "1. (подробный prompt для слайда 1 — обложка с болью)\n"
            "2. (слайд 2 — статистика/факт)\n"
            "3. (слайд 3 — решение, одобрение)\n"
            "4. (слайд 4 — продукты и суммы)\n"
            "5. (слайд 5 — CTA с WhatsApp)\n"
            "Ничего лишнего кроме этого блока."
        )

        gemini_response = text_model.generate_content(gemini_prompt)
        raw_text = gemini_response.text
        logger.info(f"Gemini raw image prompts:\n{raw_text}")

        prompts = parse_image_prompts(raw_text)

        if len(prompts) < 3:
            # Фолбек: используем дефолтные промпты если парсинг не удался
            logger.warning("Не удалось распарсить промпты, использую дефолтные")
            prompts = [
                f"Dark navy blue fintech slide, neon green headline about {topic}, "
                "Sunkar Finance eagle logo, professional dramatic lighting, bold text",
                f"Dark navy fintech infographic slide, large neon green statistic about {topic}, "
                "glowing gradient accent lines, financial data visualization",
                f"Dark navy approval slide, 'APPROVED' text in neon green, "
                f"1 DAY processing badge, professional fintech style, topic: {topic}",
                "Dark navy product card slide, three loan options with neon green amounts, "
                "10M / 50M / 30M tenge, fintech UI card design",
                "Dark navy CTA slide, WhatsApp green button glowing, Sunkar Finance eagle logo, "
                "Astana Kazakhstan, neon green call-to-action"
            ]

        # Добиваем до 5 если меньше
        while len(prompts) < 5:
            prompts.append(prompts[-1])

        # Генерируем картинки
        media = []
        for i, prompt_text in enumerate(prompts[:5]):
            logger.info(f"Генерирую картинку {i+1}/5: {prompt_text[:80]}...")
            img_bytes = generate_image(prompt_text)
            bio = io.BytesIO(img_bytes)
            bio.name = f"sunkar_slide_{i+1}.png"

            caption = f"🖼 Слайд {i+1}/5 — {topic}" if i == 0 else None
            if caption:
                media.append(InputMediaPhoto(media=bio, caption=caption))
            else:
                media.append(InputMediaPhoto(media=bio))

        await msg.delete()
        await update.message.reply_media_group(media)
        await update.message.reply_text(
            "✅ Карусель готова!\n\n"
            "Следующий шаг: загрузи в Buffer или напрямую в Instagram.\n"
            "Для текста карусели отправь тему без /image"
        )

    except requests.exceptions.Timeout:
        logger.error("Pollinations API timeout")
        await msg.edit_text(
            "⏱ Сервис генерации картинок не отвечает. Попробуй через минуту."
        )
    except Exception as e:
        logger.error(f"[image_command] Ошибка: {e}")
        await msg.edit_text(
            f"❌ Ошибка генерации картинок.\n"
            f"Детали: {str(e)[:200]}"
        )


# ─────────────────────────────────────────────
#  Запуск
# ─────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("image", image_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🦅 SUNKAR FINANCE BOT — запущен")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
