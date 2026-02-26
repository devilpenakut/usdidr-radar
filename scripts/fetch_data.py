"""
fetch_data.py
Ambil semua data real untuk dashboard USD/IDR:
  A. Spot rate (Frankfurter)
  B. BCA E-Rate (scraping)
  C. BI JISDOR (scraping bi.go.id)
  D. Historical 30D (Frankfurter)
  E. DXY (Yahoo Finance via yfinance)
  F. BI Rate (scraping / fallback)
  G. Berita terkini (NewsAPI)
  H. Sentimen Twitter (proxy dari berita)
  I. Volatility proxy (ATR 14D)

Output: data/market_data.json
"""
import os
import json
import datetime
import statistics
import time
import re

import requests
from bs4 import BeautifulSoup

# ── Config ──────────────────────────────────────────────────────────────────
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
DATE_OVERRIDE = os.environ.get("DATE_OVERRIDE", "").strip()
TODAY = (
    datetime.date.fromisoformat(DATE_OVERRIDE)
    if DATE_OVERRIDE
    else (datetime.datetime.utcnow() + datetime.timedelta(hours=7)).date()
)
DATE_30D_AGO = TODAY - datetime.timedelta(days=30)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; USDIDR-Radar/1.0)"}
OUTPUT_PATH = "data/market_data.json"

os.makedirs("data", exist_ok=True)


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")


# ── A + D: Spot & Historical (Frankfurter — gratis, no key) ─────────────────
def fetch_frankfurter():
    log("A+D: Fetching Frankfurter historical + spot...")
    url = f"https://api.frankfurter.app/{DATE_30D_AGO}..{TODAY}?from=USD&to=IDR"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        rates = {date: v["IDR"] for date, v in data["rates"].items()}
        sorted_dates = sorted(rates.keys())
        prices = [rates[d] for d in sorted_dates]
        spot = prices[-1] if prices else None
        prev = prices[-2] if len(prices) >= 2 else spot
        change_pct = round((spot - prev) / prev * 100, 3) if prev else 0

        log(f"  ✅ Spot: {spot} | Dates: {len(sorted_dates)} hari")
        return {
            "spot": spot,
            "change_pct": change_pct,
            "dates": sorted_dates,
            "prices": prices,
            "source": "frankfurter.app",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "label": "LIVE"
        }
    except Exception as e:
        log(f"  ❌ Frankfurter error: {e}")
        return {"spot": None, "prices": [], "dates": [], "label": "STALE", "error": str(e)}


# ── B: BCA E-Rate (scraping) ─────────────────────────────────────────────────
def fetch_bca_rate():
    log("B: Fetching BCA E-Rate...")
    url = "https://www.bca.co.id/id/informasi/kurs"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        # Cari tabel kurs
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            text = " ".join(c.get_text(strip=True) for c in cells)
            if "USD" in text or "Dollar Amerika" in text:
                nums = re.findall(r"[\d,]+\.\d+|[\d.]{5,}", text)
                nums = [float(n.replace(",", "")) for n in nums if float(n.replace(",", "")) > 1000]
                if len(nums) >= 2:
                    buy, sell = nums[0], nums[1]
                    log(f"  ✅ BCA Buy: {buy} | Sell: {sell}")
                    return {
                        "buy": buy, "sell": sell,
                        "mid": round((buy + sell) / 2, 2),
                        "source": "bca.co.id",
                        "timestamp": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%H:%M WIB"),
                        "label": "LIVE"
                    }
        raise ValueError("Tidak menemukan baris USD di tabel BCA")
    except Exception as e:
        log(f"  ⚠️ BCA scraping error: {e} — menggunakan proxy")
        return {"buy": None, "sell": None, "mid": None, "label": "PROXY", "error": str(e)}


# ── C: BI JISDOR ─────────────────────────────────────────────────────────────
def fetch_jisdor():
    log("C: Fetching BI JISDOR...")
    url = "https://www.bi.go.id/id/statistik/informasi-kurs/jisdor/default.aspx"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        # Cari tabel JISDOR
        table = soup.find("table", {"class": re.compile("table|grid", re.I)})
        if table:
            rows = table.find_all("tr")
            for row in rows[1:3]:  # baris pertama data
                cells = row.find_all("td")
                if len(cells) >= 2:
                    date_str = cells[0].get_text(strip=True)
                    rate_str = cells[1].get_text(strip=True).replace(",", "").replace(".", "")
                    if rate_str.isdigit() and int(rate_str) > 10000:
                        log(f"  ✅ JISDOR: {rate_str} ({date_str})")
                        return {
                            "rate": int(rate_str),
                            "date": date_str,
                            "source": "bi.go.id",
                            "label": "LIVE"
                        }
        raise ValueError("Tidak menemukan data JISDOR")
    except Exception as e:
        log(f"  ⚠️ JISDOR error: {e} — menggunakan proxy")
        return {"rate": None, "date": None, "label": "PROXY", "error": str(e)}


# ── E: DXY via yfinance ───────────────────────────────────────────────────────
def fetch_dxy():
    log("E: Fetching DXY...")
    try:
        import yfinance as yf
        dxy = yf.Ticker("DX-Y.NYB")
        hist = dxy.history(period="5d")
        if not hist.empty:
            latest = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2] if len(hist) >= 2 else latest
            change = round((latest - prev) / prev * 100, 3)
            log(f"  ✅ DXY: {round(latest, 2)} ({change:+}%)")
            return {
                "value": round(latest, 2),
                "change_pct": change,
                "source": "Yahoo Finance",
                "label": "LIVE"
            }
    except Exception as e:
        log(f"  ⚠️ DXY yfinance error: {e}")

    # Fallback: scraping via marketwatch
    try:
        r = requests.get("https://www.marketwatch.com/investing/index/dxy", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        val_el = soup.find("bg-quote", {"field": "Last"}) or soup.find("span", {"class": re.compile("value")})
        if val_el:
            val = float(val_el.get_text(strip=True).replace(",", ""))
            log(f"  ✅ DXY (MarketWatch): {val}")
            return {"value": val, "change_pct": None, "source": "MarketWatch", "label": "PROXY"}
    except Exception as e2:
        log(f"  ⚠️ DXY fallback error: {e2}")

    return {"value": None, "change_pct": None, "label": "STALE"}


# ── F: BI Rate ────────────────────────────────────────────────────────────────
def fetch_bi_rate():
    log("F: Fetching BI Rate...")
    # BI Rate jarang berubah — cek dari berita terbaru
    try:
        if NEWS_API_KEY:
            r = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": "BI rate Bank Indonesia suku bunga",
                    "language": "id",
                    "sortBy": "publishedAt",
                    "pageSize": 3,
                    "apiKey": NEWS_API_KEY
                },
                timeout=10
            )
            articles = r.json().get("articles", [])
            for a in articles:
                text = a.get("title", "") + " " + a.get("description", "")
                match = re.search(r"(\d+[.,]\d+)\s*%", text)
                if match:
                    rate = float(match.group(1).replace(",", "."))
                    if 2.0 <= rate <= 10.0:
                        log(f"  ✅ BI Rate dari berita: {rate}%")
                        return {"rate": rate, "source": "NewsAPI", "label": "LIVE"}
    except Exception as e:
        log(f"  ⚠️ BI Rate news error: {e}")

    # Known value fallback (update manual jika berubah)
    log("  ℹ️ BI Rate: menggunakan nilai terakhir diketahui (4.75%)")
    return {"rate": 4.75, "decision": "Hold", "source": "Known value", "label": "STALE"}


# ── G: Berita Terkini (NewsAPI) ───────────────────────────────────────────────
def fetch_news():
    log("G: Fetching berita terkini...")
    results = []

    if not NEWS_API_KEY:
        log("  ⚠️ NEWS_API_KEY tidak ada — menggunakan proxy dari scraping")
        return fetch_news_scraping()

    queries = [
        "rupiah USD IDR kurs",
        "Bank Indonesia rupiah dollar",
        "nilai tukar rupiah"
    ]
    seen_titles = set()
    for q in queries:
        try:
            r = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": q,
                    "language": "id",
                    "sortBy": "publishedAt",
                    "pageSize": 5,
                    "from": (TODAY - datetime.timedelta(days=1)).isoformat(),
                    "apiKey": NEWS_API_KEY
                },
                timeout=10
            )
            for a in r.json().get("articles", []):
                title = a.get("title", "")
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    results.append({
                        "title": title,
                        "source": a.get("source", {}).get("name", ""),
                        "datetime": a.get("publishedAt", "")[:16].replace("T", " "),
                        "url": a.get("url", ""),
                        "classification": classify_news(title)
                    })
        except Exception as e:
            log(f"  ⚠️ NewsAPI query error: {e}")
        if len(results) >= 5:
            break

    log(f"  ✅ {len(results)} berita dikumpulkan")
    return results[:5]


def fetch_news_scraping():
    """Fallback: scraping dari cnbcindonesia.com"""
    try:
        r = requests.get(
            "https://www.cnbcindonesia.com/search?query=rupiah+kurs+dollar",
            headers=HEADERS, timeout=15
        )
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.find_all("article", limit=5)
        results = []
        for item in items:
            title_el = item.find(["h2", "h3", "a"])
            if title_el:
                title = title_el.get_text(strip=True)
                results.append({
                    "title": title,
                    "source": "CNBCIndonesia",
                    "datetime": TODAY.isoformat(),
                    "classification": classify_news(title),
                    "label": "PROXY"
                })
        return results
    except Exception as e:
        log(f"  ❌ News scraping error: {e}")
        return []


def classify_news(title: str) -> str:
    title_lower = title.lower()
    bullish_keywords = ["menguat", "naik", "apresiasi", "positif", "stabil", "surplus",
                        "deal", "investasi masuk", "cadangan devisa", "beli rupiah"]
    bearish_keywords = ["melemah", "turun", "depresiasi", "tekanan", "defisit", "jual",
                        "anjlok", "rekor rendah", "risk off", "capital outflow"]
    bull_score = sum(1 for k in bullish_keywords if k in title_lower)
    bear_score = sum(1 for k in bearish_keywords if k in title_lower)
    if bull_score > bear_score:
        return "BULLISH_IDR"
    elif bear_score > bull_score:
        return "BEARISH_IDR"
    return "NEUTRAL"


# ── H: Twitter Sentiment Proxy ────────────────────────────────────────────────
def build_twitter_proxy(news: list) -> list:
    """Bangun sentimen Twitter berdasarkan tone berita (proxy)."""
    log("H: Building Twitter sentiment proxy...")
    bull = sum(1 for n in news if n["classification"] == "BULLISH_IDR")
    bear = sum(1 for n in news if n["classification"] == "BEARISH_IDR")
    dominant = "BEARISH_IDR" if bear >= bull else "BULLISH_IDR"

    themes = [
        {
            "theme_number": 1,
            "hashtag": "#RupiahMelemah" if dominant == "BEARISH_IDR" else "#RupiahMenguat",
            "engagement": "High",
            "summary": (
                "Sentimen negatif dominan — publik khawatir IDR melemah lebih lanjut."
                if dominant == "BEARISH_IDR"
                else "Sentimen positif — publik apresiasi penguatan IDR."
            ),
            "classification": dominant,
            "is_proxy": True
        },
        {
            "theme_number": 2,
            "hashtag": "#BIRate",
            "engagement": "Moderate",
            "summary": "Diskusi soal kebijakan suku bunga BI dan dampaknya ke nilai tukar.",
            "classification": "MIXED",
            "is_proxy": True
        },
        {
            "theme_number": 3,
            "hashtag": "#kursrupiah",
            "engagement": "High",
            "summary": "Update kurs harian — banyak pelaku pasar dan retail pantau level support/resistance.",
            "classification": "NEUTRAL",
            "is_proxy": True
        },
        {
            "theme_number": 4,
            "hashtag": "#DollarRupiah",
            "engagement": "Moderate",
            "summary": "Pergerakan DXY dan dampaknya ke IDR menjadi perhatian utama trader.",
            "classification": "MIXED",
            "is_proxy": True
        }
    ]
    return themes


# ── I: Volatility Proxy (ATR 14D) ─────────────────────────────────────────────
def compute_atr(prices: list) -> dict:
    log("I: Computing ATR 14D as volatility proxy...")
    if len(prices) < 14:
        return {"atr": None, "atr_pct": None, "label": "PROXY"}
    # True range sederhananya = |high-low| per hari
    # Karena kita hanya punya close, pakai std dev sebagai proxy
    window = prices[-14:]
    std_dev = statistics.stdev(window)
    mean_price = statistics.mean(window)
    atr_pct = round(std_dev / mean_price * 100, 3)
    log(f"  ✅ ATR proxy: ±{std_dev:.1f} IDR ({atr_pct}%)")
    return {
        "atr": round(std_dev, 2),
        "atr_pct": atr_pct,
        "interpretation": "High" if atr_pct > 0.5 else "Medium" if atr_pct > 0.2 else "Low",
        "label": "PROXY"
    }


# ── Compute Moving Averages ───────────────────────────────────────────────────
def compute_ma(prices: list, window: int) -> list:
    result = []
    for i in range(len(prices)):
        if i < window - 1:
            result.append(None)
        else:
            result.append(round(sum(prices[i - window + 1:i + 1]) / window, 2))
    return result


# ── Compute sentiment distribution ───────────────────────────────────────────
def compute_sentiment_dist(news: list) -> dict:
    total = len(news) if news else 1
    bull = sum(1 for n in news if n["classification"] == "BULLISH_IDR")
    bear = sum(1 for n in news if n["classification"] == "BEARISH_IDR")
    neu = total - bull - bear
    return {
        "bullish_pct": round(bull / total * 100),
        "bearish_pct": round(bear / total * 100),
        "neutral_pct": round(neu / total * 100)
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log(f"🚀 Memulai fetch data untuk {TODAY}")

    rate_data = fetch_frankfurter()
    bca = fetch_bca_rate()
    jisdor = fetch_jisdor()
    dxy = fetch_dxy()
    bi_rate = fetch_bi_rate()
    news = fetch_news()
    twitter = build_twitter_proxy(news)
    vol = compute_atr(rate_data.get("prices", []))

    prices = rate_data.get("prices", [])
    dates = rate_data.get("dates", [])
    ma5 = compute_ma(prices, 5)
    ma20 = compute_ma(prices, 20)

    # 52-week range dari data yang ada (proxy dengan 30D)
    min_price = min(prices) if prices else None
    max_price = max(prices) if prices else None
    avg_30d = round(sum(prices) / len(prices), 2) if prices else None
    last_price = prices[-1] if prices else None

    # Spot: override BCA mid jika lebih fresh
    spot = last_price
    if bca.get("mid") and bca["label"] == "LIVE":
        spot = bca["mid"]

    sentiment_dist = compute_sentiment_dist(news)

    output = {
        "meta": {
            "date": TODAY.isoformat(),
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "generated_at_wib": (datetime.datetime.utcnow() + datetime.timedelta(hours=7)).strftime("%H:%M WIB")
        },
        "spot": {
            "value": spot,
            "change_pct": rate_data.get("change_pct"),
            "label": rate_data.get("label", "PROXY"),
            "source": rate_data.get("source")
        },
        "bca": bca,
        "jisdor": jisdor,
        "dxy": dxy,
        "bi_rate": bi_rate,
        "historical": {
            "dates": dates,
            "prices": prices,
            "ma5": ma5,
            "ma20": ma20,
            "range_30d_low": min_price,
            "range_30d_high": max_price,
            "avg_30d": avg_30d,
            "label": rate_data.get("label", "PROXY")
        },
        "news": news,
        "twitter": twitter,
        "volatility": vol,
        "sentiment_dist": sentiment_dist
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    log(f"✅ Data tersimpan ke {OUTPUT_PATH}")
    log(f"   Spot: {spot} | BCA: {bca.get('buy')}/{bca.get('sell')} | JISDOR: {jisdor.get('rate')}")
    log(f"   DXY: {dxy.get('value')} | BI Rate: {bi_rate.get('rate')}% | Berita: {len(news)}")


if __name__ == "__main__":
    main()
