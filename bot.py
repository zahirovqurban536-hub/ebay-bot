import os
import re
import base64
from statistics import mean, median
from threading import Thread
from typing import Any

import requests
from flask import Flask
from google import genai

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)


# ============================================================
# CONFIG
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
EBAY_CLIENT_ID = os.environ.get("EBAY_CLIENT_ID")
EBAY_CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET")

# Officially available Gemini model
GEMINI_MODEL = "gemini-3.6-flash"

EBAY_MARKETPLACE = "EBAY_US"

MAX_TELEGRAM_LENGTH = 3900
EBAY_TIMEOUT = 30

app = Flask(__name__)

gemini_client = None

if GEMINI_API_KEY:
    gemini_client = genai.Client(
        api_key=GEMINI_API_KEY
    )


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default

    return str(value).strip()


def safe_float(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def split_telegram_text(
    text: str,
    max_length: int = MAX_TELEGRAM_LENGTH
):
    if not text:
        return [""]

    chunks = []
    remaining = str(text)

    while len(remaining) > max_length:

        cut = remaining.rfind(
            "\n",
            0,
            max_length
        )

        if cut < int(max_length * 0.60):
            cut = remaining.rfind(
                " ",
                0,
                max_length
            )

        if cut < int(max_length * 0.60):
            cut = max_length

        chunks.append(
            remaining[:cut].strip()
        )

        remaining = remaining[cut:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


async def send_long_message(
    update: Update,
    text: str
):
    for chunk in split_telegram_text(text):
        await update.message.reply_text(chunk)


def money(value):
    if value is None:
        return "N/A"

    return f"${value:,.2f}"


# ============================================================
# GEMINI
# ============================================================

def ask_ai(prompt: str) -> str:

    if not gemini_client:
        raise RuntimeError(
            "GEMINI_API_KEY tapılmadı."
        )

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    answer = clean_text(
        getattr(response, "text", ""),
        ""
    )

    if not answer:
        raise RuntimeError(
            "Gemini boş cavab qaytardı."
        )

    return answer


# ============================================================
# EBAY OAUTH
# ============================================================

def get_ebay_application_token():

    if not EBAY_CLIENT_ID:
        raise RuntimeError(
            "EBAY_CLIENT_ID yoxdur."
        )

    if not EBAY_CLIENT_SECRET:
        raise RuntimeError(
            "EBAY_CLIENT_SECRET yoxdur."
        )

    credentials = (
        f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}"
    )

    encoded_credentials = base64.b64encode(
        credentials.encode("utf-8")
    ).decode("utf-8")

    headers = {
        "Content-Type":
            "application/x-www-form-urlencoded",
        "Authorization":
            f"Basic {encoded_credentials}",
    }

    data = {
        "grant_type":
            "client_credentials",

        "scope":
            "https://api.ebay.com/oauth/api_scope",
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
            f"{response.status_code}\n"
            f"{response.text[:1000]}"
        )

    result = response.json()

    token = result.get(
        "access_token"
    )

    if not token:
        raise RuntimeError(
            "eBay access token alınmadı."
        )

    return token


# ============================================================
# REAL EBAY SEARCH
# ============================================================

def ebay_search_products(
    keyword: str,
    limit: int = 50
):

    token = get_ebay_application_token()

    headers = {
        "Authorization":
            f"Bearer {token}",

        "Content-Type":
            "application/json",

        "X-EBAY-C-MARKETPLACE-ID":
            EBAY_MARKETPLACE,
    }

    params = {
        "q": keyword,
        "limit": min(
            max(limit, 1),
            50
        ),
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
            f"{response.status_code}\n"
            f"{response.text[:1200]}"
        )

    return response.json()


# ============================================================
# EXTRACT REAL EBAY DATA
# ============================================================

def extract_ebay_data(data):

    items = data.get(
        "itemSummaries"
    ) or []

    total = safe_float(
        data.get("total")
    ) or 0

    total = int(total)

    prices = []
    sellers = []
    titles = []
    locations = []

    shipping_prices = []

    condition_counts = {}

    real_items = []

    for item in items:

        if not isinstance(
            item,
            dict
        ):
            continue

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        title = clean_text(
            item.get("title")
        )

        if title:
            titles.append(title)

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        price_data = (
            item.get("price")
            or {}
        )

        if isinstance(
            price_data,
            dict
        ):
            price = safe_float(
                price_data.get("value")
            )

            currency = clean_text(
                price_data.get(
                    "currency"
                ),
                "USD"
            )
        else:
            price = safe_float(
                price_data
            )

            currency = "USD"

        if (
            price is not None
            and price >= 0
        ):
            prices.append(price)

        # ----------------------------------------------------
        # SELLER
        # ----------------------------------------------------

        seller = (
            item.get("seller")
            or {}
        )

        feedback = None
        feedback_percentage = None

        if isinstance(
            seller,
            dict
        ):

            feedback = safe_float(
                seller.get(
                    "feedbackScore"
                )
            )

            feedback_percentage = (
                seller.get(
                    "feedbackPercentage"
                )
            )

        if feedback is not None:
            sellers.append(
                feedback
            )

        # ----------------------------------------------------
        # LOCATION
        # ----------------------------------------------------

        location = (
            item.get("itemLocation")
            or {}
        )

        location_text = ""

        if isinstance(
            location,
            dict
        ):

            city = clean_text(
                location.get("city")
            )

            state = clean_text(
                location.get("stateOrProvince")
            )

            country = clean_text(
                location.get("country")
            )

            location_text = ", ".join(
                x
                for x in [
                    city,
                    state,
                    country
                ]
                if x
            )

            if location_text:
                locations.append(
                    location_text
                )

        # ----------------------------------------------------
        # CONDITION
        # ----------------------------------------------------

        condition = clean_text(
            item.get(
                "condition"
            ),
            "Unknown"
        )

        condition_counts[
            condition
        ] = condition_counts.get(
            condition,
            0
        ) + 1

        # ----------------------------------------------------
        # SHIPPING
        # ----------------------------------------------------

        shipping_options = (
            item.get(
                "shippingOptions"
            )
            or []
        )

        shipping_value = None

        if shipping_options:

            first_shipping = (
                shipping_options[0]
            )

            if isinstance(
                first_shipping,
                dict
            ):

                shipping_cost = (
                    first_shipping.get(
                        "shippingCost"
                    )
                    or {}
                )

                if isinstance(
                    shipping_cost,
                    dict
                ):

                    shipping_value = (
                        safe_float(
                            shipping_cost.get(
                                "value"
                            )
                        )
                    )

        if shipping_value is not None:

            shipping_prices.append(
                shipping_value
            )

        # ----------------------------------------------------
        # SAVE REAL ITEM
        # ----------------------------------------------------

        real_items.append(
            {
                "title": title,
                "price": price,
                "currency": currency,
                "seller_feedback": feedback,
                "seller_feedback_percentage":
                    feedback_percentage,
                "location":
                    location_text,
                "condition":
                    condition,
                "shipping":
                    shipping_value,
                "item_id":
                    clean_text(
                        item.get(
                            "itemId"
                        )
                    ),
            }
        )

    return {
        "total_listings":
            total,

        "prices":
            prices,

        "sellers":
            sellers,

        "titles":
            titles,

        "locations":
            locations,

        "shipping_prices":
            shipping_prices,

        "condition_counts":
            condition_counts,

        "items":
            real_items,
    }


# ============================================================
# DETERMINISTIC SCORE
# ============================================================

def calculate_product_score(
    total_listings,
    prices,
    sellers,
    titles
):

    score = 100

    reasons = []

    # --------------------------------------------------------
    # LISTING COMPETITION
    # --------------------------------------------------------

    if total_listings <= 500:

        penalty = 0

    elif total_listings <= 1500:

        penalty = 8

    elif total_listings <= 3000:

        penalty = 15

    elif total_listings <= 10000:

        penalty = 25

    elif total_listings <= 20000:

        penalty = 32

    else:

        penalty = 40

    score -= penalty

    reasons.append(
        f"Listing rəqabəti: -{penalty}"
    )

    # --------------------------------------------------------
    # LOW PRICE PRESSURE
    # --------------------------------------------------------

    if prices:

        minimum = min(prices)

        if minimum < 5:

            penalty = 18

        elif minimum < 10:

            penalty = 13

        elif minimum < 15:

            penalty = 7

        elif minimum < 20:

            penalty = 3

        else:

            penalty = 0

        score -= penalty

        reasons.append(
            f"Aşağı qiymət təzyiqi: -{penalty}"
        )

    # --------------------------------------------------------
    # SELLER POWER
    # --------------------------------------------------------

    valid_sellers = [
        s
        for s in sellers
        if isinstance(
            s,
            (int, float)
        )
    ]

    if valid_sellers:

        very_large = sum(
            1
            for s in valid_sellers
            if s >= 10000
        )

        large_ratio = (
            very_large /
            len(valid_sellers)
        )

        if large_ratio >= 0.70:

            penalty = 12

        elif large_ratio >= 0.40:

            penalty = 8

        elif large_ratio >= 0.20:

            penalty = 4

        else:

            penalty = 0

        score -= penalty

        reasons.append(
            f"Güclü seller rəqabəti: -{penalty}"
        )

    # --------------------------------------------------------
    # TITLE DUPLICATION
    # --------------------------------------------------------

    normalized = []

    for title in titles:

        value = " ".join(
            title.lower().split()
        )

        if value:
            normalized.append(
                value
            )

    if normalized:

        counts = {}

        for title in normalized:

            counts[title] = (
                counts.get(
                    title,
                    0
                ) + 1
            )

        duplicates = sum(
            count - 1
            for count in counts.values()
            if count > 1
        )

        duplicate_ratio = (
            duplicates /
            len(normalized)
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

        reasons.append(
            f"Oxşar/təkrarlanan başlıqlar: -{penalty}"
        )

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    score = max(
        0,
        min(
            100,
            round(score)
        )
    )

    if score >= 70:

        decision = "🟢 GO"

    elif score >= 50:

        decision = "🟡 MAYBE"

    else:

        decision = "🔴 NO-GO"

    return (
        score,
        decision,
        reasons
    )


# ============================================================
# REAL EBAY REPORT
# ============================================================

def build_real_ebay_report(
    keyword,
    extracted
):

    total = extracted[
        "total_listings"
    ]

    prices = extracted[
        "prices"
    ]

    sellers = extracted[
        "sellers"
    ]

    items = extracted[
        "items"
    ]

    lines = []

    lines.append(
        "🔎 REAL EBAY US DATA"
    )

    lines.append("")

    lines.append(
        f"🔍 Search keyword: {keyword}"
    )

    lines.append(
        f"📦 eBay result count: {total:,}"
    )

    lines.append(
        f"📊 API sample analyzed: {len(items)} listings"
    )

    lines.append("")

    # --------------------------------------------------------
    # PRICE DATA
    # --------------------------------------------------------

    if prices:

        lines.append(
            "💰 REAL PRICE DATA"
        )

        lines.append(
            f"• Minimum: {money(min(prices))}"
        )

        lines.append(
            f"• Maximum: {money(max(prices))}"
        )

        lines.append(
            f"• Average of sample: {money(mean(prices))}"
        )

        lines.append(
            f"• Median of sample: {money(median(prices))}"
        )

        lines.append(
            "• Bu average/median yalnız API-dən alınan "
            f"{len(prices)} qiymət üzərində hesablanıb."
        )

    else:

        lines.append(
            "💰 Price data: tapılmadı."
        )

    lines.append("")

    # --------------------------------------------------------
    # SELLER DATA
    # --------------------------------------------------------

    if sellers:

        lines.append(
            "👥 REAL SELLER DATA"
        )

        lines.append(
            f"• Seller feedback sample: {len(sellers)}"
        )

        lines.append(
            f"• Minimum feedback: {int(min(sellers)):,}"
        )

        lines.append(
            f"• Maximum feedback: {int(max(sellers)):,}"
        )

        strong = sum(
            1
            for s in sellers
            if s >= 10000
        )

        lines.append(
            f"• 10,000+ feedback sellers: {strong}"
        )

    else:

        lines.append(
            "👥 Seller data: tapılmadı."
        )

    lines.append("")

    # --------------------------------------------------------
    # CONDITION
    # --------------------------------------------------------

    condition_counts = (
        extracted[
            "condition_counts"
        ]
    )

    if condition_counts:

        lines.append(
            "📦 CONDITION DATA"
        )

        for condition, count in (
            condition_counts.items()
        ):

            lines.append(
                f"• {condition}: {count}"
            )

        lines.append("")

    # --------------------------------------------------------
    # SHIPPING
    # --------------------------------------------------------

    shipping = extracted[
        "shipping_prices"
    ]

    if shipping:

        lines.append(
            "🚚 SHIPPING DATA"
        )

        lines.append(
            f"• Minimum sample shipping: "
            f"{money(min(shipping))}"
        )

        lines.append(
            f"• Maximum sample shipping: "
            f"{money(max(shipping))}"
        )

        lines.append("")

    # --------------------------------------------------------
    # REAL LISTINGS
    # --------------------------------------------------------

    lines.append(
        "📋 REAL SAMPLE LISTINGS"
    )

    lines.append("")

    for index, item in enumerate(
        items[:15],
        1
    ):

        lines.append(
            f"{index}. {item['title']}"
        )

        lines.append(
            f"   💵 Price: "
            f"{money(item['price'])} "
            f"{item['currency']}"
        )

        feedback = (
            item[
                "seller_feedback"
            ]
        )

        feedback_percentage = (
            item[
                "seller_feedback_percentage"
            ]
        )

        if feedback is not None:

            lines.append(
                f"   👤 Seller feedback: "
                f"{int(feedback):,}"
            )

        if feedback_percentage:

            lines.append(
                f"   ⭐ Feedback %: "
                f"{feedback_percentage}"
            )

        if item["location"]:

            lines.append(
                f"   📍 Location: "
                f"{item['location']}"
            )

        if item["shipping"] is not None:

            lines.append(
                f"   🚚 Shipping: "
                f"{money(item['shipping'])}"
            )

        lines.append(
            f"   📦 Condition: "
            f"{item['condition']}"
        )

        lines.append("")

    # --------------------------------------------------------
    # IMPORTANT DATA LIMITATION
    # --------------------------------------------------------

    lines.append(
        "⚠️ DATA LIMITATIONS"
    )

    lines.append(
        "• Browse API bu axtarış nəticəsində sold count vermir."
    )

    lines.append(
        "• Browse API bu nəticədə sell-through rate vermir."
    )

    lines.append(
        "• Supplier qiyməti eBay məlumatı deyil və "
        "bu bot onu uydurmur."
    )

    lines.append(
        "• Trend/viral status bu API nəticəsindən "
        "avtomatik təsdiqlənmir."
    )

    return "\n".join(lines)


# ============================================================
# AI PRODUCT ANALYSIS
# ============================================================

def ai_product_analysis(
    keyword,
    extracted,
    score,
    decision
):

    total = extracted[
        "total_listings"
    ]

    prices = extracted[
        "prices"
    ]

    sellers = extracted[
        "sellers"
    ]

    items = extracted[
        "items"
    ]

    if prices:

        minimum = min(prices)
        maximum = max(prices)
        average = mean(prices)
        median_price = median(prices)

    else:

        minimum = None
        maximum = None
        average = None
        median_price = None

    if sellers:

        max_feedback = max(
            sellers
        )

        strong_sellers = sum(
            1
            for s in sellers
            if s >= 10000
        )

    else:

        max_feedback = None
        strong_sellers = 0

    sample_titles = [
        item["title"]
        for item in items[:20]
        if item["title"]
    ]

    real_data = f"""
REAL EBAY US DATA:

Product:
{keyword}

Total eBay search result count:
{total}

API listings analyzed:
{len(items)}

Minimum observed price:
{minimum}

Maximum observed price:
{maximum}

Average observed price:
{average}

Median observed price:
{median_price}

Seller feedback sample:
{len(sellers)}

Maximum seller feedback:
{max_feedback}

Sellers with 10,000+ feedback:
{strong_sellers}

Real listing titles:
{sample_titles}

SYSTEM SCORE:
{score}/100

SYSTEM DECISION:
{decision}
"""

    prompt = f"""
Sən eBay US dropshipping product-research AI-sən.

Aşağıdakı məlumatlar REAL eBay Browse API-dən
götürülüb.

Sənin vəzifən həmin məlumatları şərh etməkdir.

{real_data}

ÇOX VACİB QAYDALAR:

1. YALNIZ yuxarıdakı real məlumatlardan istifadə et.

2. Listing count = satış sayı DEYİL.

3. Seller feedback = həmin məhsulun satış sayı DEYİL.

4. Sold count verilməyib.
Heç bir sold count rəqəmi yazma.

5. Sell-through rate verilməyib.
Heç bir sell-through rəqəmi yazma.

6. Supplier qiyməti verilməyib.
AliExpress, CJ, Amazon və başqa supplier qiyməti
özündən yazma.

7. Mənfəət rəqəmi hesablama.
Supplier qiyməti olmadığı üçün dəqiq profit mümkün deyil.

8. "Viral", "trend", "hot product", "best seller"
kimi ifadələri fakt kimi istifadə etmə.

9. Yüksək listing count varsa bunu yalnız
YÜKSƏK TƏKLİF/RƏQABƏT siqnalı kimi izah et.

10. Aşağı qiymət çoxdursa qiymət təzyiqini izah et.

11. 10,000+ seller feedback çoxdursa,
güclü satıcı rəqabəti kimi izah et.

12. Məhsulun batareyalı olması, elektrikli olması,
kövrək olması və s. yalnız məhsul adından açıq görünürsə
risk kimi qeyd et.

13. Məhsulun keyfiyyəti haqqında real review datası
verilməyibsə iddia etmə.

14. SYSTEM SCORE və SYSTEM DECISION dəyişdirilməməlidir.

15. Əgər məlumat kifayət etmirsə açıq şəkildə:
"Data çatışmır" yaz.

16. Heç bir statistika uydurma.

Cavab Azərbaycan dilində olsun.

FORMAT:

🧠 AI PRODUCT BRAIN

📦 Məhsul:
{keyword}

🇺🇸 REAL EBAY BAZARI

- eBay nəticə sayı:
- Analiz edilən real listing:
- Minimum qiymət:
- Maksimum qiymət:
- Sample average:
- Sample median:

🏆 RƏQABƏT

- Səviyyə:
- Səbəb:

💰 QİYMƏT STRATEGİYASI

- Real müşahidə olunan qiymət aralığı:
- Aşağı qiymət təzyiqi:
- Qiymət barədə nəticə:

👥 SELLER MÜHİTİ

- Seller feedback:
- Güclü seller rəqabəti:

📈 SATIŞ POTENSİALI

- Sold count:
- Sell-through:
- Nəticə:

⚠️ RİSKLƏR

- Data riski:
- Rəqabət riski:
- Qiymət riski:
- Məhsul riski:

🎯 PRODUCT SCORE:
{score}/100

📌 QƏRAR:
{decision}

💡 SON FİKİR:

Məhsulun eBay US dropshipping üçün
araşdırmağa dəyib-dəymədiyini real API datasına
əsasən qısa şəkildə izah et.

Əgər satış datası yoxdursa bunu açıq bildir.
"""

    return ask_ai(prompt)


# ============================================================
# FULL PRODUCT RESEARCH
# ============================================================

def perform_product_research(
    keyword,
    limit=50
):

    data = ebay_search_products(
        keyword,
        limit=limit
    )

    extracted = extract_ebay_data(
        data
    )

    if not extracted["items"]:

        raise RuntimeError(
            "eBay-də bu axtarış üçün "
            "listing tapılmadı."
        )

    score, decision, reasons = (
        calculate_product_score(
            extracted[
                "total_listings"
            ],
            extracted[
                "prices"
            ],
            extracted[
                "sellers"
            ],
            extracted[
                "titles"
            ],
        )
    )

    return (
        extracted,
        score,
        decision,
        reasons
    )


# ============================================================
# START
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = """
🤖 eBay US DROPSHIPPING AI BRAIN

Komandalar:

🔎 /ebay
Real eBay US nəticələrini göstərir.

🧠 /analyze
Real eBay məlumatı + AI product research.

🤖 /ai
Ümumi AI köməkçisi.
Məhsul adı yazsan avtomatik real eBay analizi edir.

🔥 /trend
AI məhsul araşdırma ideyaları.

💰 /profit
Profit hesablayır.

🏷 /title
3 eBay SEO title yaradır.


Misallar:

/ebay portable mini vacuum cleaner wireless

/analyze portable mini vacuum cleaner wireless

/ai portable mini vacuum cleaner wireless

/ai calming pet bed

/profit 9.20 24.99 3

/title portable mini vacuum cleaner wireless
"""

    await update.message.reply_text(
        text
    )


# ============================================================
# EBAY COMMAND
# ============================================================

async def ebay_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(
            "⚠️ Misal:\n\n"
            "/ebay portable mini vacuum cleaner wireless"
        )

        return

    keyword = " ".join(
        context.args
    )

    wait = await update.message.reply_text(
        "🔎 REAL eBay US axtarılır...\n"
        "📊 Real listing məlumatları yığılır..."
    )

    try:

        extracted, score, decision, reasons = (
            perform_product_research(
                keyword,
                limit=50
            )
        )

        report = build_real_ebay_report(
            keyword,
            extracted
        )

        result = (
            report
            + "\n\n"
            + "🎯 SYSTEM PRODUCT SCORE\n"
            + f"{score}/100\n"
            + f"📌 {decision}\n\n"
            + "🧮 SCORE SƏBƏBLƏRİ\n"
            + "\n".join(
                f"• {r}"
                for r in reasons
            )
        )

        try:
            await wait.delete()
        except Exception:
            pass

        await send_long_message(
            update,
            result
        )

    except Exception as error:

        print(
            "eBay command error:",
            repr(error)
        )

        try:
            await wait.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "❌ eBay xətası:\n\n"
            + str(error)[:1800]
        )


# ============================================================
# ANALYZE COMMAND
# ============================================================

async def analyze_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(
            "⚠️ Misal:\n\n"
            "/analyze portable mini vacuum cleaner wireless"
        )

        return

    if not gemini_client:

        await update.message.reply_text(
            "❌ GEMINI_API_KEY tapılmadı."
        )

        return

    keyword = " ".join(
        context.args
    )

    wait = await update.message.reply_text(
        "🧠 AI PRODUCT BRAIN işə düşdü...\n"
        "🔎 REAL eBay US məlumatları alınır...\n"
        "📊 Qiymətlər və seller məlumatları analiz edilir..."
    )

    try:

        extracted, score, decision, reasons = (
            perform_product_research(
                keyword,
                limit=50
            )
        )

        answer = ai_product_analysis(
            keyword,
            extracted,
            score,
            decision
        )

        try:
            await wait.delete()
        except Exception:
            pass

        await send_long_message(
            update,
            answer
        )

    except Exception as error:

        print(
            "Analyze error:",
            repr(error)
        )

        try:
            await wait.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "❌ Analiz xətası:\n\n"
            + str(error)[:1800]
        )


# ============================================================
# AI COMMAND
# ============================================================

async def ai_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(
            "⚠️ Misal:\n\n"
            "/ai portable mini vacuum cleaner wireless"
        )

        return

    if not gemini_client:

        await update.message.reply_text(
            "❌ GEMINI_API_KEY tapılmadı."
        )

        return

    user_prompt = " ".join(
        context.args
    )

    # --------------------------------------------------------
    # PRODUCT DETECTION
    # --------------------------------------------------------

    product_words = [
        "vacuum",
        "cleaner",
        "bed",
        "frother",
        "holder",
        "stand",
        "light",
        "lamp",
        "roller",
        "label maker",
        "phone",
        "charger",
        "organizer",
        "brush",
        "portable",
        "wireless",
        "magnetic",
        "pet",
        "kitchen",
        "car",
        "keyboard",
    ]

    looks_like_product = any(
        word in user_prompt.lower()
        for word in product_words
    )

    # --------------------------------------------------------
    # AUTOMATIC REAL EBAY PRODUCT ANALYSIS
    # --------------------------------------------------------

    if looks_like_product:

        wait = await update.message.reply_text(
            "🔎 Məhsul aşkarlandı...\n"
            "🇺🇸 Real eBay US datası alınır...\n"
            "🧠 AI real məlumatı analiz edir..."
        )

        try:

            extracted, score, decision, reasons = (
                perform_product_research(
                    user_prompt,
                    limit=50
                )
            )

            answer = ai_product_analysis(
                user_prompt,
                extracted,
                score,
                decision
            )

            try:
                await wait.delete()
            except Exception:
                pass

            await send_long_message(
                update,
                answer
            )

            return

        except Exception as error:

            print(
                "AI product search error:",
                repr(error)
            )

            try:
                await wait.delete()
            except Exception:
                pass

            await update.message.reply_text(
                "❌ Real eBay analizində xəta oldu:\n\n"
                + str(error)[:1500]
            )

            return

    # --------------------------------------------------------
    # GENERAL AI
    # --------------------------------------------------------

    prompt = f"""
Sən eBay US dropshipping köməkçisisən.

İstifadəçinin sualı:

{user_prompt}

Qaydalar:

- Azərbaycan dilində cavab ver.
- Rəqəm bilmirsənsə uydurma.
- Sold count uydurma.
- Sell-through uydurma.
- Supplier qiyməti uydurma.
- Trend rəqəmi uydurma.
- Praktik və qısa cavab ver.
"""

    try:

        answer = ask_ai(
            prompt
        )

        await send_long_message(
            update,
            "🤖 AI BRAIN:\n\n"
            + answer
        )

    except Exception as error:

        print(
            "Gemini error:",
            repr(error)
        )

        await update.message.reply_text(
            "❌ AI xətası:\n"
            + str(error)[:1500]
        )


# ============================================================
# TREND COMMAND
# ============================================================

async def trend_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not gemini_client:

        await update.message.reply_text(
            "❌ GEMINI_API_KEY tapılmadı."
        )

        return

    wait = await update.message.reply_text(
        "🔥 AI product research ideyaları hazırlanır..."
    )

    prompt = """
Sən eBay US dropshipping product research AI-sən.

Mənə 10 məhsul araşdırma ideyası ver.

Məhsullar:

- kiçik və asan göndərilə bilən olsun
- mümkün qədər aşağı return riskli olsun
- çox kövrək olmasın
- çox böyük/volumetrik olmasın
- mümkün qədər geniş istifadə sahəsi olsun

ÇOX VACİB:

Heç bir real satış sayı iddia etmə.

Heç bir sold count yazma.

Heç bir sell-through rate yazma.

Heç bir supplier qiyməti uydurma.

Heç bir "viral" və ya "trend" iddiasını fakt kimi göstərmə.

Sadəcə araşdırmağa dəyər məhsul ideyaları ver.

Azərbaycan dilində cavab ver.

Format:

1. Product:
Category:
Why research:
Main risk:

2. Product:
Category:
Why research:
Main risk:
"""

    try:

        answer = ask_ai(
            prompt
        )

        try:
            await wait.delete()
        except Exception:
            pass

        await send_long_message(
            update,
            "🔥 AI PRODUCT RESEARCH IDEAS\n\n"
            + answer
        )

    except Exception as error:

        print(
            "Trend error:",
            repr(error)
        )

        try:
            await wait.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "❌ Trend AI xətası:\n"
            + str(error)[:1200]
        )


# ============================================================
# PROFIT CALCULATOR
# ============================================================

def calculate_profit(
    supplier_price,
    ebay_price,
    shipping_cost=0.0,
    shipping_charge=0.0
):

    final_value_fee = (
        ebay_price * 0.1325
    )

    fixed_fee = 0.30

    total_ebay_fees = (
        final_value_fee
        + fixed_fee
    )

    total_costs = (
        supplier_price
        + shipping_cost
    )

    net_profit = (
        ebay_price
        + shipping_charge
        - total_costs
        - total_ebay_fees
    )

    if ebay_price > 0:

        margin = (
            net_profit /
            ebay_price
        ) * 100

    else:

        margin = 0

    return (
        total_ebay_fees,
        final_value_fee,
        fixed_fee,
        net_profit,
        margin
    )


async def profit_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    args = context.args

    if len(args) < 2:

        await update.message.reply_text(
            "⚠️ Format:\n\n"
            "/profit <supplier> <ebay> [shipping]\n\n"
            "Misal:\n"
            "/profit 9.20 24.99 3"
        )

        return

    try:

        supplier_price = float(
            args[0]
        )

        ebay_price = float(
            args[1]
        )

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

            raise ValueError

        (
            total_fees,
            final_value_fee,
            fixed_fee,
            net_profit,
            margin
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
            "💰 PROFIT CALCULATOR\n\n"

            f"🛒 Supplier: "
            f"${supplier_price:.2f}\n"

            f"🏷 eBay satış: "
            f"${ebay_price:.2f}\n"

            f"🚚 Shipping: "
            f"${shipping_cost:.2f}\n\n"

            "💸 eBay fee estimate:\n"

            f"• Final Value Fee: "
            f"${final_value_fee:.2f}\n"

            f"• Fixed Fee: "
            f"${fixed_fee:.2f}\n"

            f"• Total eBay fees: "
            f"${total_fees:.2f}\n\n"

            f"💵 Net profit: "
            f"${net_profit:.2f}\n"

            f"📈 Margin: "
            f"{margin:.2f}%\n\n"

            f"🎯 Result: {status}\n\n"

            "⚠️ Bu sadələşdirilmiş research "
            "hesablamasıdır. Real eBay fee "
            "kateqoriyaya və hesaba görə dəyişə bilər."
        )

        await update.message.reply_text(
            response
        )

    except ValueError:

        await update.message.reply_text(
            "❌ Düzgün rəqəm yaz.\n\n"
            "Misal:\n"
            "/profit 9.20 24.99 3"
        )


# ============================================================
# TITLE COMMAND
# ============================================================

async def title_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(
            "⚠️ Misal:\n"
            "/title portable mini vacuum cleaner wireless"
        )

        return

    if not gemini_client:

        await update.message.reply_text(
            "❌ GEMINI_API_KEY tapılmadı."
        )

        return

    product = " ".join(
        context.args
    )

    prompt = f"""
Create exactly 3 eBay US titles for:

{product}

Rules:

- English.
- Maximum 80 characters.
- Do not invent brand.
- Do not invent specifications.
- Do not invent battery size.
- Do not invent suction power.
- Do not invent material.
- Do not write Best Seller.
- Do not write Top Rated.
- Do not write Fast Shipping.
- Do not write Free Shipping.
- Do not write fake claims.
- Use useful search keywords.
- No emojis.
- Exactly 3 lines.
- No explanation.
"""

    try:

        answer = ask_ai(
            prompt
        )

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
                title
            )

            title = " ".join(
                title.split()
            )

            title = title[
                :80
            ].strip()

            if title:
                titles.append(
                    title
                )

        titles = titles[:3]

        response = (
            "🏷 EBAY SEO TITLES\n\n"
        )

        for index, title in enumerate(
            titles,
            1
        ):

            response += (
                f"{index}. {title}\n"
                f"📏 {len(title)}/80\n\n"
            )

        await update.message.reply_text(
            response
        )

    except Exception as error:

        print(
            "Title error:",
            repr(error)
        )

        await update.message.reply_text(
            "❌ Title AI xətası:\n"
            + str(error)[:1200]
        )


# ============================================================
# FLASK
# ============================================================

@app.route("/")
def index():

    return (
        "eBay Dropshipping AI Brain "
        "24/7 Aktivdir!",
        200
    )


@app.route("/health")
def health():

    return {
        "status": "ok",
        "telegram":
            bool(TELEGRAM_TOKEN),

        "gemini":
            bool(GEMINI_API_KEY),

        "ebay":
            bool(
                EBAY_CLIENT_ID
                and
                EBAY_CLIENT_SECRET
            ),

        "gemini_model":
            GEMINI_MODEL,

    }, 200


def run_flask():

    port = int(
        os.environ.get(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not TELEGRAM_TOKEN:

        raise RuntimeError(
            "TELEGRAM_TOKEN tapılmadı."
        )

    if not GEMINI_API_KEY:

        print(
            "⚠️ GEMINI_API_KEY yoxdur."
        )

    if not EBAY_CLIENT_ID:

        print(
            "⚠️ EBAY_CLIENT_ID yoxdur."
        )

    if not EBAY_CLIENT_SECRET:

        print(
            "⚠️ EBAY_CLIENT_SECRET yoxdur."
        )

    Thread(
        target=run_flask,
        daemon=True
    ).start()

    telegram_app = (
        Application
        .builder()
        .token(
            TELEGRAM_TOKEN
        )
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
            "ebay",
            ebay_command
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

    telegram_app.add_handler(
        CommandHandler(
            "trend",
            trend_command
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

    print(
        "🤖 eBay Dropshipping AI Brain "
        "uğurla işə düşdü."
    )

    telegram_app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
