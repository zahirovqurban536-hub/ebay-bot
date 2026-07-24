import os
import asyncio
import logging
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from google import genai

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Flask ilə mini port serveri (Render rahat işləsin deyə)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot aktivdir və işləyir!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Gemini Klienti
client = genai.Client(api_key=GEMINI_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salam! Mən sizin eBay Dropshipping köməkçinizəm. 🚀\n\n"
        "Məhsul üçün SEO başlıq yaratmaq üçün belə yazın:\n"
        "/title bluetooth earbuds"
    )

async def generate_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Zəhmət olmasa məhsul adını qeyd edin.\nNümunə: /title wireless bluetooth earbuds")
        return

    user_query = " ".join(context.args)
    await update.message.reply_text("🔍 Gemini AI optimal SEO başlığı hazırlayır...")

    prompt = f"""
    You are an expert eBay SEO listing specialist. 
    Create a highly optimized, high-converting eBay product title based on this product query: "{user_query}".
    
    Rules:
    - Maximum 80 characters (eBay limit).
    - Include main keywords, item specifics (brand/style/features), and high-search terms.
    - DO NOT use filler words like "L@@K", "WOW", "FREE SHIPPING", "NEW".
    - Make it readable, catchy, and natural.
    - Return ONLY 3 unique title options, numbered 1 to 3. Do not add any intro/outro text.
    """

    # Modelləri sırayla yoxlayırıq ki, 403 xətası olmasın
    models_to_try = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-2.0-flash']
    response_text = None

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            response_text = response.text
            break
        except Exception as e:
            continue

    if response_text:
        await update.message.reply_text(f"🚀 **Təklif Olunan eBay Başlıqları:**\n\n{response_text}")
    else:
        await update.message.reply_text("Xəta: API Key icazəsi məhdudlaşdırılıb (403). Lütfən Google AI Studio-dan yeni API Key götürüb Render Environment-ə əlavə edin.")

def main():
    # Flask-ı arxa fonda işə salırıq
    Thread(target=run_flask).start()

    # Telegram botu işə salırıq
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("title", generate_title))

    print("Bot uğurla başlatıldı...")
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
