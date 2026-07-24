import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from google import genai

app = Flask(__name__)

# Environment dəyişənləri
TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini AI Klienti
client = genai.Client(api_key=GEMINI_API_KEY)

# Telegram Bot tətbiqini yaradırıq
telegram_app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salam! Mən sizin eBay Dropshipping köməkçinizəm. 🚀\n\nMəhsul üçün SEO başlıq yaratmaq üçün belə yazın:\n/title bluetooth earbuds")

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

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        await update.message.reply_text(f"🚀 **Təklif Olunan eBay Başlıqları:**\n\n{response.text}")
    except Exception as e:
        await update.message.reply_text(f"Xəta baş verdi: {str(e)}")

# Handleri əlavə edirik
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("title", generate_title))

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    if request.method == "POST":
        asyncio.run(telegram_app.initialize())
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        asyncio.run(telegram_app.process_update(update))
        return "ok", 200
    return "bad request", 400

@app.route("/")
def index():
    return "Bot aktivdir!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
