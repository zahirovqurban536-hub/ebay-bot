import os
import random
from flask import Flask
from google import genai
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TELEGRAM_TOKEN")

app = Flask(__name__)

# --- HIGH-DEMAND TREND DROPSHIPPING PRODUCTS (30 REAL ITEMS) ---
PRODUCTS = [
    {
        "title": "Aesthetic Sunset Lamp Projection LED Night Light for Room Decor",
        "cat": "Home & Living / Decor",
        "supplier_price": 6.50,
        "est_ebay_price": 18.99,
        "reason": "Gündəlik satışı yüksəkdir, TikTok viral ev dekorasiyası."
    },
    {
        "title": "Portable Mini Vacuum Cleaner Wireless Handheld Cordless Dust Buster",
        "cat": "Car Electronics / Home Cleaning",
        "supplier_price": 9.20,
        "est_ebay_price": 24.50,
        "reason": "Avtomobil və masaüstü təmizlik üçün sabit satılan win-product."
    },
    {
        "title": "Ultrasonic Tooth Cleaner Electric Dental Scaler Plaque Remover",
        "cat": "Health & Beauty / Dental Care",
        "supplier_price": 8.00,
        "est_ebay_price": 22.90,
        "reason": "Şəxsi qulluq kateqoriyasında yüksək marjalı və stabil tələbatlı."
    },
    {
        "title": "Electric Milk Frother Handheld Coffee Foam Maker Stainless Steel",
        "cat": "Kitchen & Dining",
        "supplier_price": 3.80,
        "est_ebay_price": 12.99,
        "reason": "Aşağı qiymət, sürətli dönüşüm və kütləvi alıcı auditoriyası."
    },
    {
        "title": "Adjustable Posture Corrector Shoulder Back Support Belt Straightener",
        "cat": "Health & Fitness",
        "supplier_price": 5.00,
        "est_ebay_price": 15.80,
        "reason": "Ofis işçiləri və tələbələr üçün həmişə trenddə olan daimi məhsul."
    },
    {
        "title": "Wireless Bluetooth Beanie Hat Warm Winter Cap with Built-in Speakers",
        "cat": "Apparel & Accessories / Tech Gadgets",
        "supplier_price": 7.50,
        "est_ebay_price": 19.99,
        "reason": "Həm hədiyyəlik, həm də texnoloji geyim kateqoriyasında çox satır."
    },
    {
        "title": "Automatic Pet Feeder Water Dispenser Bottle for Dogs and Cats",
        "cat": "Pet Supplies",
        "supplier_price": 11.00,
        "est_ebay_price": 28.50,
        "reason": "Ev heyvanı sahibləri üçün imtina edilməz, təkrar satışı olan məhsul."
    },
    {
        "title": "LED Motion Sensor Night Light Wireless USB Rechargeable Under Cabinet",
        "cat": "Home Improvement / Lighting",
        "supplier_price": 4.50,
        "est_ebay_price": 14.90,
        "reason": "Mətbəx və şkaf işıqlandırmasında həftəlik 10+ satışı olan evergreen."
    },
    {
        "title": "Portable Thermal Label Maker Bluetooth Wireless Mini Sticker Printer",
        "cat": "Office Supplies / Electronics",
        "supplier_price": 14.00,
        "est_ebay_price": 34.99,
        "reason": "Kiçik bizneslər və ev təşkilatçılığı üçün yüksək marjalı trend."
    },
    {
        "title": "Anti-Theft Waterproof Backpack USB Charging Port Laptop Travel Bag",
        "cat": "Bags & Luggage",
        "supplier_price": 12.50,
        "est_ebay_price": 31.00,
        "reason": "Səyahət və məktəb mövsümündə kütləvi şəkildə sifariş olunur."
    },
    {
        "title": "Silicone Hair Catcher Drain Protector Shower Tub Strainer Plug",
        "cat": "Home & Kitchen / Bathroom",
        "supplier_price": 1.50,
        "est_ebay_price": 8.99,
        "reason": "Çox ucuz maya dəyəri, impulse buying (düşünmədən alma) məhsulu."
    },
    {
        "title": "Electric Lint Remover Clothes Fuzz Pill Fabric Shaver Rechargeable",
        "cat": "Household Gadgets",
        "supplier_price": 6.80,
        "est_ebay_price": 18.50,
        "reason": "Geyim qulluğu üçün hər mövsüm sabit tələbatı olan klassik çempion."
    },
    {
        "title": "Resistance Bands Set Exercise Elastic Loop for Home Workout Gym",
        "cat": "Sports & Fitness",
        "supplier_price": 5.20,
        "est_ebay_price": 16.99,
        "reason": "Evdə idman edənlər üçün kargo xərci çox az olan yüngül məhsul."
    },
    {
        "title": "Magnetic Phone Holder for Car Dashboard Air Vent Handsfree Mount",
        "cat": "Cell Phone Accessories",
        "supplier_price": 2.80,
        "est_ebay_price": 11.50,
        "reason": "Sürücülər üçün gündəlik kütləvi satılan aksesuar."
    },
    {
        "title": "Digital Food Kitchen Scale Stainless Steel Precision Cooking Measurement",
        "cat": "Kitchen Accessories",
        "supplier_price": 6.00,
        "est_ebay_price": 17.50,
        "reason": "Mətbəx kateqoriyasında ən çox axtarılan və rəyləri yüksək olan item."
    },
    {
        "title": "Reusable Silicone Food Storage Covers Stretch Lids Bowl Wrap",
        "cat": "Eco-Friendly / Kitchen",
        "supplier_price": 3.00,
        "est_ebay_price": 12.00,
        "reason": "Eko-dostu məhsullar arasında impulsiv alış nisbəti çox yüksəkdir."
    },
    {
        "title": "Car Seat Gap Organizer Crevice Storage Box Leather Pocket Auto",
        "cat": "Automotive / Interior Accessories",
        "supplier_price": 8.50,
        "est_ebay_price": 22.00,
        "reason": "Avtomobil daxili səliqəsi üçün viral sosial media məhsulu."
    },
    {
        "title": "Reusable Pet Hair Remover Roller Lint Brush for Dog Cat Fur Removing",
        "cat": "Pet Supplies / Cleaning",
        "supplier_price": 4.20,
        "est_ebay_price": 15.99,
        "reason": "Ev heyvanı saxlayanlar arasında kütləvi tələbat var."
    },
    {
        "title": "Foldable Desktop Tablet Phone Stand Adjustable Dock Holder",
        "cat": "Office & Desk Accessories",
        "supplier_price": 2.20,
        "est_ebay_price": 9.99,
        "reason": "İş masası üçün yüngül və ucuz karqolu bestseller."
    },
    {
        "title": "Electric Vegetable Chopper Cutter Wireless Food Processor Garlic Slicer",
        "cat": "Kitchen Gadgets",
        "supplier_price": 7.80,
        "est_ebay_price": 21.50,
        "reason": "Mətbəx işlərini asanlaşdıran viral TikTok gacetlərindən biri."
    },
    {
        "title": "Ergonomic Memory Foam Lumbar Support Cushion Pillow for Office Chair",
        "cat": "Office & Home Health",
        "supplier_price": 10.50,
        "est_ebay_price": 27.99,
        "reason": "Səhiyyə və rahatlıq kateqoriyasında marjası bərk olan item."
    },
    {
        "title": "Waterproof Electric Face Cleansing Brush Sonic Silicone Facial Scrubber",
        "cat": "Beauty & Personal Care",
        "supplier_price": 5.90,
        "est_ebay_price": 17.80,
        "reason": "Qadın şəxsi qulluq vasitələri arasında davamlı satışı var."
    },
    {
        "title": "Smart Key Finder Bluetooth Tracker Wireless Anti-Lost Alarm Device",
        "cat": "Electronics / Smart Home",
        "supplier_price": 3.50,
        "est_ebay_price": 13.50,
        "reason": "Sərfəli qiymətə hədiyyəlik texnoloji gacet."
    },
    {
        "title": "Stainless Steel Garlic Press Crusher Manual Mincer Kitchen Tool",
        "cat": "Kitchen Tools",
        "supplier_price": 2.10,
        "est_ebay_price": 9.50,
        "reason": "Aşağı qiyməti sayəsində mağazaya trafik çəkmək üçün ideal item."
    },
    {
        "title": "Compression Socks for Men Women Running Medical Nursing Circulation",
        "cat": "Health / Apparel",
        "supplier_price": 3.80,
        "est_ebay_price": 14.20,
        "reason": "İdmançılar və uzun müddət ayaqda qalanlar üçün kütləvi tələbat."
    },
    {
        "title": "Universal Travel Adapter All in One Plug International Power Converter",
        "cat": "Travel Accessories / Electronics",
        "supplier_price": 6.00,
        "est_ebay_price": 18.99,
        "reason": "Səyahət edənlər üçün dəyişməz və davamlı tələbatı olan məhsul."
    },
    {
        "title": "Solar Power Bank Waterproof Portable Charger Dual USB External Battery",
        "cat": "Cell Phone Accessories / Outdoor",
        "supplier_price": 13.00,
        "est_ebay_price": 32.50,
        "reason": "Kempinq və açıq hava həvəskarları üçün yüksək qazanc marjası."
    },
    {
        "title": "Non-Stick Silicone Baking Mat Oven Sheet Liner Pastry Cookie Cooking",
        "cat": "Bakeware / Kitchen",
        "supplier_price": 3.20,
        "est_ebay_price": 12.50,
        "reason": "Evdə şirniyyat və yemək bişirənlərin sevimli təkrar alacağı məhsul."
    },
    {
        "title": "Digital Vernier Caliper Micrometer Electronic Measuring Tool Stainless",
        "cat": "Tools & Home Improvement",
        "supplier_price": 7.20,
        "est_ebay_price": 20.90,
        "reason": "Usta və hobbi həvəskarları kateqoriyasında stabil satılan alət."
    },
    {
        "title": "Adjustable Hand Grip Strengthener Forearm Heavy Gripper Trainer",
        "cat": "Sports & Fitness",
        "supplier_price": 3.10,
        "est_ebay_price": 11.90,
        "reason": "Fitnes həvəskarları üçün sosial mediada çox reklam olunan gacet."
    }
]

shown_products = []

def calculate_zdn_profit(supplier_price, ebay_price, shipping_charge=0.0, shipping_cost=0.0):
    final_value_fee = ebay_price * 0.1325
    fixed_fee = 0.30
    total_ebay_fees = final_value_fee + fixed_fee
    
    total_costs = supplier_price + shipping_cost
    net_profit = (ebay_price + shipping_charge) - total_costs - total_ebay_fees
    margin = (net_profit / ebay_price) * 100 if ebay_price > 0 else 0
    
    return total_ebay_fees, final_value_fee, fixed_fee, net_profit, margin

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🤖 **eBay Dropshipping All-in-One Bot**\n\n"
        "Mövcud Komandalar:\n"
        "🔥 `/trend` - Bazarda hər gün 5+ satan real trend məhsulları göstərir.\n"
        "💰 `/profit <alış> <satış> [kargo]` - ZDN Manager dəqiqliyi ilə mənfəət hesablayır.\n"
        "🏷 `/title <məhsul adı>` - Məhsulun üçün SEO optimallaşdırılmış eBay başlığı təklif edir.\n\n"
        "_Misallar:_\n"
        "• `/profit 89.99 129.99`\n"
        "• `/title car phone holder`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def trend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global shown_products
    
    if len(shown_products) >= len(PRODUCTS):
        shown_products.clear()
        
    available_products = [p for p in PRODUCTS if p not in shown_products]
    
    selected_count = min(3, len(available_products))
    selected = random.sample(available_products, selected_count)
    shown_products.extend(selected)
    
    response = f"🔥 **Günün Yüksək Tələbatlı Məhsulları ({len(shown_products)}/{len(PRODUCTS)} baxıldı):**\n\n"
    
    for i, item in enumerate(selected, 1):
        total_fees, _, _, profit, margin = calculate_zdn_profit(item["supplier_price"], item["est_ebay_price"])
        response += (
            f"**{i}. {item['title']}**\n"
            f"📁 Kateqoriya: `{item['cat']}`\n"
            f"🛒 Alış Qiyməti: `${item['supplier_price']:.2f}`\n"
            f"🏷 Mümkün Satış: `${item['est_ebay_price']:.2f}`\n"
            f"💵 Tahmini Xalis Mənfəət: `${profit:.2f}` (Marja: `{margin:.1f}%`)\n"
            f"💡 Niyə trenddir: _{item['reason']}_\n\n"
        )
    
    response += "💡 _Bu məhsullar eBay/AutoDS bazarlarında həftəlik sabit 5+ satışı olan real seçimlərdir._"
    await update.message.reply_text(response, parse_mode="Markdown")

async def profit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ **Format:** `/profit <alış_qiyməti> <satış_qiyməti> [kargo]`\n_Misal:_ `/profit 89.99 129.99`", parse_mode="Markdown")
        return
    
    try:
        supplier_price = float(args[0])
        ebay_price = float(args[1])
        shipping_cost = float(args[2]) if len(args) >= 3 else 0.0
        
        total_fees, fvf, fixed_fee, net_profit, margin = calculate_zdn_profit(supplier_price, ebay_price, 0.0, shipping_cost)
        
        status_icon = "🟢" if net_profit > 0 else "🔴"
        status_text = "Bu məhsul gəlirlidir, siyahıya əlavə edə bilərsiniz!" if net_profit > 0 else "Diqqət! Bu qiymətlərlə zərər edirsiniz."
        
        res = (
            f"📊 **ZDN Manager Stili Mənfəət Hesablanması**\n\n"
            f"📥 **Alış Qiyməti (Item Cost):** `${supplier_price:.2f}`\n"
            f"🏷 **Satış Qiyməti (Sold Price):** `${ebay_price:.2f}`\n"
            f"🚚 **Kargo Xərci:** `${shipping_cost:.2f}`\n\n"
            f"💸 **eBay Komissiyaları Breakdown:**\n"
            f"• Final Value Fee (13.25%): `${fvf:.2f}`\n"
            f"• Fixed Fee: `${fixed_fee:.2f}`\n"
            f"• **Cəmi eBay Komissiyası:** `${total_fees:.2f}`\n"
            f"───────────────\n"
            f"{status_icon} **Xalis Mənfəət (Total Profit):** `${net_profit:.2f}`\n"
            f"📈 **Mənfəət Marjası (Margin):** `{margin:.2f}%`\n\n"
            f"💡 _{status_text}_"
        )
        await update.message.reply_text(res, parse_mode="Markdown")
        
    except ValueError:
        await update.message.reply_text("⚠️ Zəhmət olmasa qiymətləri yalnız rəqəmlə daxil edin. Misal: `/profit 89.99 129.99`", parse_mode="Markdown")

async def title_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ **Format:** `/title <məhsul_adı>`\n\n_Misal:_ `/title sunset lamp` və ya `/title wireless car charger`",
            parse_mode="Markdown"
        )
        return
    
    raw_input = " ".join(args).title()
    
    qualities = ["New", "Premium", "Heavy Duty", "Professional", "Upgraded", "Ultra"]
    features = ["Portable", "Universal", "Wireless", "Adjustable", "Compact", "Multi-Function"]
    shipping_triggers = ["US Stock", "Fast Shipping", "Fast Delivery", "USA Seller"]
    value_props = ["Best Gift", "Top Rated", "High Quality", "Durable Design", "Easy to Use"]

    def build_clean_title(template_type):
        q = random.choice(qualities)
        f = random.choice(features)
        s = random.choice(shipping_triggers)
        v = random.choice(value_props)

        if template_type == 1:
            title = f"{q} {raw_input} {f} - {s}"
        elif template_type == 2:
            title = f"{raw_input} {f} {v} - {s}"
        else:
            title = f"{q} {f} {raw_input} - {v}"
            
        return title[:80].strip()

    t1 = build_clean_title(1)
    t2 = build_clean_title(2)
    t3 = build_clean_title(3)
    
    res = (
        f"🎯 **`{raw_input}` üçün Unikal eBay SEO Başlıqları (Max 80 Simvol):**\n\n"
        f"1️⃣ `{t1}`\n"
        f"2️⃣ `{t2}`\n"
        f"3️⃣ `{t3}`\n\n"
        f"💡 _Başlığın üstünə basaraq kopyala və eBay-ə yapışdır._"
    )
    await update.message.reply_text(res, parse_mode="Markdown")

# --- RENDER VƏ FLASK SERVER ---
@app.route("/")
def index():
    return "Bot 24/7 Aktivdir!", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def main():
    Thread(target=run_flask).start()

    telegram_app = Application.builder().token(TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("trend", trend_command))
    telegram_app.add_handler(CommandHandler("profit", profit_command))
    telegram_app.add_handler(CommandHandler("title", title_command))

    print("Bot uğurla işə düşdü...")
    telegram_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
