# 📡 USD/IDR Pre-Market Intelligence Radar

Dashboard harian USD/IDR otomatis — dijalankan setiap hari kerja **08:00 WIB** via **GitHub Actions**, 
digenerate oleh **GLM-4.7 (Z.AI)**, dipublikasikan ke **GitHub Pages**, dan dikirim ke **Telegram**.

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
│   ├── generate_report.py        ← Panggil GLM-4.7 → generate HTML
│   └── deploy_pages.py           ← Update index GitHub Pages
├── outputs/                      ← HTML report tersimpan di sini
├── docs/                         ← GitHub Pages (publik)
├── data/                         ← Data intermediary (auto-generated)
├── MASTER_PROMPT_USDIDR.json     ← Master prompt reference
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
| **Z.AI GLM-4.7** | Daftar di [platform.z.ai](https://platform.z.ai) → API Keys | Ada free tier |
| **Telegram Bot** | Chat `@BotFather` di Telegram → `/newbot` | ✅ Gratis |
| **NewsAPI** | Daftar di [newsapi.org](https://newsapi.org) | ✅ 100 req/day gratis |

> **NewsAPI opsional** — jika tidak ada, berita diambil via scraping (label PROXY).

### Langkah 3 — Set GitHub Secrets

Di repo GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|-------------|-------|
| `ZAI_API_KEY` | API key dari platform.z.ai |
| `PAGES_URL` | URL GitHub Pages kamu (contoh: `https://username.github.io/usdidr-radar`) |

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
- Libur nasional Indonesia (sudah di-hardcode di `check_market.py`)
- US Federal holidays

Kirim pesan Telegram skip seperti:
```
⏭ Pre-Market Radar skip — Weekend (Sabtu 2026-03-07). Next run: Senin 2026-03-09.
```

---

## 📊 Sumber Data Real

| Data | Sumber | Free? | Label |
|------|--------|-------|-------|
| Spot USD/IDR | [Frankfurter.app](https://api.frankfurter.app) | ✅ | LIVE |
| Historical 30D | [Frankfurter.app](https://api.frankfurter.app) | ✅ | LIVE |
| BCA E-Rate | Scraping bca.co.id | ✅ | LIVE/PROXY |
| BI JISDOR | Scraping bi.go.id | ✅ | LIVE/PROXY |
| DXY Index | Yahoo Finance (yfinance) | ✅ | LIVE |
| BI Rate | NewsAPI / fallback | ✅ | LIVE/STALE |
| Berita 24H | NewsAPI.org | ✅ free tier | LIVE/PROXY |
| Twitter Sentiment | Proxy dari berita | ✅ | ⚡ PROXY |
| Implied Volatility | ATR 14D proxy | ✅ | ⚡ PROXY |

> Label **⚡ PROXY** = estimasi, bukan data langsung  
> Label **⚠ STALE** = data lama (>24 jam)  
> Label **● LIVE** = data real-time / hari ini

---

## 🤖 GLM-4.7 API

Endpoint: `https://api.z.ai/api/paas/v4/chat/completions`  
Model: `glm-4.7`  
Context window: 200K tokens  
Thinking mode: enabled (lebih akurat untuk task kompleks)

---

## 🛑 Stop Condition

Kirim pesan ke bot Telegram atau edit workflow:
```
STOP PRE-MARKET RADAR
```
Atau nonaktifkan workflow di **Actions → disable workflow**.

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
MODEL = "glm-4.7"  # ← bisa diganti glm-5, dll.
```

---

*Powered by Z.AI GLM-4.7 · GitHub Actions · Frankfurter API · NewsAPI*
