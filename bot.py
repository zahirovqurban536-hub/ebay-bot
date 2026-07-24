import threading
import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Logging konfiqurasiyası
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# /start əmri
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🚀 **eBay Dropshipping Analiz Botuna Xoş Geldiniz!**\n\n"
        "📌 **Mövcud Komandalar:**\n"
        "🔹 `/trend` — ABŞ bazarında ən çox satılan trend məhsulları göstərir.\n"
        "🔹 `/profit [Alış] [Satış] [Kargo]` — AutoDS stili mənfəət hesablayır.\n\n"
        "💡 *Nümunə (Kargosuz):* `/profit 9.99 14.56`\n"
        "💡 *Nümunə (Kargo ilə):* `/profit 9.99 14.56 3`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# /trend əmri (Trend məhsullar)
async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 ABŞ bazarındakı son trendlər analiz olunur... Lütfən gözləyin.")

# /profit əmri (Tam AutoDS Məntiqi və Rahat Quraşdırma)
async def profit_calculator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ **İstifadə qaydası:**\n"
                "`/profit [Alış Qiyməti] [Satış Qiyməti] [Kargo (İstəyə bağlı)]`\n\n"
                "📌 **Nümunə:** `/profit 9.99 14.56`",
                parse_mode="Markdown"
            )
            return

        buy_price = float(args[0])    # 1-ci: Amazon (Alış)
        sell_price = float(args[1])   # 2-ci: eBay (Satış)
        shipping_cost = float(args[2]) if len(args) >= 3 else 0.0

        # AutoDS dəqiq komissiya dərəcəsi (~15.5%)
        ebay_fee = sell_price * 0.155
        total_cost = buy_price + shipping_cost + ebay_fee
        net_profit = sell_price - total_cost
        margin = (net_profit / sell_price) * 100 if sell_price > 0 else 0

        status_emoji = "🟢" if net_profit > 0 else "🔴"

        response = (
            f"📊 **AutoDS Stili Mənfəət Analizi**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💵 **eBay Satış Qiyməti:** ${sell_price:.2f}\n"
            f"🛒 **Amazon Alış Qiyməti:** ${buy_price:.2f}\n"
            f"🚚 **Kargo Xərci:** ${shipping_cost:.2f}\n"
            f"🏛 **eBay Komissiyası (~15.5%):** ${ebay_fee:.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"{status_emoji} **Xalis Qazanc (Net Profit):** ${net_profit:.2f}\n"
            f"📈 **Mənfəət Marjası:** %{margin:.1f}\n"
        )
        
        await update.message.reply_text(response, parse_mode="Markdown")

    except ValueError:
        await update.message.reply_text("⚠️ Rəqəmləri düzgün yazın. (Məsələn: `/profit 9.99 14.56`)")

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("Xəta: BOT_TOKEN tapılmadı!")
        return

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("trend", trend))
    app.add_handler(CommandHandler("profit", profit_calculator))

    print("Bot işə düşdü...")
    threading.Thread(target=run_flask, daemon=True).start()
    app.run_polling()

if __name__ == "__main__":
    main()
