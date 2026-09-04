"""Orkestrasi satu akun end-to-end, plus retry saat kena blokir anti-bot."""

from __future__ import annotations

import asyncio
import time

from . import browser, github, sites, storage
from .config import GithubAccount, RunOptions, Settings, Site
from .errors import BotBlocked, EmailRejected, StepSkipped
from .human import human_delay
from .mail import MailProvider
from .ninerouter import NineRouter


async def _push_keys(
    router: NineRouter | None, collected: list[tuple[Site, str]], username: str
) -> None:
    if router is None:
        return
    for site, key in collected:
        print(f"→ Push key {site.name} ke 9router...")
        await router.push_key(
            site.provider_node_id, f"{username}-{site.name.lower()}", key, site.model
        )


def _save(email: str, password: str, username: str, collected: list[tuple[Site, str]]) -> None:
    storage.append_account(
        email, password, username, [(site.name, key) for site, key in collected]
    )
    print("✓ Tersimpan ke akun.txt")


async def process_account(
    browser_instance,
    mail: MailProvider,
    router: NineRouter | None,
    config: Settings,
    options: RunOptions,
) -> bool:
    """GitHub signup → OTP → login → tiap situs → push 9router → simpan.

    Email digenerate di dalam `github.register`, setelah captcha lolos, supaya
    alamat tidak terbuang kalau signup ditolak lebih awal.
    """
    password = config.github_password
    page = await browser_instance.new_page()

    # Timestamp sebelum submit → filter email lama saat polling OTP.
    started = time.time()

    try:
        registered = await github.register(page, mail, password)
        if not registered:
            return False
        email, username = registered

        print(f"\n{'=' * 60}")
        print(f"Email    : {email}")
        print(f"Username : {username}")
        print(f"{'=' * 60}")

        if not await github.submit_otp(page, mail, email, started):
            return False
        if not await github.login(page, username, password):
            return False

        collected: list[tuple[Site, str]] = []
        account = GithubAccount(username=username, password=password)
        for site in config.sites:
            try:
                key = await sites.collect_key(page, site, account, options.seen_keys)
            except StepSkipped as exc:
                print(f"⚠️  {site.name} dilewati pada langkah: {exc}")
                key = None
            if key:
                collected.append((site, key))
            else:
                print(f"⚠️  {site.name} tidak menghasilkan key, lanjut situs berikutnya")

        if not collected:
            print("✗ Tidak ada API key yang berhasil di-collect")
            return False

        await _push_keys(router, collected, username)
        if options.save_file:
            _save(email, password, username, collected)
        for site, key in collected:
            print(f"   {site.name}: {key}")
        return True
    except StepSkipped as exc:
        # Langkah GitHub (captcha, form, OTP, login) yang dilewati berarti akun ini
        # tidak bisa dilanjutkan; akun berikutnya tetap dikerjakan.
        print(f"⚠️  Akun dilewati pada langkah: {exc}")
        return False
    finally:
        await page.close()


async def run_account(
    mail: MailProvider,
    router: NineRouter | None,
    config: Settings,
    options: RunOptions,
    attempts: int = 3,
) -> bool:
    """Satu akun, browser sendiri, satu sessid (satu IP) per percobaan.

    Kena blokir anti-bot → relaunch dengan sessid + fingerprint baru, bukan retry
    di browser yang sama.
    """
    for attempt in range(1, attempts + 1):
        manager, instance = await browser.launch(
            config, browser.new_session_id(), options.browser_mode
        )
        try:
            return await process_account(instance, mail, router, config, options)
        except BotBlocked:
            print(f"↻ Blokir anti-bot (attempt {attempt}/{attempts}) → identitas baru")
            if attempt == attempts and not config.proxy_configured:
                print("   Tanpa proxy, relaunch tidak mengganti IP. Isi PROXY_* di .env.")
            await asyncio.sleep(human_delay(4, 9))
        except EmailRejected as exc:
            print(f"✗ GitHub menolak alamat email {exc} — coba MAIL_PROVIDER lain di .env")
            return False
        finally:
            await browser.close(manager)
            print("👋 Browser closed")
    return False
