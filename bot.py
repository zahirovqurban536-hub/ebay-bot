import os
import random
import base64
import requests

from flask import Flask
from google import genai
from threading import Thread

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

EBAY_CLIENT_ID = os.environ.get("EBAY_CLIENT_ID")
EBAY_CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET")


# =========================================================
# CLIENTS
# =========================================================

app = Flask(__name__)

gemini_client = None

if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)


# =========================================================
# SAMPLE PRODUCT IDEAS
# =========================================================

PRODUCTS = [
    {
        "title": "Calming Pet Bed for Dogs and Cats",
        "cat": "Pet Supplies",
        "supplier_price": 12.00,
        "reason": "Pet niche has broad demand, but competition must be checked."
    },
    {
        "title": "Portable Mini Vacuum Cleaner Wireless",
        "cat": "Home & Cleaning",
        "supplier_price": 9.20,
        "reason": "Small and relatively easy to ship."
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
        "reason": "Useful household product with simple use case."
    },
    {
        "title": "Portable Thermal Label Maker",
        "cat": "Office Supplies / Electronics",
        "supplier_price": 14.00,
        "reason": "Useful for small businesses and organization."
    },
    {
        "title": "Magnetic Phone Holder for Car",
        "cat": "Cell Phone Accessories",
        "supplier_price": 2.80,
        "reason": "Common automotive accessory."
    },
    {
        "title": "Pet Hair Remover Roller",
        "cat": "Pet Supplies / Cleaning",
        "supplier_price": 4.20,
        "reason": "Useful for pet owners and easy to demonstrate."
    },
    {
        "title": "Foldable Desktop Phone Stand",
        "cat": "Office Accessories",
        "supplier_price": 2.20,
        "reason": "Small, inexpensive and easy to ship."
    },
]


shown_products = []


# =========================================================
# PROFIT CALCULATOR
# =========================================================

def calculate_profit(
    supplier_price,
    ebay_price,
    shipping_cost=0.0,
    shipping_charge=0.0
):
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


# =========================================================
# EBAY APPLICATION TOKEN
# =========================================================

def get_ebay_application_token():
    """
    Gets a fresh eBay Application OAuth token.

    IMPORTANT:
    The Client ID and Client Secret are read from
    environment variables and are never hard-coded.
    """

    if not EBAY_CLIENT_ID or not EBAY_CLIENT_SECRET:
        raise RuntimeError(
            "EBAY_CLIENT_ID və ya EBAY_CLIENT_SECRET yoxdur."
        )

    credentials = (
        f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}"
    )

    encoded_credentials = base64.b64encode(
        credentials.encode("utf-8")
    ).decode("utf-8")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_credentials}",
    }

    data = {
        "grant_type": "client_credentials",
        "scope": (
            "https://api.ebay.com/oauth/api_scope"
        ),
    }

    response = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers=headers,
        data=data,
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"eBay OAuth xətası: "
            f"{response.status_code} "
            f"{response.text[:500]}"
        )

    result = response.json()

    token = result.get("access_token")

    if not token:
        raise RuntimeError(
            "eBay access token alınmadı."
        )

    return token


# =========================================================
# EBAY PRODUCT SEARCH
# =========================================================

def ebay_search_products(
    keyword,
    limit=10
):
    """
    Searches real eBay US listings using Browse API.
    """

    token = get_ebay_application_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
    }

    params = {
        "q": keyword,
        "limit": min(limit, 50),
    }

    response = requests.get(
        "https://api.ebay.com/buy/browse/v1/item_summary/search",
        headers=headers,
        params=params,
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"eBay Search xətası: "
            f"{response.status_code} "
            f"{response.text[:700]}"
        )

    return response.json()


# =========================================================
# EBAY SEARCH FORMATTER
# =========================================================

def format_ebay_results(data):
    items = data.get("itemSummaries", [])

    if not items:
        return (
            "❌ eBay-də bu axtarış üçün məhsul tapılmadı."
        )

    total = data.get("total", 0)

    lines = [
        "🔎 REAL eBAY US NƏTİCƏLƏRİ",
        "",
        f"📦 Tapılan listing göstəricisi: {total}",
        "",
    ]

    prices = []

    for index, item in enumerate(items[:10], 1):

        title = item.get(
            "title",
            "Adsız məhsul"
        )

        price_data = item.get(
            "price",
            {}
        )

        price_value = price_data.get(
            "value"
        )

        currency = price_data.get(
            "currency",
            "USD"
        )

        seller = item.get(
            "seller",
            {}
        )

        feedback_score = seller.get(
            "feedbackScore"
        )

        feedback_percentage = seller.get(
            "feedbackPercentage"
        )

        item_location = item.get(
            "itemLocation",
            {}
        )

        location = item_location.get(
            "city",
            "Unknown"
        )

        if price_value is not None:
            try:
                numeric_price = float(price_value)
                prices.append(numeric_price)
                price_text = (
                    f"${numeric_price:.2f} {currency}"
                )
            except (ValueError, TypeError):
                price_text = str(price_value)
        else:
            price_text = "N/A"

        lines.append(
            f"{index}. {title}\n"
            f"💵 Qiymət: {price_text}\n"
            f"👤 Seller feedback: "
            f"{feedback_score if feedback_score is not None else 'N/A'}"
            f" / "
            f"{feedback_percentage if feedback_percentage is not None else 'N/A'}\n"
            f"📍 Location: {location}\n"
        )

    if prices:
        average_price = sum(prices) / len(prices)

        lines.append(
            f"📊 İlk {len(prices)} nəticənin orta qiyməti: "
            f"${average_price:.2f}"
        )

    lines.append(
        "\n⚠️ Qeyd: 'sold', 'sell-through' və "
        "son 30 gün satış sayı bu Browse API nəticəsindən "
        "avtomatik çıxarılmır."
    )

    return "\n".join(lines)


# =========================================================
# START
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "🤖 eBay Dropshipping AI Bot\n\n"
        "Komandalar:\n\n"
        "🔥 /trend - Məhsul ideyaları\n"
        "🔎 /ebay - Real eBay US axtarışı\n"
        "💰 /profit - Profit hesabla\n"
        "🏷 /title - eBay başlığı yarat\n"
        "🧠 /analyze - AI məhsul analizi\n"
        "🤖 /ai - Ümumi AI köməkçisi\n\n"
        "Misallar:\n"
        "/ebay calming pet bed\n"
        "/profit 12 29.99\n"
        "/title calming pet bed\n"
        "/analyze calming pet bed\n"
        "/ai eBay dropshipping üçün məhsul ideyası ver"
    )

    await update.message.reply_text(text)


# =========================================================
# TREND
# =========================================================

async def trend_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global shown_products

    if len(shown_products) >= len(PRODUCTS):
        shown_products.clear()

    available = [
        product
        for product in PRODUCTS
        if product not in shown_products
    ]

    selected_count = min(
        3,
        len(available)
    )

    selected = random.sample(
        available,
        selected_count
    )

    shown_products.extend(selected)

    response = (
        "🔥 MƏHSUL İDEYALARI\n\n"
    )

    for index, product in enumerate(
        selected,
        1
    ):

        response += (
            f"{index}. {product['title']}\n"
            f"📁 {product['cat']}\n"
            f"🛒 Təxmini supplier qiyməti: "
            f"${product['supplier_price']:.2f}\n"
            f"💡 {product['reason']}\n\n"
        )

    response += (
        "⚠️ Bunlar ideyalardır, "
        "real satış statistikası kimi qəbul etmə.\n\n"
        "Real eBay nəticəsi üçün:\n"
        "/ebay məhsul adı"
    )

    await update.message.reply_text(
        response
    )


# =========================================================
# EBAY COMMAND
# =========================================================

def calculate_product_research_score(
    total_listings,
    prices,
    sellers,
    titles
):
    """
    REAL eBay Browse API məlumatlarından
    product research score hesablayır.

    Sold count və sell-through olmadığı üçün
    bunları UYDURMUR.
    """

    score = 100

    breakdown = []

    # 1. LISTING RƏQABƏTİ

    if total_listings <= 500:
        competition_points = 0

    elif total_listings <= 1500:
        competition_points = 5

    elif total_listings <= 3000:
        competition_points = 12

    elif total_listings <= 10000:
        competition_points = 22

    elif total_listings <= 20000:
        competition_points = 30

    else:
        competition_points = 38

    score -= competition_points

    breakdown.append(
        f"Listing rəqabəti: -{competition_points}"
    )

    # 2. AŞAĞI QİYMƏT TƏZYİQİ

    if prices:

        minimum = min(prices)

        if minimum < 5:
            low_price_penalty = 18

        elif minimum < 10:
            low_price_penalty = 12

        elif minimum < 15:
            low_price_penalty = 6

        else:
            low_price_penalty = 0

        score -= low_price_penalty

        breakdown.append(
            f"Aşağı qiymət təzyiqi: -{low_price_penalty}"
        )

    # 3. QİYMƏT SABİTLİYİ

    if prices and len(prices) >= 2:

        minimum = min(prices)
        maximum = max(prices)

        if minimum > 0:

            price_ratio = maximum / minimum

            if price_ratio <= 3:
                price_penalty = 0

            elif price_ratio <= 6:
                price_penalty = 3

            elif price_ratio <= 10:
                price_penalty = 6

            else:
                price_penalty = 10

            score -= price_penalty

            breakdown.append(
                f"Qiymət dəyişkənliyi: -{price_penalty}"
            )

    # 4. SELLER RƏQABƏTİ

    valid_sellers = [
        s for s in sellers
        if isinstance(s, (int, float))
        and s >= 0
    ]

    if valid_sellers:

        strong_sellers = sum(
            1
            for s in valid_sellers
            if s >= 10000
        )

        strong_ratio = (
            strong_sellers / len(valid_sellers)
        )

        if strong_ratio >= 0.70:
            seller_penalty = 12

        elif strong_ratio >= 0.40:
            seller_penalty = 8

        elif strong_ratio >= 0.20:
            seller_penalty = 4

        else:
            seller_penalty = 0

        score -= seller_penalty

        breakdown.append(
            f"Güclü seller rəqabəti: -{seller_penalty}"
        )

    # 5. TƏKRARLANAN LISTINGLƏR

    clean_titles = []

    for title in titles:

        if not title:
            continue

        normalized = (
            " ".join(
                str(title)
                .lower()
                .split()
            )
        )

        if normalized:
            clean_titles.append(normalized)

    duplicate_penalty = 0

    if clean_titles:

        title_counts = {}

        for title in clean_titles:

            title_counts[title] = (
                title_counts.get(title, 0) + 1
            )

        duplicate_count = sum(
            count - 1
            for count in title_counts.values()
            if count > 1
        )

        duplicate_ratio = (
            duplicate_count / len(clean_titles)
        )

        if duplicate_ratio >= 0.50:
            duplicate_penalty = 10

        elif duplicate_ratio >= 0.30:
            duplicate_penalty = 7

        elif duplicate_ratio >= 0.15:
            duplicate_penalty = 4

        elif duplicate_ratio >= 0.05:
            duplicate_penalty = 2

    score -= duplicate_penalty

    breakdown.append(
        f"Təkrarlanan listinglər: -{duplicate_penalty}"
    )

    # SCORE 0-100

    score = max(
        0,
        min(100, round(score))
    )

    # QƏRAR

    if score >= 70:
        decision = "🟢 GO"

    elif score >= 50:
        decision = "🟡 MAYBE"

    else:
        decision = "🔴 NO-GO"

    # DATA CONFIDENCE

    if total_listings > 0 and prices:
        data_confidence = "🟡 ORTA"

    elif total_listings > 0:
        data_confidence = "🟠 AŞAĞI"

    else:
        data_confidence = "🔴 ÇOX AŞAĞI"

    return (
        score,
        decision,
        data_confidence,
        breakdown
    )

async def ebay_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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

    await update.message.reply_text(
        "🔎 REAL eBay US axtarılır...\n"
        "🤖 Məhsul analiz edilir...\n"
        "⏳ Bir az gözlə..."
    )

    try:
        data = ebay_search_products(
            keyword,
            limit=10
        )

        result = format_ebay_results(data)

        # =================================================
        # REAL EBAY DATA
        # =================================================

        total_listings = int(
            data.get("total", 0) or 0
        )

        prices = []

        items = data.get(
            "itemSummaries",
            []
        )

                 for item in items:

            price = item.get("price")

            if isinstance(price, dict):
                price = price.get("value")

            try:

                if price is not None:
                    prices.append(
                        float(price)
                    )

            except (
                ValueError,
                TypeError
            ):
                pass

            # TITLE
            title = item.get("title", "")

            if title:
                titles.append(title)

            # SELLER FEEDBACK
            seller = item.get("seller", {})

            if isinstance(seller, dict):
                feedback = seller.get(
                    "feedbackScore",
                    0
                )
            else:
                feedback = 0

            try:
                sellers.append(
                    float(feedback)
                )
            except (
                ValueError,
                TypeError
            ):
                pass

        # =================================================
        # PRODUCT SCORE
        # =================================================

             sellers = []
    titles = []

    for item in items:

        title = item.get("title", "")
        if title:
            titles.append(title)

        seller = item.get("seller", {})

        if isinstance(seller, dict):
            feedback = seller.get("feedbackScore", 0)
        else:
            feedback = 0

        try:
            sellers.append(float(feedback))
        except (ValueError, TypeError):
            pass

    # =================================================
    # PRODUCT SCORE
    # =================================================

    (
        score,
        decision,
        data_confidence,
        breakdown
    ) = calculate_product_research_score(
        total_listings,
        prices,
        sellers,
        titles
    )
        # =================================================
        # AI PRODUCT RESEARCH
        # =================================================

        if gemini_client:

            analysis_prompt = f"""
Sən peşəkar eBay US product research köməkçisisən.

Məhsul:
{keyword}

REAL eBay Browse API nəticələri:

{result}

REAL SISTEM SCORE:
{score}/100

SISTEM QƏRARI:
{decision}

ÇOX VACİB QAYDALAR:

1. Yalnız verilən REAL eBay məlumatlarından istifadə et.
2. Sold count məlumatı yoxdursa UYDURMA.
3. Sell-through rate yoxdursa UYDURMA.
4. Supplier qiyməti yoxdursa UYDURMA.
5. Seller feedback-i satış sayı kimi göstərmə.
6. Listing sayını satış sayı kimi göstərmə.
7. Listing sayı yüksəkdirsə rəqabəti yüksək qiymətləndir.
8. Çox oxşar/təkrarlanan məhsullar varsa bunu rəqabət kimi qeyd et.
9. Çox ucuz rəqiblər varsa qiymət təzyiqini qeyd et.
10. Çox bahalı outlier məhsullar varsa ayrıca qeyd et.
11. Məhsulun elektrikli, batareyalı, kövrək və ya qaytarılma riski olan məhsul olub-olmadığını nəzərə al.
12. Trend olduğunu sübut edən məlumat yoxdursa "Trend məlumatı yoxdur" yaz.
13. Supplier qiyməti olmadığı halda profit hesablaması etmə.
14. Sistem score-unu dəyişmə.
15. Özündən rəqəm uydurma.
16. "Çox satılır" kimi ifadə yalnız real satış datası varsa istifadə oluna bilər.

Cavabı Azərbaycan dilində ver.

FORMAT:

🔥 REAL EBAY MƏHSUL ANALİZİ

📦 Məhsul:
{keyword}

🇺🇸 eBay bazarı:

- Listing sayı:

💰 Qiymət:

- Minimum:
- Maksimum:
- Orta:

🏆 Rəqabət:
🟢 Aşağı / 🟡 Orta / 🔴 Yüksək

👥 Seller vəziyyəti:

📈 Satış potensialı:

⚠️ Məlumat çatışmazlığı:

- Sold count:
- Sell-through:
- Supplier qiyməti:
- Trend:

🎯 PRODUCT SCORE:
{score}/100

NƏTİCƏ:
{decision}

💡 Qısa səbəb:

📦 DROPSHIPPING ÜÇÜN ÜSTÜNLÜKLƏR:

📦 DROPSHIPPING ÜÇÜN RİSKLƏR:

Sonda məhsul üçün qısa və dürüst qərar ver.
"""

            try:

                ai_response = (
                    gemini_client.models.generate_content(
                        model="gemini-3.6-flash",
                        contents=analysis_prompt
                    )
                )

                ai_answer = (
                    ai_response.text
                    or "AI analiz qaytarmadı."
                )

                final_response = ai_answer

            except Exception as ai_error:

                print(
                    "eBay AI analysis error:",
                    repr(ai_error)
                )

                final_response = (
                    result
                    + "\n\n"
                    + f"🎯 PRODUCT SCORE: {score}/100\n"
                    + f"📌 NƏTİCƏ: {decision}"
                )

        else:

            final_response = (
                result
                + "\n\n"
                + f"🎯 PRODUCT SCORE: {score}/100\n"
                + f"📌 NƏTİCƏ: {decision}"
            )

        # =================================================
        # TELEGRAM MESAJ LIMITI
        # =================================================

        max_length = 3900

        for i in range(
            0,
            len(final_response),
            max_length
        ):

            await update.message.reply_text(
                final_response[
                    i:i + max_length
                ]
            )

    except Exception as error:

        print(
            "eBay error:",
            repr(error)
        )

        await update.message.reply_text(
            "❌ eBay API xətası.\n\n"
            + str(error)[:1200]
        )
        
# =========================================================
# PROFIT
# =========================================================

async def profit_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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

        if supplier_price < 0 or ebay_price < 0 or shipping_cost < 0:
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
            shipping_cost
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
            f"• Final Value Fee: "
            f"${final_value_fee:.2f}\n"
            f"• Fixed Fee: "
            f"${fixed_fee:.2f}\n"
            f"• Cəmi eBay xərci: "
            f"${total_fees:.2f}\n\n"

            f"💰 Xalis profit: "
            f"${net_profit:.2f}\n"
            f"📈 Profit marjası: "
            f"{margin:.2f}%\n\n"

            f"🎯 Nəticə: {status}"
        )

        await update.message.reply_text(
            response
        )

    except ValueError:
        await update.message.reply_text(
            "❌ Qiymətləri rəqəmlə yaz.\n\n"
            "Misal:\n"
            "/profit 12 29.99 5"
        )

# =========================================================
# TITLE
# =========================================================

async def title_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:
        await update.message.reply_text(
            "⚠️ Məhsul adını yaz.\n\n"
            "Misal:\n"
            "/title mətbəx üçün elektrik süd köpürdücü"
        )
        return

    raw_input = " ".join(context.args)

    if not gemini_client:
        await update.message.reply_text(
            "❌ GEMINI_API_KEY tapılmadı. Başlıq yaradıla bilmədi."
        )
        return

    prompt = f"""
Create 3 eBay product titles for this product:

{raw_input}

IMPORTANT RULES:

- Write the titles in natural English.
- Each title MUST be maximum 80 characters.
- Use only information supported by the product name.
- Do not invent product features.
- Do not invent brand names.
- Do not use "USA Seller".
- Do not use "Top Rated".
- Do not use "Best Seller".
- Do not use "Best Gift".
- Do not use "Fast Shipping".
- Do not use "Free Shipping".
- Do not use fake quality claims such as "Premium" or "Professional"
  unless clearly supported by the product information.
- Focus on useful eBay search keywords.
- Avoid unnecessary symbols and emojis.
- Return exactly 3 titles.
- Put each title on a separate line.
- Do not add explanations.

Product:
{raw_input}
"""

    try:

        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )

        answer = (
            response.text.strip()
            if response.text
            else ""
        )

        if not answer:
            await update.message.reply_text(
                "❌ AI başlıq yarada bilmədi."
            )
            return

        # AI cavabını sətirlərə böl
        raw_titles = [
            line.strip()
            for line in answer.splitlines()
            if line.strip()
        ]

        titles = []

        for title in raw_titles:

            # Nömrələməni təmizlə
            title = title.lstrip("0123456789.-) ")

            # 80 simvoldan artıqdırsa kəs
            title = title[:80].strip()

            if title:
                titles.append(title)

        # Maksimum 3 başlıq
        titles = titles[:3]

        if not titles:
            await update.message.reply_text(
                "❌ AI düzgün eBay başlığı yarada bilmədi."
            )
            return

        response_text = (
            "🏷 EBAY SEO TITLE\n\n"
        )

        for index, title in enumerate(titles, 1):
            response_text += (
                f"{index}. {title}\n"
                f"📏 {len(title)}/80 simvol\n\n"
            )

        await update.message.reply_text(
            response_text
        )

    except Exception as error:

        print(
            "Title AI error:",
            repr(error)
        )

        await update.message.reply_text(
            "❌ AI başlıq yarada bilmədi."
        )

# =========================================================
# ANALYZE
# =========================================================


async def analyze_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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

    wait_message = await update.message.reply_text(
        "🔎 Real eBay US məlumatları axtarılır...\n"
        "🤖 Məhsul analiz edilir...\n"
        "Bir az gözlə..."
    )

    try:

        # =================================================
        # REAL EBAY SEARCH
        # =================================================

        data = ebay_search_products(
            keyword,
            limit=10
        )

        result = format_ebay_results(data)

        # =================================================
        # REAL DATA EXTRACTION
        # =================================================

        total_listings = 0
        prices = []
        sellers = []
        titles = [] 

        
        if isinstance(data, dict):

            total_listings = int(
                data.get("total", 0)
                or data.get("totalListings", 0)
                or 0
            )

            items = (
                data.get("itemSummaries")
                or data.get("items")
                or data.get("results")
                or []
            )

            for item in items:

                price = item.get("price")

                if isinstance(price, dict):
                    price = price.get("value")

                try:

                    if price is not None:
                        prices.append(
                            float(price)
                        )

                except (
                    ValueError,
                    TypeError
                ):
                    pass

        # =================================================
        # REAL SCORE
        # =================================================

     (
        score,
        decision,
        data_confidence,
        breakdown
    ) = calculate_product_research_score(
        total_listings,
        prices,
        sellers,
        titles
    )

        # =================================================
        # AI ANALYSIS
        # =================================================

        analysis_prompt = f"""
Sən eBay US dropshipping product research
köməkçisisən.

Məhsul:
{keyword}

Aşağıdakı məlumatlar REAL eBay Browse API
nəticələrindən götürülüb:

{result}

REAL EBAY MƏLUMATLARI:

Listing sayı:
{total_listings}

İlk nəticələrdən alınan qiymətlər:
{prices}

Sistem tərəfindən real məlumatlardan
hesablanan ilkin score:
{score}/100

Sistem qərarı:
{decision}

VACİB QAYDALAR:

1. Yalnız verilən real eBay məlumatlarından istifadə et.

2. Sold count məlumatı yoxdursa:
"Sold count: məlumat yoxdur"
yaz.

3. Sell-through rate məlumatı yoxdursa:
"Sell-through: məlumat yoxdur"
yaz.

4. Supplier qiyməti verilməyibsə:
supplier qiyməti UYDURMA.

5. Satış sayı olmayan halda:
"çox satılır" demə.

6. Listing sayı satış sayı deyil.

7. Seller feedback satış sayı deyil.

8. Məhsulun trend olduğunu sübut edən məlumat
yoxdursa trend olduğunu iddia etmə.

9. Qiymətləri real eBay nəticələrindən istifadə et.

10. Eyni və çox oxşar listinglər varsa,
rəqabət göstəricisi kimi qeyd et.

11. Çox bahalı və qeyri-adi qiymətlər varsa,
onları ayrıca qeyd et.

12. Sistem score-unu dəyişmə.
Verilən score:
{score}/100

13. Sistem qərarını dəyişmə.
Verilən qərar:
{decision}

Cavabı Azərbaycan dilində ver.

FORMAT:

🔎 REAL EBAY MƏHSUL ANALİZİ

📦 Məhsul:
{keyword}

🇺🇸 eBay bazarı:
- Listing sayı:

💰 Qiymət:
- Minimum:
- Maksimum:
- Orta:

🏆 Rəqabət:
🟢 Aşağı
🟡 Orta
🔴 Yüksək

👥 Seller vəziyyəti:

📈 Satış potensialı:

⚠️ Məlumat çatışmazlığı:
- Sold count:
- Sell-through:
- Supplier qiyməti:
- Trend:

🎯 PRODUCT SCORE:
{score}/100

NƏTİCƏ:
{decision}

💡 Qısa səbəb:

Sonda məhsulun dropshipping üçün
əsas üstünlüklərini və əsas risklərini qısa yaz.
"""

        try:

            ai_response = (
                gemini_client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=analysis_prompt
                )
            )

            ai_answer = (
                ai_response.text
                or "AI analiz qaytarmadı."
            )

            try:
                await wait_message.delete()
            except Exception:
                pass

            final_response = (
                ai_answer
            )

        except Exception as ai_error:

            print(
                "Analyze AI error:",
                repr(ai_error)
            )

            try:
                await wait_message.delete()
            except Exception:
                pass

            final_response = (
                "🔎 REAL EBAY MƏHSUL ANALİZİ\n\n"
                + result
                + "\n\n"
                + f"🎯 PRODUCT SCORE: {score}/100\n"
                + f"📌 NƏTİCƏ: {decision}"
            )

        # =================================================
        # TELEGRAM MESSAGE LIMIT
        # =================================================

        max_length = 3900

        for i in range(
            0,
            len(final_response),
            max_length
        ):

            await update.message.reply_text(
                final_response[
                    i:i + max_length
                ]
            )

    except Exception as error:

        print(
            "Analyze eBay error:",
            repr(error)
        )

        try:
            await wait_message.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "❌ eBay analiz xətası:\n\n"
            + str(error)[:1200]
        )


# =========================================================
# AI
# =========================================================

async def ai_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(
            "⚠️ Misal:\n"
            "/ai eBay dropshipping üçün "
            "3 məhsul ideyası ver"
        )

        return

    if not gemini_client:

        await update.message.reply_text(
            "❌ GEMINI_API_KEY tapılmadı."
        )

        return

    prompt = " ".join(
        context.args
    )

    try:

        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )

        answer = (
            response.text
            or "AI cavab qaytarmadı."
        )

        await update.message.reply_text(
            "🤖 AI:\n\n"
            + answer
        )

    except Exception as error:

        print(
            "Gemini error:",
            repr(error)
        )

        await update.message.reply_text(
            "❌ AI xətası:\n"
            + str(error)[:1000]
        )


# =========================================================
# FLASK
# =========================================================

@app.route("/")
def index():

    return "Bot 24/7 Aktivdir!", 200


def run_flask():

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not TELEGRAM_TOKEN:

        raise RuntimeError(
            "TELEGRAM_TOKEN tapılmadı."
        )

    Thread(
        target=run_flask,
        daemon=True
    ).start()

    telegram_app = (
        Application
        .builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    telegram_app.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    telegram_app.add_handler(
        CommandHandler(
            "trend",
            trend_command
        )
    )

    telegram_app.add_handler(
        CommandHandler(
            "ebay",
            ebay_command
        )
    )

    telegram_app.add_handler(
        CommandHandler(
            "profit",
            profit_command
        )
    )

    telegram_app.add_handler(
        CommandHandler(
            "title",
            title_command
        )
    )

    telegram_app.add_handler(
        CommandHandler(
            "analyze",
            analyze_command
        )
    )

    telegram_app.add_handler(
        CommandHandler(
            "ai",
            ai_command
        )
    )

    print(
        "🤖 Bot uğurla işə düşdü..."
    )

    telegram_app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
    
