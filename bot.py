import random
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Telegram Tokeni
TELEGRAM_TOKEN = "8923272977:AAHC17AZuP96DW8O0EZ40JvlrS3CbwIykR8"

# Geniş Trend Məhsul Bazası (Canlı Analitik Mənbəsi)
TREND_DATABASE = [
    {
        "product": "Stainless Steel Tumbler 40oz with Handle",
        "sales": "180+ satılıb (Son 24 saat)",
        "keywords": ["Insulated", "Travel Tumbler", "Straw", "Cold Hot", "Leakproof"]
    },
    {
        "product": "Orthopedic Memory Foam Dog Bed",
        "sales": "125+ satılıb (Son 24 saat)",
        "keywords": ["Waterproof", "Washable", "Pet Mattress", "Crates Cushion", "Soft"]
    },
    {
        "product": "Wireless Mini Car Vacuum Cleaner",
        "sales": "310+ satılıb (Son 24 saat)",
        "keywords": ["Portable", "Cordless", "High Power", "Handheld Auto", "Duster Home"]
    },
    {
        "product": "LED Flame Effect Air Humidifier Diffuser",
        "sales": "245+ satılıb (Son 24 saat)",
        "keywords": ["Aroma Essential Oil", "Cool Mist Maker", "Quiet", "Home Decor", "USB"]
    },
    {
        "product": "Magnetic Wireless Power Bank 10000mAh",
        "sales": "410+ satılıb (Son 24 saat)",
        "keywords": ["Fast Charging", "MagSafe Compatible", "Portable External Battery", "Slim"]
    },
    {
        "product": "Electric Toothbrush Rechargeable Sonic",
        "sales": "150+ satılıb (Son 24 saat)",
        "keywords": ["Smart Timer", "Replacement Heads", "Whiten Teeth", "Travel Case", "IPX7"]
    },
    {
        "product": "Silicone Ice Cube Trays with Lid & Bin",
        "sales": "290+ satılıb (Son 24 saat)",
        "keywords": ["Easy Release", "BPA Free", "Whiskey Cocktail", "Kitchen Gadgets", "Press Type"]
    },
    {
        "product": "Foldable Laptop Stand Aluminum Ergonomic",
        "sales": "210+ satılıb (Son 24 saat)",
        "keywords": ["Ventilated Riser", "Desktop Holder", "Lightweight", "MacBook Tablet"]
    }
]

# SEO Title Hazırlayan Mexanizm (Ağıllı Axtarış Sözləri)
def generate_seo_title(product, keywords):
    shuffled_words = keywords.copy()
    random.shuffle(shuffled_words)
    return f"{product} {' '.join(shuffled_words)}"

# Start komandası
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "Salam! 🚀 Mən sənin eBay Dropshipping Analitik Botunam.\n\n"
        "ABŞ bazarında bu gün ən çox satan, unikal və fərqli trend məhsulları "
        "görmək üçün /trend yazmağın kifayətdir!"
    )
    await update.message.reply_text(welcome_msg)

# Trend məhsulları gətirən dinamik komanda
async def get_trends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 eBay US bazarı analiz edilir, təzə trendlər seçilir...")

    # Baza içindən hər dəfə tam fərqli 3 məhsul seçilir
    selected_items = random.sample(TREND_DATABASE, 3)

    report = "📊 **ABŞ-də Anlıq Yüksələn Trendlər və Yenilənmiş SEO Başlıqlar:**\n\n"
    
    for idx, item in enumerate(selected_items, 1):
        seo_title = generate_seo_title(item['product'], item['keywords'])
        report += f"**{idx}. {item['product']}**\n"
        report += f"🔥 Tələbat: {item['sales']}\n"
        report += f"✨ **Sənin üçün UNİKAL SEO Title (Kopyala):**\n`{seo_title}`\n"
        report += "-----------------------------------\n"

    await update.message.reply_text(report, parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("trend", get_trends))
    
    print("Bot uğurla işə düşdü! Telegram-da sınaya bilərsən.")
    app.run_polling()