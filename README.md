# 📡 USD/IDR Pre-Market Intelligence Radar

Dashboard harian USD/IDR otomatis — dijalankan setiap hari kerja **08:00 WIB** via **GitHub Actions**, 
digenerate oleh **Gemini (Google AI)**, dan dipublikasikan ke **GitHub Pages**.

---

## 🗂️ Struktur Project

```
usdidr-radar/
├── .github/
│   └── workflows/
│       └── daily_radar.yml       ← Scheduler otomatis
├── scripts/
│   ├── check_market.py           ← Cek hari kerja / libur
│   ├── fetch_data.py             ← Ambil data real (Frankfurter, BCA, BI, NewsAPI)
│   ├── generate_report.py        ← Panggil Gemini → generate HTML
│   └── deploy_pages.py           ← Update index GitHub Pages
├── docs/                         ← HTML report + GitHub Pages (publik)
├── data/                         ← Data intermediary (auto-generated)
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup (5 langkah)

### Langkah 1 — Fork / Clone repo ini

```bash
git clone https://github.com/USERNAME/usdidr-radar.git
cd usdidr-radar
```

### Langkah 2 — Dapatkan API Keys

| Service | Cara Dapat | Gratis? |
|---------|-----------|---------|
| **Gemini** | Daftar di [aistudio.google.com](https://aistudio.google.com/apikey) → Get API key | Ada free tier |
| **Tavily** | Daftar di [tavily.com](https://tavily.com) | ✅ Ada free tier |
| **NewsAPI** | Daftar di [newsapi.org](https://newsapi.org) | ✅ 100 req/day gratis |

> **NewsAPI & Tavily opsional** — tanpa NewsAPI berita diambil via scraping; tanpa Tavily kurs BCA pakai sumber cadangan (label PROXY).

### Langkah 3 — Set GitHub Secrets

Di repo GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|-------------|-------|
| `GEMINI_API_KEY` | API key dari Google AI Studio (wajib) |
| `NEWS_API_KEY` | API key NewsAPI (opsional) |
| `TAVILY_API_KEY` | API key Tavily (opsional) |

### Langkah 4 — Aktifkan GitHub Pages

1. Di repo: **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / folder: `/docs`
4. Klik **Save**

Setelah beberapa menit, dashboard bisa diakses di:
`https://USERNAME.github.io/usdidr-radar`

### Langkah 5 — Test Manual

Di tab **Actions** → workflow `📡 USD/IDR Pre-Market Radar` → **Run workflow**

---

## 📅 Jadwal Otomatis

```
Cron: 0 1 * * 1-5
     = Setiap Senin–Jumat pukul 01:00 UTC = 08:00 WIB
```

Otomatis **skip** pada:
- Weekend (Sabtu–Minggu)
- Libur nasional Indonesia & US Federal holidays (di-hardcode di `check_market.py`)

---

## 📊 Sumber Data Real

| Data | Sumber | Free? | Label |
|------|--------|-------|-------|
| Spot USD/IDR | [Frankfurter.app](https://api.frankfurter.app) | ✅ | LIVE |
| Historical 30D | [Frankfurter.app](https://api.frankfurter.app) | ✅ | LIVE |
| BCA E-Rate | bca.co.id via Tavily → r.jina.ai → markdown.new (fallback: currency-api / open.er-api) | ✅ | LIVE/PROXY |
| BI JISDOR | Webservice bi.go.id | ✅ | LIVE/PROXY |
| DXY Index | Yahoo Finance (yfinance) | ✅ | LIVE |
| BI Rate | NewsAPI / fallback | ✅ | LIVE/STALE |
| Berita 24H | NewsAPI.org (fallback: scraping CNBC/Bisnis/Kontan, via r.jina.ai / markdown.new jika diblokir) | ✅ free tier | LIVE/PROXY |
| Implied Volatility | ATR 14D proxy | ✅ | ⚡ PROXY |

> Label **⚡ PROXY** = estimasi, bukan data langsung  
> Label **⚠ STALE** = data lama (>24 jam)  
> Label **● LIVE** = data real-time / hari ini

---

## 🤖 Gemini API

Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`  
Model: `gemini-3-flash-preview`  
Auth: header `x-goog-api-key` (key tidak pernah masuk URL/log)

---

## 🛑 Stop Condition

Nonaktifkan workflow di **Actions → disable workflow**.

---

## 🔧 Kustomisasi

**Ubah jadwal:**
```yaml
# .github/workflows/daily_radar.yml
- cron: '0 1 * * 1-5'   # ← ubah sesuai kebutuhan (UTC)
```

**Tambah libur nasional:**
```python
# scripts/check_market.py → HOLIDAYS_2026
"2026-MM-DD",  # nama hari
```

**Ganti model:**
```python
# scripts/generate_report.py
MODEL = "gemini-3-flash-preview"  # ← bisa diganti model Gemini lain
```

---

*Powered by Gemini · GitHub Actions · Frankfurter API · NewsAPI*
