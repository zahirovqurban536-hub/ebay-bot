import os
import re
import base64
import math
import statistics
import time
from collections import Counter
from threading import Thread, Lock
from typing import Any, Optional

import requests
from flask import Flask
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================================
# CONFIG
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
EBAY_CLIENT_ID = os.environ.get("EBAY_CLIENT_ID", "").strip()
EBAY_CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET", "").strip()

# Gemini 3.6 Flash is a current stable production model.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

EBAY_MARKETPLACE = "EBAY_US"
EBAY_TIMEOUT = 30
MAX_TELEGRAM_LENGTH = 3900
EBAY_SAMPLE_LIMIT = min(max(int(os.environ.get("EBAY_SAMPLE_LIMIT", "50")), 10), 50)

# Research estimate only. Change in Render Environment if your account/category differs.
EBAY_FEE_RATE = float(os.environ.get("EBAY_FEE_RATE", "0.1325"))
EBAY_FIXED_FEE = float(os.environ.get("EBAY_FIXED_FEE", "0.30"))

app = Flask(__name__)
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

_token_cache = {"token": None, "expires_at": 0.0}
_token_lock = Lock()

# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(value: Any, default: str = "") -> str:
    return default if value is None else str(value).strip()


def safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def money(value: Optional[float]) -> str:
    return "N/A" if value is None else f"${value:,.2f}"


def normalize_title(title: str) -> str:
    text = clean_text(title).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def percentile(values, p):
    values = sorted(v for v in values if isinstance(v, (int, float)))
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    k = (len(values) - 1) * (p / 100)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return values[int(k)]
    return values[f] + (values[c] - values[f]) * (k - f)


def trimmed_values(values):
    if len(values) < 8:
        return list(values)
    lo = percentile(values, 5)
    hi = percentile(values, 95)
    return [v for v in values if lo <= v <= hi]


def split_telegram_text(text: str):
    if not text:
        return [""]
    chunks = []
    remaining = str(text)

    while len(remaining) > MAX_TELEGRAM_LENGTH:
        cut = remaining.rfind("\n", 0, MAX_TELEGRAM_LENGTH)
        if cut < int(MAX_TELEGRAM_LENGTH * 0.60):
            cut = remaining.rfind(" ", 0, MAX_TELEGRAM_LENGTH)
        if cut < int(MAX_TELEGRAM_LENGTH * 0.60):
            cut = MAX_TELEGRAM_LENGTH
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()

    if remaining:
        chunks.append(remaining)
    return chunks


async def send_long_message(update: Update, text: str):
    for chunk in split_telegram_text(text):
        await update.message.reply_text(chunk)


# ============================================================
# GEMINI AI BRAIN
# ============================================================

def ask_ai(prompt: str) -> str:
    if not gemini_client:
        raise RuntimeError("GEMINI_API_KEY tapılmadı.")

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    answer = clean_text(getattr(response, "text", ""))
    if not answer:
        raise RuntimeError("Gemini boş cavab qaytardı.")
    return answer


def ai_product_brain(
    keyword: str,
    report: str,
    score: int,
    decision: str,
    confidence: str,
    supplier_price: Optional[float] = None,
) -> str:

    supplier_info = (
        f"Supplier qiyməti: {money(supplier_price)}"
        if supplier_price is not None
        else "Supplier qiyməti: VERİLMƏYİB"
    )

    prompt = f"""
Sən eBay US dropshipping üçün peşəkar product-research AI beynisən.

MƏHSUL:
{keyword}

REAL EBAY BROWSE API DATA:
{report}

SYSTEM SCORE:
{score}/100

SYSTEM DECISION:
{decision}

DATA CONFIDENCE:
{confidence}

{supplier_info}

QƏTİ QAYDALAR:
- Listing sayı satış sayı deyil.
- Seller feedback satış sayı deyil.
- Sold count yoxdursa uydurma.
- Sell-through yoxdursa uydurma.
- Supplier qiyməti yoxdursa profit rəqəmi uydurma.
- Trend/viral status API-də yoxdursa fakt kimi yazma.
- $100 kimi outlier qiyməti normal bazar qiyməti kimi qəbul etmə.
- Median və qiymət sıxlığını əsas götür.
- Böyük seller-ləri feedback datası ilə əsaslandır.
- US item-location payını nəzərə al.
- Təkrarlanan/oxşar title-ları saturation siqnalı kimi qiymətləndir.
- System score-u və qərarı dəyişmə.
- Faktla ehtimalı ayır.
- Azərbaycan dilində yaz.
- Lazımsız ümumi məsləhət vermə.

FORMAT:

🧠 AI PRODUCT BRAIN

📦 Məhsul:
{keyword}

🇺🇸 REAL EBAY BAZARI
- Listing sayı:
- API sample:
- Normal qiymət zonası:
- Median:
- US location payı:
- Free shipping payı:

🏆 RƏQABƏT
- Səviyyə:
- Əsas səbəb:
- Böyük seller rəqabəti:

💰 QİYMƏT STRATEGİYASI
- Median bazar qiyməti:
- Aşağı qiymət təzyiqi:
- Outlier:
- Realistic test price:

📈 SATIŞ POTENSİALI
Sold count/sell-through yoxdursa bunu açıq yaz.
Yalnız mövcud bazar siqnallarına əsaslan.

⚠️ RİSKLƏR
- Rəqabət:
- Qiymət:
- Shipping:
- Məhsul tipi:
- Data çatışmazlığı:

🎯 PRODUCT SCORE:
{score}/100

📌 QƏRAR:
{decision}

💡 SON FİKİR:
3-5 konkret cümlə ilə qərarı izah et.
"""
    return ask_ai(prompt)


# ============================================================
# EBAY OAUTH
# ============================================================

def get_ebay_application_token() -> str:
    if not EBAY_CLIENT_ID or not EBAY_CLIENT_SECRET:
        raise RuntimeError("EBAY_CLIENT_ID və ya EBAY_CLIENT_SECRET yoxdur.")

    now = time.time()

    with _token_lock:
        if _token_cache["token"] and now < _token_cache["expires_at"]:
            return _token_cache["token"]

        credentials = f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}"
        encoded = base64.b64encode(credentials.encode()).decode()

        response = requests.post(
            "https://api.ebay.com/identity/v1/oauth2/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {encoded}",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=EBAY_TIMEOUT,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"eBay OAuth xətası: {response.status_code} "
                f"{response.text[:700]}"
            )

        result = response.json()
        token = result.get("access_token")
        expires_in = safe_float(result.get("expires_in")) or 7200

        if not token:
            raise RuntimeError("eBay access token alınmadı.")

        _token_cache["token"] = token
        _token_cache["expires_at"] = time.time() + max(60, expires_in - 120)
        return token


# ============================================================
# EBAY SEARCH
# ============================================================

def ebay_search_products(keyword: str) -> dict:
    token = get_ebay_application_token()

    response = requests.get(
        "https://api.ebay.com/buy/browse/v1/item_summary/search",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": EBAY_MARKETPLACE,
        },
        params={
            "q": keyword,
            "limit": EBAY_SAMPLE_LIMIT,
            "fieldgroups": "EXTENDED",
        },
        timeout=EBAY_TIMEOUT,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"eBay Search xətası: {response.status_code} "
            f"{response.text[:900]}"
        )

    return response.json()


# ============================================================
# EBAY DATA EXTRACTION
# ============================================================

def extract_ebay_data(data: dict) -> dict:
    items = data.get("itemSummaries") or []
    total = int(safe_float(data.get("total")) or 0)

    prices = []
    sellers = []
    titles = []
    conditions = Counter()
    shipping_costs = []

    us_location_count = 0
    fixed_price_count = 0
    auction_count = 0
    free_shipping_count = 0
    promoted_count = 0
    top_rated_count = 0

    for item in items:
        if not isinstance(item, dict):
            continue

        title = clean_text(item.get("title"))
        if title:
            titles.append(title)

        price_data = item.get("price") or {}
        price = (
            safe_float(price_data.get("value"))
            if isinstance(price_data, dict)
            else safe_float(price_data)
        )
        if price is not None and price >= 0:
            prices.append(price)

        seller = item.get("seller") or {}
        if isinstance(seller, dict):
            feedback = safe_float(seller.get("feedbackScore"))
            if feedback is not None:
                sellers.append(feedback)

        location = item.get("itemLocation") or {}
        if isinstance(location, dict):
            country = clean_text(location.get("country")).upper()
            if country == "US":
                us_location_count += 1

        condition = clean_text(item.get("condition"), "Unknown")
        conditions[condition] += 1

        buying_options = item.get("buyingOptions") or []
        if "FIXED_PRICE" in buying_options:
            fixed_price_count += 1
        if "AUCTION" in buying_options:
            auction_count += 1

        if item.get("priorityListing") is True:
            promoted_count += 1
        if item.get("topRatedBuyingExperience") is True:
            top_rated_count += 1

        shipping_options = item.get("shippingOptions") or []
        if isinstance(shipping_options, list):
            values = []
            for shipping in shipping_options:
                if not isinstance(shipping, dict):
                    continue
                sd = shipping.get("shippingCost") or {}
                value = (
                    safe_float(sd.get("value"))
                    if isinstance(sd, dict)
                    else safe_float(sd)
                )
                if value is not None and value >= 0:
                    values.append(value)

            if values:
                best = min(values)
                shipping_costs.append(best)
                if best == 0:
                    free_shipping_count += 1

    sample_prices = trimmed_values(prices)

    return {
        "items": items,
        "total": total,
        "sample_size": len(items),
        "prices": prices,
        "sample_prices": sample_prices,
        "avg": statistics.mean(sample_prices) if sample_prices else None,
        "median": statistics.median(sample_prices) if sample_prices else None,
        "p10": percentile(sample_prices, 10),
        "p25": percentile(sample_prices, 25),
        "p75": percentile(sample_prices, 75),
        "p90": percentile(sample_prices, 90),
        "sellers": sellers,
        "titles": titles,
        "conditions": conditions,
        "shipping_costs": shipping_costs,
        "us_location_count": us_location_count,
        "fixed_price_count": fixed_price_count,
        "auction_count": auction_count,
        "free_shipping_count": free_shipping_count,
        "promoted_count": promoted_count,
        "top_rated_count": top_rated_count,
    }


# ============================================================
# PROFESSIONAL SCORE
# ============================================================

def calculate_score(data: dict):
    total = data["total"]
    sample = max(1, data["sample_size"])
    prices = data["sample_prices"]
    sellers = data["sellers"]
    titles = data["titles"]

    score = 100
    reasons = []

    # Competition
    if total <= 300:
        penalty = 0
    elif total <= 1000:
        penalty = 5
    elif total <= 3000:
        penalty = 10
    elif total <= 10000:
        penalty = 18
    elif total <= 20000:
        penalty = 26
    else:
        penalty = 35

    score -= penalty
    reasons.append(f"Listing rəqabəti: -{penalty}")

    # Price pressure
    if prices:
        median_price = statistics.median(prices)
        low_price_ratio = sum(
            1 for p in prices if p <= median_price * 0.90
        ) / len(prices)

        if median_price < 10:
            penalty = 15
        elif median_price < 15:
            penalty = 11
        elif median_price < 20:
            penalty = 6
        else:
            penalty = 0

        if low_price_ratio >= 0.45:
            penalty += 5
        elif low_price_ratio >= 0.30:
            penalty += 2

        penalty = min(penalty, 20)
        score -= penalty
        reasons.append(f"Aşağı qiymət təzyiqi: -{penalty}")

    # Strong sellers
    if sellers:
        strong_10k = sum(s >= 10000 for s in sellers) / len(sellers)
        strong_100k = sum(s >= 100000 for s in sellers) / len(sellers)

        if strong_100k >= 0.25:
            penalty = 10
        elif strong_10k >= 0.40:
            penalty = 7
        elif strong_10k >= 0.20:
            penalty = 4
        else:
            penalty = 0

        score -= penalty
        reasons.append(f"Güclü seller rəqabəti: -{penalty}")

    # Duplicate titles
    normalized = [normalize_title(t) for t in titles if normalize_title(t)]
    duplicate_ratio = 0.0

    if normalized:
        counts = Counter(normalized)
        duplicate_ratio = (
            sum(c - 1 for c in counts.values() if c > 1)
            / len(normalized)
        )

        if duplicate_ratio >= 0.60:
            penalty = 10
        elif duplicate_ratio >= 0.40:
            penalty = 8
        elif duplicate_ratio >= 0.25:
            penalty = 6
        elif duplicate_ratio >= 0.10:
            penalty = 3
        else:
            penalty = 0

        score -= penalty
        reasons.append(f"Oxşar/təkrarlanan başlıqlar: -{penalty}")

    # US location
    us_ratio = data["us_location_count"] / sample

    if us_ratio < 0.30:
        penalty = 8
    elif us_ratio < 0.60:
        penalty = 4
    else:
        penalty = 0

    score -= penalty
    reasons.append(f"US location siqnalı: -{penalty}")

    # Shipping competition
    shipping = data["shipping_costs"]
    if shipping:
        free_ratio = data["free_shipping_count"] / len(shipping)

        if free_ratio < 0.40:
            penalty = 4
        elif free_ratio < 0.60:
            penalty = 2
        else:
            penalty = 0

        score -= penalty
        reasons.append(f"Shipping rəqabəti: -{penalty}")

    score = max(0, min(100, round(score)))

    if score >= 75:
        decision = "🟢 GO"
    elif score >= 55:
        decision = "🟡 MAYBE"
    else:
        decision = "🔴 NO-GO"

    if data["sample_size"] >= 40 and prices and sellers:
        confidence = "🟢 YÜKSƏK"
    elif data["sample_size"] >= 20 and prices:
        confidence = "🟡 ORTA"
    else:
        confidence = "🔴 AŞAĞI"

    metrics = {
        "us_ratio": us_ratio,
        "duplicate_ratio": duplicate_ratio,
    }

    return score, decision, confidence, reasons, metrics


# ============================================================
# PROFIT ENGINE
# ============================================================

def calculate_profit(supplier, sale, shipping=0.0):
    fee = sale * EBAY_FEE_RATE + EBAY_FIXED_FEE
    net = sale - supplier - shipping - fee
    margin = (net / sale * 100) if sale > 0 else 0
    return fee, net, margin


def max_supplier_price(sale, target_margin, shipping=0.0):
    target_profit = sale * (target_margin / 100)
    fee = sale * EBAY_FEE_RATE + EBAY_FIXED_FEE
    return sale - fee - shipping - target_profit


# ============================================================
# REPORT
# ============================================================

def build_report(keyword, data, score, decision, confidence,
                 reasons, metrics, supplier_price=None):

    prices = data["prices"]
    sample_prices = data["sample_prices"]
    sellers = data["sellers"]
    median_price = data["median"]

    us_pct = metrics["us_ratio"] * 100
    duplicate_pct = metrics["duplicate_ratio"] * 100

    lines = [
        "🔎 REAL EBAY US DATA",
        "",
        f"🔍 Search keyword: {keyword}",
        f"📦 eBay result count: {data['total']:,}",
        f"📊 API sample analyzed: {data['sample_size']} listings",
        "",
        "💰 REAL PRICE DATA",
        f"• Minimum sample: {money(min(prices) if prices else None)}",
        f"• Maximum sample: {money(max(prices) if prices else None)}",
        f"• 10th percentile: {money(data['p10'])}",
        f"• 25th percentile: {money(data['p25'])}",
        f"• Average sample: {money(data['avg'])}",
        f"• Median sample: {money(median_price)}",
        f"• 75th percentile: {money(data['p75'])}",
        f"• 90th percentile: {money(data['p90'])}",
        "• 5%-95% trimmed sample outlier təsirini azaldır.",
        "",
        "👥 REAL SELLER DATA",
        f"• Seller feedback sample: {len(sellers)}",
        f"• Minimum feedback: {min(sellers) if sellers else 'N/A'}",
        f"• Maximum feedback: {max(sellers) if sellers else 'N/A'}",
        f"• 10,000+ feedback sellers: {sum(s >= 10000 for s in sellers)}",
        f"• 100,000+ feedback sellers: {sum(s >= 100000 for s in sellers)}",
        "",
        "🇺🇸 US MARKET SIGNAL",
        f"• Item location = US: {data['us_location_count']}/{data['sample_size']} ({us_pct:.1f}%)",
        f"• Fixed price: {data['fixed_price_count']}/{data['sample_size']}",
        f"• Auction: {data['auction_count']}/{data['sample_size']}",
        f"• Free shipping: {data['free_shipping_count']}/{data['sample_size']}",
        f"• Promoted listings visible: {data['promoted_count']}/{data['sample_size']}",
        f"• Top Rated Plus signal: {data['top_rated_count']}/{data['sample_size']}",
        "",
        "🧠 SATURATION SIGNALS",
        f"• Similar/duplicate normalized titles: {duplicate_pct:.1f}%",
        f"• New condition: {data['conditions'].get('New', 0)}",
        "",
        "📋 REAL SAMPLE LISTINGS",
    ]

    for i, item in enumerate(data["items"][:15], 1):
        title = clean_text(item.get("title"), "Adsız məhsul")

        price_data = item.get("price") or {}
        price = (
            safe_float(price_data.get("value"))
            if isinstance(price_data, dict)
            else safe_float(price_data)
        )

        seller = item.get("seller") or {}
        feedback = seller.get("feedbackScore", "N/A") if isinstance(seller, dict) else "N/A"
        feedback_pct = seller.get("feedbackPercentage", "N/A") if isinstance(seller, dict) else "N/A"

        location = item.get("itemLocation") or {}
        country = clean_text(location.get("country"), "N/A") if isinstance(location, dict) else "N/A"

        shipping_values = []
        for ship in item.get("shippingOptions") or []:
            if not isinstance(ship, dict):
                continue
            sd = ship.get("shippingCost") or {}
            value = (
                safe_float(sd.get("value"))
                if isinstance(sd, dict)
                else safe_float(sd)
            )
            if value is not None:
                shipping_values.append(value)

        ship = min(shipping_values) if shipping_values else None

        lines.append(
            f"\n{i}. {title}\n"
            f"   💵 {money(price)} | 👤 {feedback} | ⭐ {feedback_pct}%\n"
            f"   📍 {country} | 🚚 {money(ship)}"
        )

    lines.extend([
        "",
        "⚠️ DATA LIMITATIONS",
        "• Browse API sold count vermir.",
        "• Browse API sell-through rate vermir.",
        "• Seller feedback satış sayı deyil.",
        "• Supplier qiyməti eBay datası deyil.",
        "• Trend/viral status bu nəticədən avtomatik təsdiqlənmir.",
        "",
        "🎯 SYSTEM PRODUCT SCORE",
        f"{score}/100",
        f"📌 {decision}",
        "",
        "🧮 SCORE SƏBƏBLƏRİ",
    ])

    lines.extend(f"• {reason}" for reason in reasons)

    if supplier_price is not None and median_price:
        fee, net, margin = calculate_profit(
            supplier_price,
            median_price,
            0,
        )

        lines.extend([
            "",
            "💰 SUPPLIER / PROFIT CHECK",
            f"• Supplier: {money(supplier_price)}",
            f"• Median test sale: {money(median_price)}",
            f"• Estimated eBay fee: {money(fee)}",
            f"• Estimated net profit: {money(net)}",
            f"• Estimated margin: {margin:.1f}%",
            f"• 10% margin üçün max supplier: {money(max_supplier_price(median_price, 10))}",
            f"• 15% margin üçün max supplier: {money(max_supplier_price(median_price, 15))}",
            "• Bu research estimate-dir; real eBay fee kateqoriyaya/hesaba görə dəyişə bilər.",
        ])

    return "\n".join(lines)


# ============================================================
# COMMANDS
# ============================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 eBay Professional AI Brain\n\n"
        "🔎 /ebay <məhsul> — real eBay US data\n"
        "🧠 /analyze <məhsul> — real data + AI qərar\n"
        "💰 /analyze <məhsul> | supplier=5.20 — profit daxil\n"
        "💵 /profit <supplier> <sale> [shipping]\n"
        "🏷 /title <məhsul> — 3 SEO title\n"
        "🔥 /trend — AI product research ideas\n"
        "🤖 /ai <sual> — ümumi AI\n\n"
        "Misal:\n"
        "/analyze portable mini vacuum cleaner wireless | supplier=5.20"
    )


def parse_analyze_args(args):
    raw = " ".join(args).strip()
    supplier = None

    match = re.search(
        r"(?:supplier|cost|alış)\s*=\s*\$?\s*([0-9]+(?:\.[0-9]+)?)",
        raw,
        re.I,
    )

    if match:
        supplier = float(match.group(1))
        raw = raw[:match.start()] + raw[match.end():]

    return raw.replace("||", "|").strip(" |"), supplier


async def ebay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Misal: /ebay calming pet bed")
        return

    keyword = " ".join(context.args)

    wait = await update.message.reply_text(
        "🔎 Real eBay US datası alınır...\n"
        "📊 Qiymət + seller + shipping analiz edilir..."
    )

    try:
        data = extract_ebay_data(ebay_search_products(keyword))

        if not data["items"]:
            result = f"❌ eBay-də '{keyword}' üçün listing tapılmadı."
        else:
            score, decision, confidence, reasons, metrics = calculate_score(data)
            result = build_report(
                keyword,
                data,
                score,
                decision,
                confidence,
                reasons,
                metrics,
            )

        try:
            await wait.delete()
        except Exception:
            pass

        await send_long_message(update, result)

    except Exception as error:
        try:
            await wait.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "❌ Real eBay analizində xəta oldu:\n\n"
            + str(error)[:1800]
        )


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Misal:\n"
            "/analyze portable mini vacuum cleaner wireless\n\n"
            "Supplier ilə:\n"
            "/analyze portable mini vacuum cleaner wireless | supplier=5.20"
        )
        return

    keyword, supplier_price = parse_analyze_args(context.args)

    if not keyword:
        await update.message.reply_text("❌ Məhsul adı boşdur.")
        return

    wait = await update.message.reply_text(
        "🧠 PROFESSIONAL AI BRAIN işə düşdü...\n"
        "🔎 Real eBay US datası alınır...\n"
        "📊 Rəqabət + qiymət + seller + shipping hesablanır..."
    )

    try:
        data = extract_ebay_data(ebay_search_products(keyword))

        if not data["items"]:
            raise RuntimeError("eBay-də bu axtarış üçün listing tapılmadı.")

        score, decision, confidence, reasons, metrics = calculate_score(data)

        report = build_report(
            keyword,
            data,
            score,
            decision,
            confidence,
            reasons,
            metrics,
            supplier_price,
        )

        if gemini_client:
            try:
                result = ai_product_brain(
                    keyword,
                    report,
                    score,
                    decision,
                    confidence,
                    supplier_price,
                )
            except Exception as ai_error:
                print("AI error:", repr(ai_error))
                result = report
        else:
            result = report

        try:
            await wait.delete()
        except Exception:
            pass

        await send_long_message(update, result)

    except Exception as error:
        try:
            await wait.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "❌ Real eBay analizində xəta oldu:\n\n"
            + str(error)[:1800]
        )


async def profit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Format:\n/profit <supplier> <sale> [shipping]\n\n"
            "Misal:\n/profit 5.20 12.99 0"
        )
        return

    try:
        supplier = float(context.args[0])
        sale = float(context.args[1])
        shipping = float(context.args[2]) if len(context.args) >= 3 else 0.0

        fee, net, margin = calculate_profit(supplier, sale, shipping)
        status = "🟢 GO" if net > 0 else "🟡 BREAK-EVEN" if net == 0 else "🔴 NO-GO"

        await update.message.reply_text(
            "💰 PROFIT ENGINE\n\n"
            f"🛒 Supplier: {money(supplier)}\n"
            f"🏷 Sale: {money(sale)}\n"
            f"🚚 Shipping: {money(shipping)}\n"
            f"💸 Estimated eBay fee: {money(fee)}\n"
            f"💵 Net profit: {money(net)}\n"
            f"📈 Margin: {margin:.1f}%\n\n"
            f"🎯 {status}\n\n"
            "⚠️ Research estimate; actual eBay fees may vary."
        )

    except ValueError:
        await update.message.reply_text("❌ Qiymətləri rəqəmlə yaz.")


async def title_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Misal: /title portable mini vacuum cleaner"
        )
        return

    if not gemini_client:
        await update.message.reply_text("❌ GEMINI_API_KEY tapılmadı.")
        return

    product = " ".join(context.args)

    prompt = f"""
Create exactly 3 eBay US titles for:
{product}

Rules:
- English.
- Maximum 80 characters each.
- Use only facts supported by the product name.
- No invented brand/specifications.
- No fake claims.
- No emojis.
- Exactly 3 lines.
"""

    try:
        answer = ask_ai(prompt)
        titles = []

        for line in answer.splitlines():
            line = re.sub(
                r"^\s*(?:\d+[\.\)\-:]|\-|\*)\s*",
                "",
                line.strip(),
            )
            if line:
                titles.append(" ".join(line.split())[:80])

        titles = titles[:3]

        if not titles:
            raise RuntimeError("AI title qaytarmadı.")

        result = "🏷 EBAY SEO TITLES\n\n"

        for i, title in enumerate(titles, 1):
            result += f"{i}. {title}\n📏 {len(title)}/80\n\n"

        await update.message.reply_text(result)

    except Exception as error:
        await update.message.reply_text(
            "❌ Title xətası:\n" + str(error)[:1000]
        )


async def trend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not gemini_client:
        await update.message.reply_text("❌ GEMINI_API_KEY tapılmadı.")
        return

    prompt = """
Sən eBay US dropshipping product researcher-sən.

5 məhsul araşdırma ideyası ver.

Qəti qaydalar:
- Sold count uydurma.
- Sell-through uydurma.
- Supplier price uydurma.
- Trend/viral sözünü sübut olmadan fakt kimi yazma.
- Kiçik, asan göndərilən, aşağı return riskli məhsullara üstünlük ver.
- Hər məhsul üçün:
  Product:
  Category:
  Why research:
  Main risk:
  What to validate on eBay:
- Azərbaycan dilində yaz.
"""

    try:
        answer = ask_ai(prompt)
        await send_long_message(
            update,
            "🔥 AI PRODUCT RESEARCH IDEAS\n\n" + answer
        )
    except Exception as error:
        await update.message.reply_text(
            "❌ Trend AI xətası:\n" + str(error)[:1000]
        )


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Misal: /ai eBay dropshipping üçün məhsul ideyası ver"
        )
        return

    if not gemini_client:
        await update.message.reply_text("❌ GEMINI_API_KEY tapılmadı.")
        return

    question = " ".join(context.args)

    prompt = f"""
Sən eBay US dropshipping köməkçisisən.

İstifadəçinin sualı:
{question}

Qaydalar:
- Azərbaycan dilində cavab ver.
- Fakt bilmirsənsə uydurma.
- Sold count/sell-through yoxdursa bunu açıq de.
- Praktik və konkret cavab ver.
"""

    try:
        answer = ask_ai(prompt)
        await send_long_message(update, "🤖 AI BRAIN\n\n" + answer)
    except Exception as error:
        await update.message.reply_text(
            "❌ AI xətası:\n" + str(error)[:1200]
        )


# ============================================================
# FLASK / RENDER HEALTH
# ============================================================

@app.route("/")
def index():
    return "eBay Professional AI Brain 24/7 Aktivdir!", 200


@app.route("/health")
def health():
    return {
        "status": "ok",
        "telegram": bool(TELEGRAM_TOKEN),
        "gemini": bool(GEMINI_API_KEY),
        "ebay": bool(EBAY_CLIENT_ID and EBAY_CLIENT_SECRET),
        "gemini_model": GEMINI_MODEL,
        "ebay_sample_limit": EBAY_SAMPLE_LIMIT,
    }, 200


def run_flask():
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)


# ============================================================
# MAIN
# ============================================================

def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN tapılmadı.")

    Thread(target=run_flask, daemon=True).start()

    telegram_app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("trend", trend_command))
    telegram_app.add_handler(CommandHandler("ebay", ebay_command))
    telegram_app.add_handler(CommandHandler("analyze", analyze_command))
    telegram_app.add_handler(CommandHandler("profit", profit_command))
    telegram_app.add_handler(CommandHandler("title", title_command))
    telegram_app.add_handler(CommandHandler("ai", ai_command))

    print("🤖 eBay Professional AI Brain uğurla işə düşdü.")

    telegram_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
