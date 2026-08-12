import os
import re
import random
import base64
from statistics import mean, median
from threading import Thread
from typing import Any

import requests
from flask import Flask
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================================
# CONFIG
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
EBAY_CLIENT_ID = os.environ.get("EBAY_CLIENT_ID")
EBAY_CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET")

GEMINI_MODEL = "gemini-3.6-flash"
EBAY_MARKETPLACE = "EBAY_US"

MAX_TELEGRAM_LENGTH = 3900
EBAY_TIMEOUT = 30

app = Flask(__name__)

gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ============================================================
# SAMPLE PRODUCT IDEAS
# ============================================================

PRODUCTS = [
    {
        "title": "Calming Pet Bed for Dogs and Cats",
        "cat": "Pet Supplies",
        "supplier_price": 12.00,
        "reason": "Broad pet niche and easy visual demonstration."
    },
    {
        "title": "Portable Mini Vacuum Cleaner Wireless",
        "cat": "Home & Cleaning",
        "supplier_price": 9.20,
        "reason": "Small product with a simple use case."
    },
    {
        "title": "Electric Milk Frother Handheld",
        "cat": "Kitchen & Dining",
        "supplier_price": 3.80,
        "reason": "Low-cost kitchen accessory with broad audience."
    },
    {
        "title": "LED Motion Sensor Night Light",
        "cat": "Home Improvement / Lighting",
        "supplier_price": 4.50,
        "reason": "Useful household product with an easy use case."
    },
    {
        "title": "Portable Thermal Label Maker",
        "cat": "Office / Electronics",
        "supplier_price": 14.00,
        "reason": "Useful for organization and small businesses."
    },
    {
        "title": "Magnetic Phone Holder for Car",
        "cat": "Cell Phone Accessories",
        "supplier_price": 2.80,
        "reason": "Common automotive accessory with a broad audience."
    },
    {
        "title": "Pet Hair Remover Roller",
        "cat": "Pet Supplies / Cleaning",
        "supplier_price": 4.20,
        "reason": "Easy-to-demonstrate cleaning product."
    },
    {
        "title": "Foldable Desktop Phone Stand",
        "cat": "Office Accessories",
        "supplier_price": 2.20,
        "reason": "Small and inexpensive accessory."
    },
]

shown_products = []

# ============================================================
# GENERAL HELPERS
# ============================================================

def split_telegram_text(text: str, max_length: int = MAX_TELEGRAM_LENGTH):
    """Split long text into Telegram-safe chunks."""
    if not text:
        return [""]

    chunks = []
    remaining = str(text)

    while len(remaining) > max_length:
        cut = remaining.rfind("\n", 0, max_length)
        if cut < int(max_length * 0.60):
            cut = remaining.rfind(" ", 0, max_length)
        if cut < int(max_length * 0.60):
            cut = max_length

        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


async def send_long_message(update: Update, text: str):
    for chunk in split_telegram_text(text):
        await update.message.reply_text(chunk)


def clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def money(value: float) -> str:
    return f"${value:,.2f}"


def safe_float(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_title(title: str) -> str:
    return " ".join(clean_text(title).lower().split())


# ============================================================
# GEMINI "BRAIN"
# ============================================================

def ask_ai(prompt: str) -> str:
    """Send one request to Gemini."""
    if not gemini_client:
        raise RuntimeError("GEMINI_API_KEY tapılmadı.")

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    answer = clean_text(getattr(response, "text", ""), "")

    if not answer:
        raise RuntimeError("Gemini boş cavab qaytardı.")

    return answer


def ai_product_brain(
    keyword: str,
    ebay_report: str,
    score: int,
    decision: str,
    data_confidence: str,
) -> str:
    """
    The main AI research brain.

    Important:
    It is instructed not to invent sold counts, supplier prices,
    sell-through rates or trends that are not present in the data.
    """

    prompt = f"""
Sən eBay US dropshipping üçün peşəkar product-research AI beynisən.

MƏHSUL:
{keyword}

REAL eBAY BROWSE API HESABATI:
{ebay_report}

SİSTEM SCORE:
{score}/100

SİSTEM QƏRARI:
{decision}

DATA CONFIDENCE:
{data_confidence}

SƏNİN ƏSAS VƏZİFƏN:
Real eBay listing məlumatını şərh et və dropshipping baxımından
düşünülmüş, dürüst qərar ver.

ÇOX VACİB:
- Listing sayı satış sayı deyil.
- Seller feedback satış sayı deyil.
- Sold count verilməyibsə uydurma.
- Sell-through verilməyibsə uydurma.
- Supplier qiyməti verilməyibsə uydurma.
- Trend datası verilməyibsə "Trend sübut olunmayıb" yaz.
- Mənfəət üçün supplier qiyməti yoxdursa rəqəm uydurma.
- Məhsulun elektrik, batareya, kövrəklik, ölçü və qaytarılma
  risklərini yalnız məhsul məlumatından əsaslandır.
- Bahalı outlier qiymətləri normal qiymət kimi qəbul etmə.
- Çox aşağı qiymətli rəqiblər varsa qiymət təzyiqini qeyd et.
- Çox oxşar listinglər varsa rəqabət kimi qeyd et.
- Sistem score-unu dəyişmə.
- Sistem qərarını dəyişmə.
- Özündən statistika uydurma.
- "Çox satılır", "viral", "trenddir" kimi sözləri yalnız sübut
  varsa istifadə et.

Cavabı Azərbaycan dilində ver.

FORMAT:

🧠 AI PRODUCT BRAIN

📦 Məhsul:
{keyword}

🇺🇸 REAL EBAY BAZARI
- Listing sayı:
- Minimum qiymət:
- Maksimum qiymət:
- Orta qiymət:
- Median qiymət:

🏆 RƏQABƏT
- Aşağı / Orta / Yüksək
- Səbəb:

💰 QİYMƏT STRATEGİYASI
- Real bazar aralığı:
- Aşağı qiymət təzyiqi:
- Outlier qiymətlər:

👥 SELLER MÜHİTİ
- Seller feedback barədə nə görünür:
- Güclü seller rəqabəti varmı:

📈 SATIŞ POTENSİALI
Real sold count yoxdursa satış sayı iddia etmə.
Yalnız bazar rəqabəti və qiymət siqnallarına əsaslanan
potensialı izah et.

⚠️ RİSKLƏR
- Məhsul riski:
- Rəqabət riski:
- Qiymət riski:
- Data çatışmazlığı:

🎯 PRODUCT SCORE:
{score}/100

📌 QƏRAR:
{decision}

💡 SON FİKİR:
Məhsulu dropshipping üçün qısa və dürüst şəkildə
GO / MAYBE / NO-GO məntiqi ilə izah et.
"""

    return ask_ai(prompt)


# ============================================================
# PROFIT CALCULATOR
# ============================================================

def calculate_profit(
    supplier_price: float,
    ebay_price: float,
    shipping_cost: float = 0.0,
    shipping_charge: float = 0.0,
):
    """
    Simplified eBay fee estimate used by this bot.

    Note:
    This is a research estimate, not a promise of the exact final
    eBay invoice. Actual fees can vary by category/account.
    """

    final_value_fee = ebay_price * 0.1325
    fixed_fee = 0.30

    total_ebay_fees = final_value_fee + fixed_fee
    total_costs = supplier_price + shipping_cost

    net_profit = (
        ebay_price
        + shipping_charge
        - total_costs
        - total_ebay_fees
    )

    margin = (
        (net_profit / ebay_price) * 100
        if ebay_price > 0
        else 0
    )

    return (
        total_ebay_fees,
        final_value_fee,
        fixed_fee,
        net_profit,
        margin,
    )


# ============================================================
# EBAY OAUTH
# ============================================================

def get_ebay_application_token() -> str:
    if not EBAY_CLIENT_ID or not EBAY_CLIENT_SECRET:
        raise RuntimeError(
            "EBAY_CLIENT_ID və ya EBAY_CLIENT_SECRET yoxdur."
        )

    credentials = f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}"

    encoded_credentials = base64.b64encode(
        credentials.encode("utf-8")
    ).decode("utf-8")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_credentials}",
    }

    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope",
    }

    response = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers=headers,
        data=data,
        timeout=EBAY_TIMEOUT,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "eBay OAuth xətası: "
            f"{response.status_code} "
            f"{response.text[:700]}"
        )

    result = response.json()
    token = result.get("access_token")

    if not token:
        raise RuntimeError("eBay access token alınmadı.")

    return token


# ============================================================
# EBAY SEARCH
# ============================================================

def ebay_search_products(keyword: str, limit: int = 20) -> dict:
    token = get_ebay_application_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": EBAY_MARKETPLACE,
    }

    params = {
        "q": keyword,
        "limit": min(max(limit, 1), 50),
    }

    response = requests.get(
        "https://api.ebay.com/buy/browse/v1/item_summary/search",
        headers=headers,
        params=params,
        timeout=EBAY_TIMEOUT,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "eBay Search xətası: "
            f"{response.status_code} "
            f"{response.text[:900]}"
        )

    return response.json()


# ============================================================
# EBAY DATA EXTRACTION
# ============================================================

def extract_ebay_data(data: dict) -> dict:
    items = data.get("itemSummaries") or []

    total = safe_float(data.get("total")) or 0
    total = int(total)

    prices = []
    sellers = []
    titles = []
    locations = []

    for item in items:
        if not isinstance(item, dict):
            continue

        title = clean_text(item.get("title"))
        if title:
            titles.append(title)

        price_data = item.get("price") or {}

        if isinstance(price_data, dict):
            price = safe_float(price_data.get("value"))
        else:
            price = safe_float(price_data)

        if price is not None and price >= 0:
            prices.append(price)

        seller = item.get("seller") or {}

        if isinstance(seller, dict):
            feedback = safe_float(seller.get("feedbackScore"))
            feedback_percentage = seller.get("feedbackPercentage")
        else:
            feedback = None
            feedback_percentage = None

        if feedback is not None:
            sellers.append(feedback)

        location = item.get("itemLocation") or {}

        if isinstance(location, dict):
            city = clean_text(location.get("city"))
            country = clean_text(location.get("country"))
            location_text = ", ".join(
                x for x in [city, country] if x
            )
            if location_text:
                locations.append(location_text)

    return {
        "total_listings": total,
        "prices": prices,
        "sellers": sellers,
        "titles": titles,
        "locations": locations,
        "items": items,
    }


# ============================================================
# PRODUCT SCORE
# ============================================================

def calculate_product_research_score(
    total_listings: int,
    prices: list,
    sellers: list,
    titles: list,
):
    score = 100
    breakdown = []

    # Competition from listing count.
    if total_listings <= 500:
        penalty = 0
    elif total_listings <= 1500:
        penalty = 5
    elif total_listings <= 3000:
        penalty = 12
    elif total_listings <= 10000:
        penalty = 22
    elif total_listings <= 20000:
        penalty = 30
    else:
        penalty = 38

    score -= penalty
    breakdown.append(f"Listing rəqabəti: -{penalty}")

    # Low-price pressure.
    if prices:
        minimum = min(prices)

        if minimum < 5:
            penalty = 18
        elif minimum < 10:
            penalty = 12
        elif minimum < 15:
            penalty = 6
        else:
            penalty = 0

        score -= penalty
        breakdown.append(
            f"Aşağı qiymət təzyiqi: -{penalty}"
        )

    # Price spread.
    if len(prices) >= 2:
        minimum = min(prices)
        maximum = max(prices)

        if minimum > 0:
            ratio = maximum / minimum

            if ratio <= 3:
                penalty = 0
            elif ratio <= 6:
                penalty = 3
            elif ratio <= 10:
                penalty = 6
            else:
                penalty = 10

            score -= penalty
            breakdown.append(
                f"Qiymət dəyişkənliyi: -{penalty}"
            )

    # Strong seller competition.
    valid_sellers = [
        s for s in sellers
        if isinstance(s, (int, float)) and s >= 0
    ]

    if valid_sellers:
        strong = sum(
            1 for s in valid_sellers
            if s >= 10000
        )

        ratio = strong / len(valid_sellers)

        if ratio >= 0.70:
            penalty = 12
        elif ratio >= 0.40:
            penalty = 8
        elif ratio >= 0.20:
            penalty = 4
        else:
            penalty = 0

        score -= penalty
        breakdown.append(
            f"Güclü seller rəqabəti: -{penalty}"
        )

    # Exact duplicate titles.
    normalized_titles = [
        normalize_title(t)
        for t in titles
        if normalize_title(t)
    ]

    if normalized_titles:
        counts = {}

        for title in normalized_titles:
            counts[title] = counts.get(title, 0) + 1

        duplicates = sum(
            count - 1
            for count in counts.values()
            if count > 1
        )

        duplicate_ratio = (
            duplicates / len(normalized_titles)
        )

        if duplicate_ratio >= 0.50:
            penalty = 10
        elif duplicate_ratio >= 0.30:
            penalty = 7
        elif duplicate_ratio >= 0.15:
            penalty = 4
        elif duplicate_ratio >= 0.05:
            penalty = 2
        else:
            penalty = 0

        score -= penalty
        breakdown.append(
            f"Təkrarlanan listinglər: -{penalty}"
        )

    score = max(0, min(100, round(score)))

    if score >= 70:
        decision = "🟢 GO"
    elif score >= 50:
        decision = "🟡 MAYBE"
    else:
        decision = "🔴 NO-GO"

    if total_listings > 0 and prices:
        data_confidence = "🟢 YÜKSƏK"
    elif total_listings > 0:
        data_confidence = "🟡 ORTA"
    else:
        data_confidence = "🔴 AŞAĞI"

    return score, decision, data_confidence, breakdown


# ============================================================
# EBAY REPORT FORMATTER
# ============================================================

def format_ebay_results(data: dict) -> str:
    extracted = extract_ebay_data(data)

    items = extracted["items"]
    total = extracted["total_listings"]
    prices = extracted["prices"]

    if not items:
        return "❌ eBay-də bu axtarış üçün listing tapılmadı."

    lines = [
        "🔎 REAL eBAY US NƏTİCƏLƏRİ",
        "",
        f"📦 Listing sayı: {total:,}",
        "",
    ]

    for index, item in enumerate(items[:10], 1):
        title = clean_text(
            item.get("title"),
            "Adsız məhsul"
        )

        price_data = item.get("price") or {}

        if isinstance(price_data, dict):
            value = safe_float(price_data.get("value"))
            currency = clean_text(
                price_data.get("currency"),
                "USD"
            )
        else:
            value = safe_float(price_data)
            currency = "USD"

        if value is not None:
            price_text = f"${value:.2f} {currency}"
        else:
            price_text = "N/A"

        seller = item.get("seller") or {}

        if isinstance(seller, dict):
            feedback = seller.get("feedbackScore", "N/A")
            feedback_pct = seller.get(
                "feedbackPercentage",
                "N/A"
            )
        else:
            feedback = "N/A"
            feedback_pct = "N/A"

        location = item.get("itemLocation") or {}

        if isinstance(location, dict):
            city = clean_text(
                location.get("city"),
                "Unknown"
            )
        else:
            city = "Unknown"

        lines.append(
            f"{index}. {title}\n"
            f"💵 Qiymət: {price_text}\n"
            f"👤 Seller feedback: {feedback} / {feedback_pct}\n"
            f"📍 Location: {city}\n"
        )

    if prices:
        lines.append(
            f"📊 İlk {len(prices)} qiymətin orta qiyməti: "
            f"${mean(prices):.2f}"
        )
        lines.append(
            f"📉 Median qiymət: ${median(prices):.2f}"
        )

    lines.append("")
    lines.append(
        "⚠️ Browse API bu nəticədə sold count və "
        "sell-through məlumatını avtomatik vermir."
    )

    return "\n".join(lines)


# ============================================================
# START
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = (
        "🤖 eBay Dropshipping AI Brain\n\n"
        "Komandalar:\n\n"
        "🔥 /trend - AI məhsul ideyaları\n"
        "🔎 /ebay - Real eBay US axtarışı\n"
        "🧠 /analyze - Dərin AI məhsul analizi\n"
        "💰 /profit - Profit hesabla\n"
        "🏷 /title - 3 eBay title yarat\n"
        "🤖 /ai - Ümumi AI köməkçisi\n\n"
        "Misallar:\n"
        "/ebay calming pet bed\n"
        "/analyze electric milk frother\n"
        "/profit 12 29.99 5\n"
        "/title calming pet bed\n"
        "/ai eBay dropshipping üçün məhsul ideyası ver"
    )

    await update.message.reply_text(text)


# ============================================================
# TREND
# ============================================================

async def trend_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    global shown_products

    # If AI is available, use the stronger product-brain prompt.
    if gemini_client:
        prompt = """
Sən eBay US dropshipping product research AI-sən.

Mənə 5 potensial məhsul ideyası ver.

Qaydalar:
- Məhsul adlarını ingiliscə yaz.
- ABŞ eBay bazarı üçün düşün.
- Kiçik, asan göndərilən və vizual izahı olan məhsullara üstünlük ver.
- Elektronika, batareya, kövrək və yüksək return riskli məhsullara
  ehtiyatla yanaş.
- Uydurma satış sayı, sold count və sell-through rəqəmi yazma.
- "Viral" və "trend" sözlərini sübut olmadan fakt kimi yazma.
- Hər məhsul üçün niyə araşdırmağa dəyər olduğunu yaz.
- Supplier qiyməti bilmirsənsə qiymət uydurma.
- Cavabı Azərbaycan dilində ver.

Format:
1. Product:
Category:
Why research:
Main risk:
"""

        try:
            answer = ask_ai(prompt)
            await send_long_message(
                update,
                "🔥 AI PRODUCT IDEAS\n\n" + answer
            )
            return
        except Exception as error:
            print("Trend AI error:", repr(error))

    # Fallback local ideas.
    if len(shown_products) >= len(PRODUCTS):
        shown_products.clear()

    available = [
        p for p in PRODUCTS
        if p not in shown_products
    ]

    selected = random.sample(
        available,
        min(3, len(available))
    )

    shown_products.extend(selected)

    response = "🔥 MƏHSUL İDEYALARI\n\n"

    for index, product in enumerate(selected, 1):
        response += (
            f"{index}. {product['title']}\n"
            f"📁 {product['cat']}\n"
            f"🛒 Supplier: ${product['supplier_price']:.2f}\n"
            f"💡 {product['reason']}\n\n"
        )

    response += (
        "⚠️ Bunlar ideyalardır, real satış statistikası deyil.\n"
        "Real bazarı yoxlamaq üçün /ebay məhsul adı"
    )

    await update.message.reply_text(response)


# ============================================================
# EBAY COMMAND
# ============================================================

async def ebay_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Format:\n\n"
            "/ebay calming pet bed\n\n"
            "və ya:\n"
            "/ebay electric milk frother"
        )
        return

    keyword = " ".join(context.args)

    wait = await update.message.reply_text(
        "🔎 REAL eBay US axtarılır...\n"
        "🧠 AI brain məlumatları analiz edir...\n"
        "⏳ Bir az gözlə..."
    )

    try:
        data = ebay_search_products(
            keyword,
            limit=20
        )

        extracted = extract_ebay_data(data)

        score, decision, confidence, breakdown = (
            calculate_product_research_score(
                extracted["total_listings"],
                extracted["prices"],
                extracted["sellers"],
                extracted["titles"],
            )
        )

        report = format_ebay_results(data)

        if gemini_client:
            try:
                final_response = ai_product_brain(
                    keyword,
                    report,
                    score,
                    decision,
                    confidence,
                )
            except Exception as ai_error:
                print("eBay AI error:", repr(ai_error))

                final_response = (
                    report
                    + "\n\n"
                    + f"🎯 PRODUCT SCORE: {score}/100\n"
                    + f"📌 NƏTİCƏ: {decision}\n"
                    + f"📊 DATA CONFIDENCE: {confidence}"
                )
        else:
            final_response = (
                report
                + "\n\n"
                + f"🎯 PRODUCT SCORE: {score}/100\n"
                + f"📌 NƏTİCƏ: {decision}\n"
                + f"📊 DATA CONFIDENCE: {confidence}"
            )

        try:
            await wait.delete()
        except Exception:
            pass

        await send_long_message(
            update,
            final_response
        )

    except Exception as error:
        print("eBay error:", repr(error))

        try:
            await wait.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "❌ eBay API xətası:\n\n"
            + str(error)[:1500]
        )


# ============================================================
# ANALYZE COMMAND
# ============================================================

async def analyze_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Misal:\n"
            "/analyze electric milk frother\n\n"
            "və ya:\n"
            "/analyze wireless phone holder"
        )
        return

    keyword = " ".join(context.args)

    if not gemini_client:
        await update.message.reply_text(
            "❌ GEMINI_API_KEY tapılmadı."
        )
        return

    wait = await update.message.reply_text(
        "🧠 AI PRODUCT BRAIN işə düşdü...\n"
        "🔎 Real eBay məlumatları yığılır...\n"
        "📊 Rəqabət və qiymət analiz edilir..."
    )

    try:
        data = ebay_search_products(
            keyword,
            limit=30
        )

        extracted = extract_ebay_data(data)

        score, decision, confidence, breakdown = (
            calculate_product_research_score(
                extracted["total_listings"],
                extracted["prices"],
                extracted["sellers"],
                extracted["titles"],
            )
        )

        report = format_ebay_results(data)

        final_response = ai_product_brain(
            keyword,
            report,
            score,
            decision,
            confidence,
        )

        try:
            await wait.delete()
        except Exception:
            pass

        await send_long_message(
            update,
            final_response
        )

    except Exception as error:
        print("Analyze error:", repr(error))

        try:
            await wait.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "❌ Analiz xətası:\n\n"
            + str(error)[:1500]
        )


# ============================================================
# PROFIT COMMAND
# ============================================================

async def profit_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    args = context.args

    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ Format:\n\n"
            "/profit <alış> <satış> [shipping]\n\n"
            "Misal:\n"
            "/profit 12 29.99 5"
        )
        return

    try:
        supplier_price = float(args[0])
        ebay_price = float(args[1])
        shipping_cost = (
            float(args[2])
            if len(args) >= 3
            else 0.0
        )

        if (
            supplier_price < 0
            or ebay_price < 0
            or shipping_cost < 0
        ):
            await update.message.reply_text(
                "❌ Qiymətlər mənfi ola bilməz."
            )
            return

        (
            total_fees,
            final_value_fee,
            fixed_fee,
            net_profit,
            margin,
        ) = calculate_profit(
            supplier_price,
            ebay_price,
            shipping_cost,
        )

        if net_profit > 0:
            status = "🟢 GO"
        elif net_profit == 0:
            status = "🟡 BREAK-EVEN"
        else:
            status = "🔴 NO-GO"

        response = (
            "📊 PROFİT ANALİZİ\n\n"
            f"🛒 Supplier: ${supplier_price:.2f}\n"
            f"🏷 eBay satış: ${ebay_price:.2f}\n"
            f"🚚 Shipping: ${shipping_cost:.2f}\n\n"
            "💸 eBay xərcləri:\n"
            f"• Final Value Fee: ${final_value_fee:.2f}\n"
            f"• Fixed Fee: ${fixed_fee:.2f}\n"
            f"• Cəmi eBay xərci: ${total_fees:.2f}\n\n"
            f"💰 Xalis profit: ${net_profit:.2f}\n"
            f"📈 Profit marjası: {margin:.2f}%\n\n"
            f"🎯 Nəticə: {status}\n\n"
            "⚠️ Bu sadələşdirilmiş research hesabıdır; "
            "real eBay fee kateqoriyaya və hesaba görə dəyişə bilər."
        )

        await update.message.reply_text(response)

    except ValueError:
        await update.message.reply_text(
            "❌ Qiymətləri rəqəmlə yaz.\n\n"
            "Misal:\n"
            "/profit 12 29.99 5"
        )


# ============================================================
# TITLE COMMAND
# ============================================================

async def title_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Məhsul adını yaz.\n\n"
            "Misal:\n"
            "/title electric milk frother"
        )
        return

    if not gemini_client:
        await update.message.reply_text(
            "❌ GEMINI_API_KEY tapılmadı."
        )
        return

    product = " ".join(context.args)

    prompt = f"""
Create exactly 3 eBay US product titles for:

{product}

Rules:
- Natural English.
- Maximum 80 characters per title.
- Use only facts supported by the product name.
- Do not invent a brand.
- Do not invent specifications.
- Do not use USA Seller.
- Do not use Top Rated.
- Do not use Best Seller.
- Do not use Best Gift.
- Do not use Fast Shipping.
- Do not use Free Shipping.
- Do not use fake claims such as Premium or Professional.
- Focus on useful eBay search keywords.
- Avoid emojis.
- Avoid unnecessary punctuation.
- Return exactly 3 lines.
- No explanations.
"""

    try:
        answer = ask_ai(prompt)

        raw_titles = [
            line.strip()
            for line in answer.splitlines()
            if line.strip()
        ]

        titles = []

        for title in raw_titles:
            title = re.sub(
                r"^\s*(?:\d+[\.\)\-:]|\-|\*)\s*",
                "",
                title,
            )

            title = " ".join(title.split())
            title = title[:80].strip()

            if title:
                titles.append(title)

        titles = titles[:3]

        if not titles:
            raise RuntimeError(
                "AI title qaytarmadı."
            )

        response = "🏷 EBAY SEO TITLE\n\n"

        for index, title in enumerate(titles, 1):
            response += (
                f"{index}. {title}\n"
                f"📏 {len(title)}/80 simvol\n\n"
            )

        await update.message.reply_text(response)

    except Exception as error:
        print("Title AI error:", repr(error))

        await update.message.reply_text(
            "❌ AI title yaradıla bilmədi:\n"
            + str(error)[:1000]
        )


# ============================================================
# GENERAL AI COMMAND
# ============================================================

async def ai_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Misal:\n"
            "/ai eBay dropshipping üçün 5 məhsul ideyası ver"
        )
        return

    if not gemini_client:
        await update.message.reply_text(
            "❌ GEMINI_API_KEY tapılmadı."
        )
        return

    user_prompt = " ".join(context.args)

    system_prompt = f"""
Sən istifadəçinin eBay dropshipping AI köməkçisisən.

İstifadəçinin sualı:
{user_prompt}

Qaydalar:
- Azərbaycan dilində cavab ver.
- Lazımsız uzun danışma.
- Rəqəm və statistika bilmirsənsə uydurma.
- Sold count və sell-through məlumatı verilməyibsə fakt kimi göstərmə.
- eBay dropshipping üçün praktik cavab ver.
- Məhsul araşdırmasında rəqabət, qiymət, risk və profit
  məntiqini nəzərə al.
"""

    try:
        answer = ask_ai(system_prompt)

        await send_long_message(
            update,
            "🤖 AI BRAIN:\n\n" + answer
        )

    except Exception as error:
        print("Gemini error:", repr(error))

        await update.message.reply_text(
            "❌ AI xətası:\n"
            + str(error)[:1200]
        )


# ============================================================
# HEALTH / FLASK
# ============================================================

@app.route("/")
def index():
    return "eBay Dropshipping AI Bot 24/7 Aktivdir!", 200


@app.route("/health")
def health():
    return {
        "status": "ok",
        "telegram": bool(TELEGRAM_TOKEN),
        "gemini": bool(GEMINI_API_KEY),
        "ebay": bool(
            EBAY_CLIENT_ID and EBAY_CLIENT_SECRET
        ),
    }, 200


def run_flask():
    port = int(
        os.environ.get("PORT", "5000")
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )


# ============================================================
# MAIN
# ============================================================

def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError(
            "TELEGRAM_TOKEN tapılmadı."
        )

    Thread(
        target=run_flask,
        daemon=True,
    ).start()

    telegram_app = (
        Application
        .builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    telegram_app.add_handler(
        CommandHandler("start", start_command)
    )

    telegram_app.add_handler(
        CommandHandler("trend", trend_command)
    )

    telegram_app.add_handler(
        CommandHandler("ebay", ebay_command)
    )

    telegram_app.add_handler(
        CommandHandler("analyze", analyze_command)
    )

    telegram_app.add_handler(
        CommandHandler("profit", profit_command)
    )

    telegram_app.add_handler(
        CommandHandler("title", title_command)
    )

    telegram_app.add_handler(
        CommandHandler("ai", ai_command)
    )

    print("🤖 eBay Dropshipping AI Brain uğurla işə düşdü.")

    telegram_app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
