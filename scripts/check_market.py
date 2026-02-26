"""
check_market.py
Cek apakah hari ini hari kerja (bukan weekend / libur nasional).
Output ke GitHub Actions environment variable.
"""
import os
import sys
import datetime

# ── Daftar libur nasional Indonesia + US Federal 2026 ──────────────────────
# Format: "YYYY-MM-DD"
HOLIDAYS_2026 = {
    # Indonesia
    "2026-01-01",  # Tahun Baru
    "2026-01-27",  # Isra Mikraj
    "2026-01-29",  # Tahun Baru Imlek
    "2026-03-20",  # Hari Raya Nyepi
    "2026-03-26",  # Wafat Isa Almasih
    "2026-04-02",  # Idul Fitri (cuti bersama)
    "2026-04-03",  # Idul Fitri
    "2026-05-01",  # Hari Buruh
    "2026-05-14",  # Kenaikan Isa Almasih
    "2026-05-24",  # Hari Raya Waisak
    "2026-06-01",  # Hari Lahir Pancasila
    "2026-06-10",  # Idul Adha (estimasi)
    "2026-07-01",  # Tahun Baru Islam (estimasi)
    "2026-08-17",  # HUT RI
    "2026-09-10",  # Maulid Nabi (estimasi)
    "2026-12-25",  # Natal
    # US Federal (relevan untuk data USD)
    "2026-01-19",  # Martin Luther King Jr. Day
    "2026-02-16",  # Presidents' Day
    "2026-05-25",  # Memorial Day
    "2026-07-03",  # Independence Day (observed)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving
    "2026-12-25",  # Christmas
}


def set_output(key: str, value: str):
    """Tulis ke GitHub Actions output."""
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"{key}={value}\n")
    else:
        print(f"OUTPUT: {key}={value}")


def main():
    date_override = os.environ.get("DATE_OVERRIDE", "").strip()
    if date_override:
        today = datetime.date.fromisoformat(date_override)
    else:
        # Waktu Jakarta (UTC+7)
        today = (datetime.datetime.utcnow() + datetime.timedelta(hours=7)).date()

    today_str = today.isoformat()
    weekday = today.weekday()  # 0=Senin, 6=Minggu

    print(f"📅 Tanggal: {today_str} ({today.strftime('%A')})")

    if weekday >= 5:
        day_name = "Sabtu" if weekday == 5 else "Minggu"
        reason = f"Weekend ({day_name} {today_str})"
        next_monday = today + datetime.timedelta(days=(7 - weekday))
        skip_msg = f"⏭ Pre-Market Radar skip — {reason}. Next run: Senin {next_monday}."
        print(f"⏭ {reason} — skip")
        set_output("market_open", "false")
        set_output("skip_reason", skip_msg)
        return

    if today_str in HOLIDAYS_2026:
        reason = f"Libur nasional ({today_str})"
        print(f"⏭ {reason} — skip")
        set_output("market_open", "false")
        set_output("skip_reason", f"⏭ Pre-Market Radar skip — {reason}.")
        return

    print("✅ Hari kerja — lanjutkan generate radar")
    set_output("market_open", "true")
    set_output("skip_reason", "")


if __name__ == "__main__":
    main()
