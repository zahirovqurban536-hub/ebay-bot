import os
import logging
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot aktivdir!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salam! Mən sizin eBay Dropshipping Analitik botunuzam. 🚀\n\n"
        "İstifadə edə biləcəyiniz əmrlər:\n"
        "/trend - Ən çox axtarılan kateqoriyalar və trendləri görün\n"
        "/help - Kömək menyusu"
    )

async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🔥 **eBay Dropshipping 2026 Trend Məhsullar & Kateqoriyalar:**\n\n"
        "1. **Elektronika & Aksesuarlar:**\n"
        "   - Wireless Earbuds / Bluetooth Headphones\n"
        "   - Smartwatch Chargers & Straps\n"
        "   - Phone Holder Stand for Cars\n\n"
        "2. **Ev & Mətbəx:**\n"
        "   - Portable Mini Air Coolers\n"
        "   - LED Strip Lights (RGB)\n"
        "   - Silicone Kitchen Utensils\n\n"
        "3. **Şəxsi Qulluq:**\n"
        "   - Hair Clippers & Trimmers\n"
        "   - Posture Corrector Braces\n\n"
        "💡 *Məsləhət:* Bu kateqoriyalarda yüksək reytinqli və sürətli çatdırılması olan təchizatçılara üstünlük verin."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Problem yaranarsa və ya sualınız olarsa, dərhal mənə bildirin!")

def main():
    Thread(target=run_flask).start()

    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("trend", trend))
    bot_app.add_handler(CommandHandler("help", help_command))

    print("Bot uğurla işə düşdü...")
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
