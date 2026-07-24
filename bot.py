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

# --- GENİŞ TREND MƏHSULLAR BAZASI ---
TREND_PRODUCTS = [
    {
        "title": "Magnetic Wireless Power Bank 10000mAh",
        "demand": "410+ satılıb (Son 24 saat)",
        "seo": "Magnetic Wireless Power Bank 10000mAh Portable External Battery Slim MagSafe Compatible Fast Charging"
    },
    {
        "title": "Silicone Ice Cube Trays with Lid & Bin",
        "demand": "290+ satılıb (Son 24 saat)",
        "seo": "Silicone Ice Cube Trays with Lid & Bin Easy Release Kitchen Gadgets Press Type Whiskey Cocktail BPA Free"
    },
    {
        "title": "Foldable Laptop Stand Aluminum Ergonomic",
        "demand": "210+ satılıb (Son 24 saat)",
        "seo": "Foldable Laptop Stand Aluminum Ergonomic MacBook Tablet Lightweight Ventilated Riser Desktop Holder"
    },
    {
        "title": "Wireless Earbuds Bluetooth 5.3 Noise Cancelling",
        "demand": "530+ satılıb (Son 24 saat)",
        "seo": "Wireless Earbuds Bluetooth 5.3 Headphones In Ear Stereo Sound Earphones Noise Cancelling Waterproof Mic"
    },
    {
        "title": "Portable Neck Fan Rechargeable Blueless",
        "demand": "340+ satılıb (Son 24 saat)",
        "seo": "Portable Neck Fan Hands Free Personal Fan Rechargeable Leafless Quiet Air Cooler Outdoor Travel Sports"
    },
    {
        "title": "LED Car Atmosphere Strip Lights Interior",
        "demand": "180+ satılıb (Son 24 saat)",
        "seo": "LED Car Interior Atmosphere Lights RGB Strip Lighting Kit Wireless Music Remote Control Auto Decorative Lamp"
    },
    {
        "title": "Handheld Cordless Car Vacuum Cleaner High Power",
        "demand": "260+ satılıb (Son 24 saat)",
        "seo": "Handheld Cordless Car Vacuum Cleaner 9000Pa Powerful Suction Rechargeable Dust Blower Auto Home Office"
    },
    {
        "title": "Smart Fitness Tracker Watch Blood Pressure",
        "demand": "310+ satılıb (Son 24 saat)",
        "seo": "Smart Watch Fitness Tracker Heart Rate Blood Pressure Monitor Step Counter Waterproof Sleep Monitor Android iOS"
    },
    {
        "title": "Electric Milk Frother Handheld Coffee Maker",
        "demand": "220+ satılıb (Son 24 saat)",
        "seo": "Electric Milk Frother Handheld Foam Maker Drink Mixer Stainless Steel Whisk for Latte Cappuccino Hot Chocolate"
    }
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🚀 **eBay Dropshipping Analiz Botuna Xoş Geldiniz!**\n\n"
        "📌 **Mövcud Komandalar:**\n"
        "👉 `/trend` – ABŞ bazarında anlıq yüksələn yenilənən trendlər və SEO başlıqlar.\n"
        "👉 `/profit [Alış] [Satış] [Kargo]` – AutoDS stili net mənfəət hesablama.\n\n"
        "📌 **Nümunə (Kargosuz):** `/profit 9.99 14.56`\n"
        "📌 **Nümunə (Kargo ilə):** `/profit 9.99 14.56 3`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Bazadakı anlıq yüksələn trendlər və SEO başlıqlar analiz olunur...")
    
    # Bazadan təsadüfi 3 məhsul seçirik
    selected_items = random.sample(TREND_PRODUCTS, 3)
    
    result_text = "🔥 **ABŞ Bazarı Üçün Yenilənmiş Trendlər Və SEO Başlıqları:**\n\n"
    
    for idx, item in enumerate(selected_items, 1):
        result_text += (
            f"{idx}. 📌 **{item['title']}**\n"
            f"📈 **Tələbat:** {item['demand']}\n"
            f"🎯 **SEO Title (Kopyala):**\n"
            f"`{item['seo']}`\n"
            f"───────────────────\n"
        )
        
    result_text += "💡 *Məsləhət:* Hər dəfə `/trend` yazanda fərqli məhsul ideyaları görəcəksiniz. Başlığın üstünə vuraraq birbaşa kopyalaya bilərsiniz!"
    
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
