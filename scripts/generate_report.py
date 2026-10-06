"""
generate_report.py
Panggil Google Gemini API dengan data real yang sudah di-fetch,
lalu ekstrak HTML output dan simpan ke docs/.
"""
import os
import json
import re
import datetime
import time
import requests

# ── Config ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODEL = "gemini-3-flash-preview"
DATE_OVERRIDE = os.environ.get("DATE_OVERRIDE", "").strip()
TODAY = (
    datetime.date.fromisoformat(DATE_OVERRIDE)
    if DATE_OVERRIDE
    else (datetime.datetime.utcnow() + datetime.timedelta(hours=7)).date()
)
DATA_PATH = "data/market_data.json"
DOCS_DIR = "docs"

os.makedirs(DOCS_DIR, exist_ok=True)


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")


def load_data() -> dict:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt(data: dict) -> str:
    """Bangun prompt lengkap dengan data real yang sudah di-inject."""

    d = data
    spot = d["spot"]
    bca = d["bca"]
    jisdor = d["jisdor"]
    dxy = d["dxy"]
    bi_rate = d["bi_rate"]
    hist = d["historical"]
    news = d["news"]
    vol = d["volatility"]
    sent = d["sentiment_dist"]
    meta = d["meta"]

    # Format news untuk prompt
    news_text = "\n".join([
        f"  {i+1}. [{n['classification']}] {n['title']} — {n.get('source','')} {n.get('datetime','')}"
        for i, n in enumerate(news[:5])
    ])
    if not news_text:
        news_text = "  (TIDAK ADA BERITA — semua sumber gagal)"

    prices_json = json.dumps(hist["prices"][-30:])
    dates_json = json.dumps(hist["dates"][-30:])
    ma5_json = json.dumps(hist["ma5"][-30:])
    ma20_json = json.dumps(hist["ma20"][-30:])

    prompt = f"""Kamu adalah analis FX profesional. Buat SATU file HTML lengkap untuk "Pre-Market Intelligence Radar USD/IDR".

═══════════════════════════════
DATA REAL (sudah di-fetch otomatis)
═══════════════════════════════

TANGGAL: {TODAY.strftime('%A, %d %B %Y')} · Generated: {meta['generated_at_wib']}

A. SPOT USD/IDR:
   Mid-market: {spot['value']} IDR
   Perubahan: {spot['change_pct']:+}%
   Label: {spot['label']} · Sumber: {spot.get('source','')}

B. BCA E-RATE:
   Beli: {bca.get('buy', 'N/A')} | Jual: {bca.get('sell', 'N/A')}
   Update: {bca.get('timestamp', 'N/A')} · Label: {bca.get('label','PROXY')}

C. BI JISDOR:
   Rate: {jisdor.get('rate', 'N/A')} | Tanggal: {jisdor.get('date', 'N/A')}
   Label: {jisdor.get('label','PROXY')}

D. HISTORICAL 30D (untuk chart):
   Tanggal: {dates_json}
   Harga close: {prices_json}
   5D MA: {ma5_json}
   20D MA: {ma20_json}
   Range 30D: {hist['range_30d_low']} – {hist['range_30d_high']}
   Avg 30D: {hist['avg_30d']}
   Label: {hist.get('label','PROXY')}

E. DXY:
   Nilai: {dxy.get('value', 'N/A')} | Perubahan: {dxy.get('change_pct', 'N/A')}%
   Label: {dxy.get('label','PROXY')}

F. BI RATE:
   Rate: {bi_rate.get('rate', 'N/A')}% | Keputusan: {bi_rate.get('decision', 'N/A')}
   Label: {bi_rate.get('label','PROXY')}

G. BERITA TERKINI (24H):
{news_text}

I. VOLATILITY PROXY (ATR 14D):
   ATR: ±{vol.get('atr', 'N/A')} IDR ({vol.get('atr_pct', 'N/A')}%) → {vol.get('interpretation', 'N/A')}
   Label: PROXY

DISTRIBUSI SENTIMEN BERITA:
   Bullish IDR: {sent['bullish_pct']}% | Bearish IDR: {sent['bearish_pct']}% | Neutral: {sent['neutral_pct']}%

═══════════════════════════════
INSTRUKSI OUTPUT
═══════════════════════════════

Buat file HTML LENGKAP dengan:
1. Dark theme: bg #080c10, surface #0d1318, border #1a2332
2. Font: DM Mono + Syne dari Google Fonts
3. Scanlines overlay effect (CSS pseudo-element)
4. Semua chart embedded (Chart.js dari CDN https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js)

LAYOUT SECTIONS (wajib urut):

S1 — HEADER: judul "Pre-Market Intelligence Radar · USD/IDR · {TODAY.strftime('%d %b %Y').upper()}", radar dot pulse animasi, timestamp

S2 — RATE HERO (4 kolom):
  - Spot {spot['value']} IDR ({spot['change_pct']:+}%) [CYAN accent, label: {spot['label']}]
  - BCA E-Rate {bca.get('buy','N/A')} / {bca.get('sell','N/A')} [ORANGE accent, label: {bca.get('label','PROXY')}]
  - Range 30D: {hist['range_30d_low']} – {hist['range_30d_high']} · Avg: {hist['avg_30d']} [GREEN accent]
  - JISDOR {jisdor.get('rate','N/A')} · BI Rate {bi_rate.get('rate','N/A')}% [RED accent, label: {jisdor.get('label','PROXY')}]
  - Setiap sel dengan label data: ● LIVE atau ⚡ PROXY atau ⚠ STALE sesuai data di atas

S3 — 30-DAY PRICE CHART (full width):
  - Line chart pakai data ACTUAL dari section D di atas
  - 3 dataset: USD/IDR (cyan), 5D MA (orange dashed), 20D MA (red dashed)
  - Badge: UPTREND jika harga > 20D MA, DOWNTREND jika di bawah
  - Sumbu Y range: auto dari data ±0.5%
  - Sumbu X: label tanggal dari array dates

S4 — NEWS FEED + ANALYSIS TABLE (2 kolom):
  Kiri: 5 berita dari section G, setiap berita pakai dot hijau/merah/kuning + badge klasifikasi
  Kanan: tabel analisis 5 faktor + quick take paragraph 2 baris

S5 — VOLATILITY BAR + RISK HEATMAP (2 kolom):
  Kiri: Bar chart 6 faktor signal intensity (estimasi dari data yang ada)
  Kanan: 8 progress bar risk scoring

S6 — SENTIMENT DONUT + MACRO (2 kolom):
  Kiri: Donut chart pakai data ACTUAL: Bearish {sent['bearish_pct']}% / Bullish {sent['bullish_pct']}% / Neutral {sent['neutral_pct']}%
  Kanan: 6 kotak macro (BI Rate, DXY, GDP, Next release, Tariff, IDR high)

S7 — TELEGRAM PREVIEW BOX:
  Tulis pesan Telegram 6 baris berdasarkan analisis data hari ini

S8 — FOOTER: sumber data, timestamp, schedule info

ATURAN PENTING:
- SEMUA angka di chart harus berasal dari data real di atas, BUKAN dikarang
- JANGAN mengarang judul berita, sumber, atau tanggal. Tampilkan HANYA berita dari section G, persis apa adanya.
  Jika section G kosong, tampilkan pesan "Tidak ada berita tersedia hari ini" (dan donut sentimen diganti teks yang sama)
- Label ● LIVE / ⚡ PROXY / ⚠ STALE wajib muncul di setiap data point
- Output HANYA berisi kode HTML (mulai dari <!DOCTYPE html> hingga </html>)
- Tidak ada teks penjelasan sebelum atau sesudah kode HTML
- File harus self-contained dan bisa dibuka offline (kecuali Google Fonts + Chart.js CDN)
- Jangan gunakan localStorage atau sessionStorage

ATURAN AKSESIBILITAS (wajib):
- Struktur: <header>, <main>, <footer>; satu <h1> untuk judul, <h2> untuk tiap section S2–S8
- Warna via CSS custom properties di :root (--bg, --surface, --border, --text, --muted, accent), bukan hex berulang
- Ukuran font minimal 12px (0.75rem) untuk SEMUA teks termasuk badge/label; teks isi minimal 14px
- Kontras teks minimal 4.5:1 terhadap background (warna muted jangan lebih gelap dari #8a9bb0 di bg gelap)
- Setiap <canvas> chart wajib role="img" dan aria-label berisi ringkasan angka (mis. "USD/IDR 30 hari, naik dari X ke Y")
- Animasi (radar pulse, dll.) dimatikan di @media (prefers-reduced-motion: reduce)
- Responsif: grid jadi 1 kolom di @media (max-width: 640px), tanpa scroll horizontal di lebar 375px
"""
    return prompt


def call_glm(prompt: str) -> str:
    """Panggil Google Gemini API."""
    log(f"🤖 Memanggil {MODEL} ({len(prompt)} chars prompt)...")

    url = GEMINI_ENDPOINT.format(model=MODEL)
    payload = {
        "system_instruction": {
            "parts": [{"text": "Kamu adalah ahli FX dan front-end developer. Output HANYA kode HTML valid, lengkap, dan self-contained. Tidak ada penjelasan, tidak ada markdown, tidak ada komentar di luar HTML."}]
        },
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 16000,
            "temperature": 0.3
        }
    }

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY},
                json=payload,
                timeout=300
            )
            if response.status_code == 429:
                wait = 30 * attempt
                log(f"⚠️ Rate limit (429) — attempt {attempt}/{max_retries}, tunggu {wait}s...")
                time.sleep(wait)
                continue
            if response.status_code == 503:
                wait = 20 * attempt
                log(f"⚠️ Service unavailable — attempt {attempt}/{max_retries}, tunggu {wait}s...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            result = response.json()
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            log(f"✅ Response diterima ({len(text)} chars)")
            return text
        except requests.exceptions.Timeout:
            log(f"⚠️ Timeout — attempt {attempt}/{max_retries}, retry...")
            time.sleep(20)
            continue

    raise Exception(f"❌ Gagal setelah {max_retries} retry — Gemini tidak merespons")

def extract_html(raw: str) -> str:
    """Ekstrak blok HTML dari response Gemini."""
    # Coba ambil dari ```html ... ```
    match = re.search(r"```html\s*(<!DOCTYPE.*?</html>)\s*```", raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Langsung cari <!DOCTYPE ... </html>
    match = re.search(r"(<!DOCTYPE html.*?</html>)", raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Jika tidak ada, kembalikan seluruh response
    log("⚠️ Tidak menemukan HTML yang bersih — menyimpan raw response")
    return raw


def save_outputs(html: str, date_str: str):
    filename = f"PreMarket_Radar_USDIDR_{date_str}.html"

    # Simpan ke docs/ untuk GitHub Pages
    docs_path = os.path.join(DOCS_DIR, filename)
    with open(docs_path, "w", encoding="utf-8") as f:
        f.write(html)

    log(f"🌐 GitHub Pages: {docs_path}")

    # Simpan path untuk step berikutnya
    with open("data/latest_report.txt", "w") as f:
        f.write(filename)

    return filename


def main():
    if not GEMINI_API_KEY:
        log("❌ GEMINI_API_KEY tidak ada di environment!")
        exit(1)

    log(f"🚀 Generate report untuk {TODAY}")

    data = load_data()
    prompt = build_prompt(data)
    raw_response = call_glm(prompt)
    html = extract_html(raw_response)
    filename = save_outputs(html, TODAY.isoformat())

    log(f"✅ Report selesai: {filename}")

    # Simpan telegram message untuk step berikutnya
    data_spot = data["spot"]
    data_news = data["news"]
    bear_count = sum(1 for n in data_news if n["classification"] == "BEARISH_IDR")
    bull_count = sum(1 for n in data_news if n["classification"] == "BULLISH_IDR")
    stance = "BEARISH IDR" if bear_count > bull_count else "BULLISH IDR" if bull_count > bear_count else "NEUTRAL"
    best_bull = next((n["title"][:60] for n in data_news if n["classification"] == "BULLISH_IDR"), "N/A")
    worst_bear = next((n["title"][:60] for n in data_news if n["classification"] == "BEARISH_IDR"), "N/A")

    telegram_msg = (
        f"📡 PRE-MARKET RADAR · USD/IDR · {TODAY.strftime('%d %b %Y').upper()}\n"
        f"📍 Portfolio Stance: {stance} · Spot {data_spot['value']} ({data_spot['change_pct']:+}%)\n"
        f"🟢 Bullish Catalyst: {best_bull}\n"
        f"🔴 Highest Risk: {worst_bear}\n"
        f"🌐 Key Macro Driver: BI Rate {data['bi_rate']['rate']}% · DXY {data['dxy'].get('value','N/A')}\n"
        f"📎 [{filename}]"
    )
    with open("data/telegram_msg.txt", "w", encoding="utf-8") as f:
        f.write(telegram_msg)

    log("📝 Telegram message tersimpan ke data/telegram_msg.txt")


if __name__ == "__main__":
    main()
