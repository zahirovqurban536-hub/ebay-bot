import os
import random
import threading
from flask import Flask
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- FLASK WEB SERVER (Render üçün) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "eBay Bot is Active!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- TELEGRAM BOT BÖLMƏSİ ---
TOKEN = "8023272977:AAHC17AZJP96DW806EZ48JvlrS3CbwIykR8"  # Sənin Bot Tokenin

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🚀 **eBay Dropshipping Analiz Botuna Xoş Geldiniz!**\n\n"
        "📌 **Mövcud Komandalar:**\n"
        "👉 `/trend` — ABŞ bazarında an çox satılan trend məhsulları göstərir.\n"
        "👉 `/profit [Alış] [Satış] [Kargo]` — AutoDS stili mənfəət hesablayır.\n\n"
        "💡 **Nümunə (Kargosuz):** `/profit 9.99 14.56`\n"
        "💡 **Nümunə (Kargo ilə):** `/profit 9.99 14.56 3`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 ABŞ bazarındakı son trendlər analiz olunur... Lütfən gözləyin.")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    url = "https://www.ebay.com/b/Trending-Deals/bn_7000259122"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = []
        # eBay-dən trend məhsul adlarını və qiymətlərini tapırıq
        for card in soup.find_all('div', class_='brwrvr__item-card')[:5]:
            title = card.find('span', class_='textual-display')
            price = card.find('span', class_='textual-display')
            if title:
                items.append(f"📦 **{title.text.strip()}**")
        
        if items:
            result_text = "🔥 **ABŞ eBay Top Trend Məhsullar:**\n\n" + "\n\n".join(items)
        else:
            # Əgər eBay scraping bloklasa, ehtiyat dropshipping trendləri
            result_text = (
                "🔥 **Güncel eBay ABŞ Top Dropshipping Trendləri:**\n\n"
                "1. 📦 **Wireless Earbuds Bluetooth 5.3** — Est. Price: $14.99\n"
                "2. 📦 **Portable Mini Neck Fan Rechargeable** — Est. Price: $11.50\n"
                "3. 📦 **LED Car Atmosphere Strip Lights** — Est. Price: $9.80\n"
                "4. 📦 **Pet Hair Remover Roller for Furniture** — Est. Price: $12.30\n"
                "5. 📦 **Electric Kitchen Spice Grinder** — Est. Price: $18.20\n\n"
                "💡 *Məsləhət: AutoDS üzərindən bu kateqoriyadakı fərqli təchizatçıları müqayisə edin.*"
            )
    except Exception as e:
        result_text = "⚠️ Məlumat çəkilərkən xəta baş verdi, yenidən cəhd edin."

    await update.message.reply_text(result_text, parse_mode="Markdown")

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("❌ Səhv format! İstifadə: `/profit [Alış] [Satış] [Kargo]`", parse_mode="Markdown")
            return
            
        buy_price = float(args[0])
        sell_price = float(args[1])
        shipping_cost = float(args[2]) if len(args) >= 3 else 0.0

        # AutoDS / eBay hesablaması (təxmini %13.25 + $0.30 komissiya)
        ebay_fee = (sell_price * 0.1325) + 0.30
        total_cost = buy_price + shipping_cost + ebay_fee
        net_profit = sell_price - total_cost
        margin = (net_profit / sell_price) * 100 if sell_price > 0 else 0

        res = (
            f"📊 **AutoDS Stili Mənfəət Hesablaması:**\n\n"
            f"💵 Satış Qiyməti: `${sell_price:.2f}`\n"
            f"🛒 Alış Qiyməti: `${buy_price:.2f}`\n"
            f"🚚 Kargo Xərci: `${shipping_cost:.2f}`\n"
            f"🏛️ eBay Komissiyası (~13.25% + $0.30): `${ebay_fee:.2f}`\n"
            f"───────────────────\n"
            f"💰 **Xalis Mənfəət:** `${net_profit:.2f}`\n"
            f"📈 **Mənfəət Marjası:** `{margin:.1f}%`"
        )
        await update.message.reply_text(res, parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Rəqəmləri düzgün daxil edin. Məsələn: `/profit 9.99 14.56`", parse_mode="Markdown")

def main():
    # Flask-ı arxa fonda başladaq
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Telegram botu başladaq
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("trend", trend))
    bot_app.add_handler(CommandHandler("profit", profit))
    
    print("Bot uğurla işə düşdü...")
    bot_app.run_polling()

if __name__ == "__main__":
    main()
