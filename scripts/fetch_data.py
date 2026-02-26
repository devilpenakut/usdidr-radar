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
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

# ── Config ──────────────────────────────────────────────────────────────────
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
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


# ── B: BCA E-Rate (Tavily extract → fallback proxy) ──────────────────────────
def fetch_bca_rate():
    log("B: Fetching BCA E-Rate...")

    # Opsi 1: Tavily — extract langsung dari bca.co.id (handle JS rendering)
    if TAVILY_API_KEY and TAVILY_AVAILABLE:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=TAVILY_API_KEY)
            resp = client.extract(urls=["https://www.bca.co.id/id/informasi/kurs"])
            raw = ""
            for r in resp.get("results", []):
                raw += r.get("raw_content", "")

            # Parse angka IDR dari konten — cari pola USD + angka 5 digit
            lines = raw.splitlines()
            for line in lines:
                if "USD" in line.upper() or "Dollar" in line:
                    nums = re.findall(r"1[0-9][.,]\d{3}(?:[.,]\d{1,2})?", line)
                    nums_clean = []
                    for n in nums:
                        try:
                            nums_clean.append(float(n.replace(".", "").replace(",", ".")))
                        except:
                            pass
                    nums_valid = [n for n in nums_clean if 10000 < n < 25000]
                    if len(nums_valid) >= 2:
                        buy, sell = sorted(nums_valid[:2])
                        mid = round((buy + sell) / 2, 0)
                        log(f"  ✅ BCA via Tavily: Buy={buy} Sell={sell}")
                        return {
                            "buy": buy, "sell": sell, "mid": mid,
                            "source": "bca.co.id via Tavily",
                            "timestamp": datetime.datetime.now(
                                datetime.timezone(datetime.timedelta(hours=7))
                            ).strftime("%H:%M WIB"),
                            "label": "LIVE"
                        }
            log("  ⚠️ Tavily extract BCA: angka tidak ditemukan di konten")
        except Exception as e:
            log(f"  ⚠️ Tavily BCA error: {e}")

    # Opsi 2: fawazahmed0 currency API (no key, gratis)
    try:
        r = requests.get(
            "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
            timeout=10
        )
        r.raise_for_status()
        mid = r.json()["usd"]["idr"]
        spread = round(mid * 0.003, 0)
        log(f"  ✅ BCA proxy fawazahmed0: mid={mid}")
        return {
            "buy": round(mid - spread, 0), "sell": round(mid + spread, 0),
            "mid": round(mid, 2),
            "source": "fawazahmed0 (BCA spread est. ±0.3%)",
            "timestamp": datetime.datetime.now(
                datetime.timezone(datetime.timedelta(hours=7))
            ).strftime("%H:%M WIB"),
            "label": "PROXY"
        }
    except Exception as e:
        log(f"  ⚠️ fawazahmed0 error: {e}")

    # Opsi 3: open.er-api
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        r.raise_for_status()
        mid = r.json()["rates"]["IDR"]
        spread = round(mid * 0.003, 0)
        log(f"  ✅ BCA proxy open.er-api: mid={mid}")
        return {
            "buy": round(mid - spread, 0), "sell": round(mid + spread, 0),
            "mid": round(mid, 2),
            "source": "open.er-api (BCA spread est. ±0.3%)",
            "timestamp": datetime.datetime.now(
                datetime.timezone(datetime.timedelta(hours=7))
            ).strftime("%H:%M WIB"),
            "label": "PROXY"
        }
    except Exception as e:
        log(f"  ⚠️ open.er-api error: {e}")
        return {"buy": None, "sell": None, "mid": None, "label": "PROXY", "error": str(e)}


# ── C: BI JISDOR (via BI webservice JSON) ────────────────────────────────────
def fetch_jisdor():
    log("C: Fetching BI JISDOR...")

    # Opsi 1: BI webservice API
    try:
        today_str = TODAY.strftime("%Y%m%d")
        url = f"https://www.bi.go.id/biwebservice/wskursbi.asmx/getSubKursLokal2?startdate={today_str}&enddate={today_str}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("Table")
        for item in items:
            kode = item.find("kode_kurs")
            rate_el = item.find("kurs_tengah") or item.find("kurs_jual")
            if kode and "USD" in kode.get_text() and rate_el:
                rate = float(rate_el.get_text().replace(",", "").replace(".", ""))
                if rate > 10000:
                    log(f"  ✅ JISDOR webservice: {rate}")
                    return {
                        "rate": int(rate),
                        "date": TODAY.strftime("%d/%m/%Y"),
                        "source": "bi.go.id/biwebservice",
                        "label": "LIVE"
                    }
    except Exception as e:
        log(f"  ⚠️ BI webservice error: {e}")

    # Opsi 2: gunakan spot dari Frankfurter + label STALE
    # Opsi 2: Tavily search untuk JISDOR
    if TAVILY_API_KEY and TAVILY_AVAILABLE:
        try:
            client = TavilyClient(api_key=TAVILY_API_KEY)
            resp = client.search(
                query=f"JISDOR Bank Indonesia kurs USD IDR {TODAY.strftime('%d %B %Y')}",
                search_depth="basic",
                max_results=3
            )
            for r in resp.get("results", []):
                text = r.get("content", "") + r.get("title", "")
                match = re.search(r"1[5-9][.,]\d{3}", text)
                if match:
                    rate_str = match.group(0).replace(".", "").replace(",", "")
                    rate = int(rate_str)
                    if 15000 < rate < 20000:
                        log(f"  ✅ JISDOR via Tavily: {rate}")
                        return {
                            "rate": rate,
                            "date": TODAY.strftime("%d/%m/%Y"),
                            "source": "Tavily/BI",
                            "label": "PROXY"
                        }
        except Exception as e:
            log(f"  ⚠️ Tavily JISDOR error: {e}")

    log("  ℹ️ JISDOR: menggunakan spot rate sebagai proxy")
    return {"rate": None, "date": None, "label": "PROXY", "note": "BI site JS-rendered"}


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


# ── G: Berita Terkini (Tavily → NewsAPI → Scraping fallback) ─────────────────
def fetch_news():
    log("G: Fetching berita terkini...")

    # Opsi 1: Tavily API (best quality, real-time)
    if TAVILY_API_KEY and TAVILY_AVAILABLE:
        try:
            client = TavilyClient(api_key=TAVILY_API_KEY)
            results = []
            queries = [
                "rupiah dollar hari ini kurs IDR",
                "Bank Indonesia rupiah berita terkini"
            ]
            seen = set()
            for q in queries:
                resp = client.search(
                    query=q,
                    search_depth="basic",
                    topic="news",
                    days=1,
                    max_results=4,
                    include_answer=False
                )
                for r in resp.get("results", []):
                    title = r.get("title", "")
                    if title and title not in seen and len(title) > 20:
                        seen.add(title)
                        results.append({
                            "title": title[:120],
                            "source": r.get("url","").split("/")[2] if r.get("url") else "Tavily",
                            "datetime": r.get("published_date", TODAY.isoformat())[:16],
                            "url": r.get("url", ""),
                            "classification": classify_news(title),
                            "label": "LIVE"
                        })
                if len(results) >= 5:
                    break
            if results:
                log(f"  ✅ {len(results)} berita dari Tavily")
                return results[:5]
        except Exception as e:
            log(f"  ⚠️ Tavily error: {e}")

    # Opsi 2: NewsAPI (free tier: English only, no date filter)
    if NEWS_API_KEY:
        newsapi_queries = [
            ("Indonesian rupiah dollar exchange rate", "en"),
            ("Bank Indonesia interest rate rupiah", "en"),
            ("IDR USD currency Indonesia", "en"),
        ]
        newsapi_results = []
        seen_newsapi = set()
        for q, lang in newsapi_queries:
            try:
                r = requests.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": q,
                        "language": lang,
                        "sortBy": "publishedAt",
                        "pageSize": 5,
                        "apiKey": NEWS_API_KEY
                        # Note: 'from' param requires paid plan — dihapus
                    },
                    timeout=10
                )
                data = r.json()
                if data.get("status") == "error":
                    log(f"  ⚠️ NewsAPI error: {data.get('message','')}")
                    break
                for a in data.get("articles", []):
                    title = a.get("title", "")
                    if not title or title in seen_newsapi or len(title) < 15:
                        continue
                    if "[Removed]" in title:
                        continue
                    seen_newsapi.add(title)
                    newsapi_results.append({
                        "title": title[:120],
                        "source": a.get("source", {}).get("name", "NewsAPI"),
                        "datetime": a.get("publishedAt", "")[:16].replace("T", " "),
                        "url": a.get("url", ""),
                        "classification": classify_news(title),
                        "label": "LIVE"
                    })
                if len(newsapi_results) >= 5:
                    break
            except Exception as e:
                log(f"  ⚠️ NewsAPI query error: {e}")
                continue

        if newsapi_results:
            log(f"  ✅ {len(newsapi_results)} berita dari NewsAPI")
            return newsapi_results[:5]
        else:
            log("  ⚠️ NewsAPI: 0 artikel — mungkin rate limit atau plan gratis")

    # Opsi 3: Scraping fallback
    log("  ℹ️ Fallback ke scraping...")
    return fetch_news_scraping()


def fetch_news_scraping():
    """Fallback: scraping dari beberapa sumber berita IDR."""
    results = []
    seen = set()

    sources = [
        ("https://www.cnbcindonesia.com/search?query=rupiah+kurs+dollar", "CNBCIndonesia"),
        ("https://ekonomi.bisnis.com/search?type=news&q=rupiah", "BisnisIndonesia"),
        ("https://www.kontan.co.id/search/?q=rupiah+kurs", "Kontan"),
    ]

    for url, src_name in sources:
        try:
            r = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            # Cari semua heading/link yang mengandung kata kunci
            candidates = soup.find_all(["h1","h2","h3","a"], limit=30)
            for el in candidates:
                title = el.get_text(strip=True)
                if len(title) < 20:
                    continue
                keywords = ["rupiah","kurs","IDR","BI rate","dollar","devisa","valas"]
                if any(k.lower() in title.lower() for k in keywords):
                    if title not in seen:
                        seen.add(title)
                        results.append({
                            "title": title[:120],
                            "source": src_name,
                            "datetime": TODAY.isoformat(),
                            "classification": classify_news(title),
                            "label": "PROXY"
                        })
            if len(results) >= 5:
                break
        except Exception as e:
            log(f"  ⚠️ Scraping {src_name}: {e}")
            continue

    # Jika masih kosong — gunakan headline statis berdasarkan konteks DXY + spot
    if not results:
        log("  ℹ️ Menggunakan fallback headlines kontekstual")
        results = [
            {"title": "Rupiah stabil di kisaran 16.700-an, pasar tunggu data inflasi AS", "source": "Fallback", "datetime": TODAY.isoformat(), "classification": "NEUTRAL", "label": "PROXY"},
            {"title": "BI pertahankan suku bunga 4,75% demi jaga stabilitas rupiah", "source": "Fallback", "datetime": TODAY.isoformat(), "classification": "NEUTRAL", "label": "PROXY"},
            {"title": "DXY menguat tipis, tekanan eksternal masih bayangi rupiah", "source": "Fallback", "datetime": TODAY.isoformat(), "classification": "BEARISH_IDR", "label": "PROXY"},
        ]
    return results[:5]


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
