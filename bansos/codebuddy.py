"""Tambah provider CodeBuddy lewat OAuth di dashboard 9router.

Alur:
  1. Login 9router di browser (password NINEROUTER_PASSWORD).
  2. Buka /dashboard/providers/codebuddy-intl, klik OAuth → tab baru.
  3. Di tab baru: klik #social-google → Confirm → login Google → region Singapore → Submit.
  4. Polling GET /api/providers sampai jumlah connection codebuddy-intl naik.
     Belum naik → klik OAuth sekali lagi di 9router dan tunggu lagi.
     Tetap tidak naik setelah semua percobaan = failed.

Kredensial Google dibaca dari gmail.txt (jalur = GMAIL_FILE di .env):

    Password: 12345
    email1@gmail.com
    email2@gmail.com

Baris pertama opsional berisi satu password bersama, baris-baris berikutnya
email. Tiap email dicoba berurutan sampai satu akun berhasil nambah.
Kalau gmail.txt tidak ada password bersama, password tiap akun dibaca dari
GOOGLE_PASSWORD di .env (sama untuk semua akun).

ponytail: ambil satu akun per run; tambah antrian multi-akun kalau butuh.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .browser import close, launch
from .config import Settings, load_env, settings
from .human import human_delay
from .ninerouter import NineRouter
from .page import click_first_visible, fill_input, goto

PROVIDER_ID = "codebuddy-intl"
DASHBOARD_URL = "http://100.68.92.106:20128/dashboard/providers/codebuddy-intl"

NINE_PASSWORD = ["input[placeholder='Enter password']", "input[type='password']"]
NINE_LOGIN_BTN = ["button:has-text('Login')"]
NINE_OAUTH_BTN = [
    "body > div.flex.h-screen.w-full.overflow-hidden.bg-bg > main > div.flex-1.overflow-y-auto.custom-scrollbar.p-6.lg\\:p-10 > div > div > div:nth-child(2) > div.mt-4.grid.grid-cols-1.gap-2.sm\\:flex > button.inline-flex.items-center.justify-center.gap-2.font-semibold.transition-all.duration-150.ease-out.cursor-pointer.active\\:scale-\\[0\\.97\\].disabled\\:opacity-50.disabled\\:cursor-not-allowed.disabled\\:active\\:scale-100.bg-surface-2.hover\\:bg-surface-3.text-text-main.border.border-border.disabled\\:opacity-50.h-7.px-3.text-xs.rounded-\\[8px\\].w-full.sm\\:w-auto",
    "button:has-text('OAuth')",
]

CB_GOOGLE_BTN = ["#social-google"]
CB_CONFIRM_BTN = ["body > dialog > div.ui-dialog-footer > button:nth-child(1)"]
CB_REGION_INPUT = ["#root > div > div.flex-1 > div > div > div.max-w-500px.w-100\\%.flex.flex-col.gap-6 > div > div.mb-2 > div > div > div > input"]
CB_REGION_SINGAPORE = ["body > div.t-portal-wrapper.appear-done.enter-done > div > div > div.cursor-pointer.border-b.border-white\\/10.border-solid.bg-\\#1a1a1a.px-3.py-4.text-white\\/80"]
CB_SUBMIT_BTN = ["#root > div > div.flex-1 > div > div > div.max-w-500px.w-100\\%.flex.flex-col.gap-6 > div.cb-btn.box-border.h-38px.flex.cursor-pointer.items-center.justify-center.gap-2.rounded-56px.text-center.text-nowrap.text-sm.font-600.transition-colors.cb-btn--default.px-8.py-2.h-58px.flex.gap-4.rounded-2\\!.bg-\\#28B894\\!.text-lg\\!.text-black\\!"]

# Selector login Google sama dengan 9router-automation (core/selectors.py).
G_EMAIL = ["input[type='email']", "#identifierId", "input[name='identifier']"]
G_EMAIL_NEXT = ["#identifierNext > div > button", "#identifierNext button", "#identifierNext"]
G_PASSWORD = ["input[type='password']", "input[name='Passwd']"]
G_PASSWORD_NEXT = ["#passwordNext > div > button", "#passwordNext button", "#passwordNext"]

POLL_INTERVAL = 10
POLL_ROUNDS = 12          # ~2 menit per percobaan
MAX_ATTEMPTS = 2          # percobaan awal + satu klik OAuth ulang


@dataclass(frozen=True)
class GoogleAccount:
    email: str
    password: str


def load_gmail_accounts(path: str | Path) -> list[GoogleAccount]:
    """Baca gmail.txt. Baris 'Password: ...' opsional, sisanya email."""
    lines = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines()]
    shared = ""
    emails: list[str] = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        match = re.match(r"(?i)^password\s*:\s*(.+)$", line)
        if match:
            shared = match.group(1).strip()
            continue
        if "@" in line:
            emails.append(line.strip())
    fallback = shared or os.getenv("GOOGLE_PASSWORD", "").strip()
    if not fallback:
        raise ValueError(f"password tidak ada: tulis 'Password: ...' di {path} atau isi GOOGLE_PASSWORD")
    return [GoogleAccount(email=email, password=fallback) for email in emails]


async def _wait_new_account(router: NineRouter, baseline: int) -> bool:
    for _ in range(POLL_ROUNDS):
        await asyncio.sleep(POLL_INTERVAL)
        count = await router.count_provider(PROVIDER_ID)
        if count > baseline:
            print(f"✓ Akun CodeBuddy baru terdeteksi ({baseline} → {count})")
            return True
    return False


async def _login_google(popup, email: str, password: str) -> None:
    await fill_input(popup, G_EMAIL, email, label="Google email")
    await click_first_visible(popup, G_EMAIL_NEXT, label="Google next")
    await asyncio.sleep(human_delay(2, 3))
    await fill_input(popup, G_PASSWORD, password, label="Google password")
    await click_first_visible(popup, G_PASSWORD_NEXT, label="Google password next")
    await asyncio.sleep(human_delay(3, 5))


async def _oauth_once(context, page, email: str, password: str) -> None:
    """Klik OAuth di 9router, lalu jalankan alur di tab CodeBuddy yang terbuka."""
    if not await click_first_visible(page, NINE_OAUTH_BTN, label="OAuth"):
        raise RuntimeError("tombol OAuth tidak ketemu")
    await asyncio.sleep(human_delay(2, 3))

    popup = next((p for p in context.pages if "codebuddy" in p.url and p is not page), None)
    if popup is None:
        raise RuntimeError("tab CodeBuddy tidak terbuka")
    await popup.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(human_delay(2, 3))

    await click_first_visible(popup, CB_GOOGLE_BTN, label="Sign up with Google")
    await asyncio.sleep(human_delay(2, 3))
    await click_first_visible(popup, CB_CONFIRM_BTN, label="Confirm")
    await asyncio.sleep(human_delay(2, 3))

    if "google" in popup.url:
        await _login_google(popup, email, password)

    await click_first_visible(popup, CB_REGION_INPUT, label="Registration location")
    await asyncio.sleep(human_delay(1, 2))
    await click_first_visible(popup, CB_REGION_SINGAPORE, label="Current Region Singapore")
    await asyncio.sleep(human_delay(1, 2))
    await click_first_visible(popup, CB_SUBMIT_BTN, label="Submit")


async def add_codebuddy(config: Settings, router: NineRouter, accounts: list[GoogleAccount]) -> bool:
    baseline = await router.count_provider(PROVIDER_ID)
    if baseline < 0:
        return False
    print(f"→ Baseline {PROVIDER_ID}: {baseline} akun")

    manager, browser = await launch(config, session_id="codebuddy")
    try:
        context = await browser.new_context()
        page = await context.new_page()
        await goto(page, f"{config.ninerouter_url}/login")
        await fill_input(page, NINE_PASSWORD, config.ninerouter_password, label="9router password")
        await click_first_visible(page, NINE_LOGIN_BTN, label="Login")
        await asyncio.sleep(human_delay(2, 3))

        await goto(page, DASHBOARD_URL)
        await asyncio.sleep(human_delay(2, 3))

        for account in accounts:
            print(f"→ Akun Google: {account.email}")
            for attempt in range(1, MAX_ATTEMPTS + 1):
                print(f"→ Percobaan OAuth {attempt}/{MAX_ATTEMPTS}")
                try:
                    await _oauth_once(context, page, account.email, account.password)
                except RuntimeError as exc:
                    print(f"✗ {exc}")
                if await _wait_new_account(router, baseline):
                    return True
                print("⚠️  Belum ada akun baru.")

        print(f"✗ Failed: tidak ada akun {PROVIDER_ID} baru setelah semua percobaan.")
        return False
    finally:
        await close(manager)


def main() -> None:
    load_env()
    config = settings()
    gmail_file = os.getenv("GMAIL_FILE", "gmail.txt").strip()
    try:
        accounts = load_gmail_accounts(gmail_file)
    except (OSError, ValueError) as exc:
        print(f"✗ {exc}")
        return
    if not accounts:
        print(f"✗ Tidak ada email di {gmail_file}")
        return
    print(f"→ {len(accounts)} akun Google dari {gmail_file}")

    router = NineRouter(config)
    try:
        if not asyncio.run(router.login()):
            return
        ok = asyncio.run(add_codebuddy(config, router))
    finally:
        asyncio.run(router.aclose())
    print("✓ Berhasil" if ok else "✗ Gagal")


if __name__ == "__main__":
    asyncio.run(main())
