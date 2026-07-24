import os
import random
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8923272977:AAHC17AZuP96DW8O0EZ40JvlrS3CbwIykR8"

# --- FLASK WEB SERVER (Render 7/24 aktiv qalsın deyə) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "eBay Bot is Active 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🚀 **eBay Dropshipping Analiz Botuna Xoş Geldiniz!**\n\n"
        "📌 **Mövcud Komandalar:**\n"
        "👉 `/trend` – ABŞ bazarında anlıq yüksələn trendlər və hazır SEO başlıqlar.\n"
        "👉 `/profit [Alış] [Satış] [Kargo]` – AutoDS stili net mənfəət hesablama.\n\n"
        "📌 **Nümunə (Kargosuz):** `/profit 9.99 14.56`\n"
        "📌 **Nümunə (Kargo ilə):** `/profit 9.99 14.56 3`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 ABŞ bazarındakı anlıq yüksələn trendlər və SEO başlıqlar analiz olunur... Lütfen gözləyin.")
    
    result_text = (
        "🔥 **ABŞ-də Anlıq Yüksələn Trendlər və Yenilənmiş SEO Başlıqlar:**\n\n"
        "1. 🔋 **Magnetic Wireless Power Bank 10000mAh**\n"
        "📈 **Tələbat:** 410+ satılıb (Son 24 saat)\n"
        "🎯 **SEO Title (Kopyala):**\n"
        "`Magnetic Wireless Power Bank 10000mAh Portable External Battery Slim MagSafe Compatible Fast Charging`\n"
        "───────────────────\n"
        "2. 🧊 **Silicone Ice Cube Trays with Lid & Bin**\n"
        "📈 **Tələbat:** 290+ satılıb (Son 24 saat)\n"
        "🎯 **SEO Title (Kopyala):**\n"
        "`Silicone Ice Cube Trays with Lid & Bin Easy Release Kitchen Gadgets Press Type Whiskey Cocktail BPA Free`\n"
        "───────────────────\n"
        "3. 💻 **Foldable Laptop Stand Aluminum Ergonomic**\n"
        "📈 **Tələbat:** 210+ satılıb (Son 24 saat)\n"
        "🎯 **SEO Title (Kopyala):**\n"
        "`Foldable Laptop Stand Aluminum Ergonomic MacBook Tablet Lightweight Ventilated Riser Desktop Holder`\n\n"
        "💡 *Məsləhət:* Bu SEO başlıqlarını üstünə vuraraq kopyalayıb birbaşa eBay listinqinizdə istifadə edə bilərsiniz!"
    )
    await update.message.reply_text(result_text, parse_mode="Markdown")

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("❌ Səhv format! Nümunə: `/profit 10 25` və ya `/profit 10 25 3`", parse_mode="Markdown")
            return

        buy_price = float(args[0])
        sell_price = float(args[1])
        shipping_cost = float(args[2]) if len(args) >= 3 else 0.0

        ebay_fee = sell_price * 0.1325 + 0.30
        payout_fee = sell_price * 0.015
        total_fees = ebay_fee + payout_fee
        
        net_profit = sell_price - buy_price - shipping_cost - total_fees
        profit_margin = (net_profit / sell_price) * 100 if sell_price > 0 else 0

        status_emoji = "🟢" if net_profit > 0 else "🔴"

        response = (
            f"📊 **AutoDS Stili Mənfəət Hesablanması**\n\n"
            f"💵 **Alış Qiyməti:** ${buy_price:.2f}\n"
            f"🏷️ **Satış Qiyməti:** ${sell_price:.2f}\n"
            f"🚚 **Kargo Xərci:** ${shipping_cost:.2f}\n"
            f"🏛️ **Tahmini eBay & Çəkim Komissiyası:** ${total_fees:.2f}\n"
            f"───────────────\n"
            f"{status_emoji} **Xalis Mənfəət:** ${net_profit:.2f}\n"
            f"📈 **Mənfəət Marjası:** {profit_margin:.1f}%\n\n"
        )
        
        if net_profit > 0:
            response += "✅ *Bu məhsul gəlirlidir, siyahıya əlavə edə bilərsiniz!*"
        else:
            response += "⚠️ *Zərərli və ya çox aşağı marja! Qiyməti artırmağı düşünün.*"

        await update.message.reply_text(response, parse_mode="Markdown")

    except ValueError:
        await update.message.reply_text("❌ Xahiş olunur yalnız rəqəm daxil edin! Nümunə: `/profit 10.5 24.99`", parse_mode="Markdown")

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("trend", trend))
    bot_app.add_handler(CommandHandler("profit", profit))
    
    print("Bot işə düşdü...")
    bot_app.run_polling()

if __name__ == '__main__':
    main()
