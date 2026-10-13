"""Orkestrasi satu akun end-to-end, plus retry saat kena blokir anti-bot."""

from __future__ import annotations

import asyncio
import random
import time

from . import browser, github, sites, storage
from .config import GithubAccount, RunOptions, Settings, Site
from .errors import BotBlocked, EmailRejected, RateLimited, StepSkipped
from .human import human_delay
from .mail import MailProvider, new_fresh_address
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


async def _register_key(options: RunOptions, key: str) -> bool:
    """Daftarkan key ke seen_keys secara atomic. False kalau duplikat."""
    async with options.seen_lock:
        if key in options.seen_keys:
            return False
        options.seen_keys.add(key)
        return True


async def _flush(
    router: NineRouter | None,
    options: RunOptions,
    email: str,
    push_label: str,
    batch: list[tuple[Site, str]],
    label: str,
) -> None:
    """Push + save batch key yang sudah dikumpulkan, lalu cetak hasilnya."""
    if not batch:
        return
    await _push_keys(router, batch, push_label)
    if options.save_file:
        _save(email, "", push_label, batch)
    for site, key in batch:
        print(f"{label}    {site.name}: {key}")


async def process_account(
    browser_instance,
    mail: MailProvider,
    router: NineRouter | None,
    config: Settings,
    options: RunOptions,
    slot: int = 1,
) -> bool:
    """Kerjakan semua site dalam config.sites.

    Urutan untuk direct sites (Agnes + TokenHarbor):
      1. TokenHarbor selesai → push + save TH key langsung
      2. Agnes selesai → push + save Agnes key

    Ini supaya TH yang biasanya lebih cepat sudah tersimpan walau Agnes gagal.
    """
    github_sites = [s for s in config.sites if s.requires_github]
    direct_sites = [s for s in config.sites if not s.requires_github]
    # Pisah TH dan Agnes supaya bisa di-flush terpisah
    th_sites = [s for s in direct_sites if s.name != "AgnesAI"]
    agnes_sites = [s for s in direct_sites if s.name == "AgnesAI"]

    page = await browser_instance.new_page()
    started = time.time()
    all_collected: list[tuple[Site, str]] = []
    label = f"[slot {slot}]"
    # Set lokal per slot: mencegah collect_key membaca ulang key yang baru saja
    # dibuat dalam satu run slot yang sama. Inter-slot dedup tetap lewat
    # options.seen_keys + _register_key (yang pakai lock).
    local_seen: set[str] = set()

    try:
        shared_email: str | None = None
        if direct_sites:
            try:
                shared_email = await new_fresh_address(mail)
                print(f"{label} Email bersama (direct): {shared_email}")
            except Exception as exc:
                print(f"{label} ⚠️  Gagal generate email bersama: {exc}")

        email_for_name = shared_email or ""
        key_name = email_for_name.split("@")[0] if email_for_name else "direct"
        push_label_direct = key_name

        # ── 1. TokenHarbor dulu ──────────────────────────────────────────────
        th_batch: list[tuple[Site, str]] = []
        for site in th_sites:
            try:
                key = await sites.collect_key(
                    page, site, GithubAccount("direct", ""),
                    local_seen, mail=mail, shared_email=shared_email,
                )
            except StepSkipped as exc:
                print(f"{label} ⚠️  {site.name} dilewati: {exc}")
                key = None
            if key and await _register_key(options, key):
                th_batch.append((site, key))
                all_collected.append((site, key))
            elif key:
                print(f"{label} ⚠️  Key {site.name} duplikat — dilewati")
            else:
                print(f"{label} ⚠️  {site.name} tidak menghasilkan key")

        # Flush TH sebelum Agnes mulai
        if th_batch:
            print(f"{label} → Simpan TokenHarbor key sebelum lanjut ke Agnes...")
            await _flush(router, options, shared_email or "direct", push_label_direct, th_batch, label)

        # ── 2. Agnes sesudah TH tersimpan ────────────────────────────────────
        agnes_batch: list[tuple[Site, str]] = []
        for site in agnes_sites:
            try:
                key = await sites.collect_key(
                    page, site, GithubAccount("direct", ""),
                    local_seen, mail=mail, shared_email=shared_email,
                )
            except StepSkipped as exc:
                print(f"{label} ⚠️  {site.name} dilewati: {exc}")
                key = None
            if key and await _register_key(options, key):
                agnes_batch.append((site, key))
                all_collected.append((site, key))
            elif key:
                print(f"{label} ⚠️  Key {site.name} duplikat — dilewati")
            else:
                print(f"{label} ⚠️  {site.name} tidak menghasilkan key")

        if agnes_batch:
            await _flush(router, options, shared_email or "direct", push_label_direct, agnes_batch, label)

        # ── 3. GitHub sites ───────────────────────────────────────────────────
        email = shared_email or "direct"
        username = "direct"
        registered = None
        if github_sites:
            password = config.github_password
            registered = await github.register(page, mail, password)
            if not registered:
                if not all_collected:
                    return False
            else:
                email, username = registered
                print(f"\n{'=' * 60}")
                print(f"{label} Email    : {email}")
                print(f"{label} Username : {username}")
                print(f"{'=' * 60}")

                if not await github.submit_otp(page, mail, email, started):
                    pass
                elif not await github.login(page, username, password):
                    pass
                else:
                    account = GithubAccount(username=username, password=password)
                    gh_batch: list[tuple[Site, str]] = []
                    for site in github_sites:
                        try:
                            key = await sites.collect_key(page, site, account, local_seen, mail=mail)
                        except StepSkipped as exc:
                            print(f"{label} ⚠️  {site.name} dilewati: {exc}")
                            key = None
                        if key and await _register_key(options, key):
                            gh_batch.append((site, key))
                            all_collected.append((site, key))
                        elif key:
                            print(f"{label} ⚠️  Key {site.name} duplikat — dilewati")
                        else:
                            print(f"{label} ⚠️  {site.name} tidak menghasilkan key")
                    if gh_batch:
                        await _flush(router, options, email, username, gh_batch, label)

        if not all_collected:
            print(f"{label} ✗ Tidak ada API key yang berhasil di-collect")
            return False

        return True

    except StepSkipped as exc:
        print(f"{label} ⚠️  Akun dilewati: {exc}")
        return False
    finally:
        await page.close()


async def run_account(
    mail: MailProvider,
    router: NineRouter | None,
    config: Settings,
    options: RunOptions,
    attempts: int = 3,
    slot: int = 1,
) -> bool:
    """Satu akun, browser sendiri."""
    for attempt in range(1, attempts + 1):
        manager, instance = await browser.launch(
            config, browser.new_session_id(), options.browser_mode
        )
        try:
            return await process_account(instance, mail, router, config, options, slot=slot)
        except BotBlocked:
            print(f"[slot {slot}] ↻ Blokir anti-bot (attempt {attempt}/{attempts}) → identitas baru")
            if attempt == attempts and not config.proxy_configured:
                print("   Tanpa proxy, relaunch tidak mengganti IP. Isi PROXY_* di .env.")
            await asyncio.sleep(human_delay(4, 9))
        except RateLimited as exc:
            print(f"[slot {slot}] ↻ Rate-limit ({exc}) → ganti session proxy (IP baru)")
            if not config.proxy_configured:
                print("   Tanpa proxy, IP tidak bisa diganti. Isi PROXY_* di .env.")
            await asyncio.sleep(human_delay(2, 5))
        except EmailRejected as exc:
            print(f"[slot {slot}] ✗ GitHub menolak alamat email {exc}")
            return False
        finally:
            await browser.close(manager)
            print(f"[slot {slot}] 👋 Browser closed")
    return False


async def run_concurrent(
    mail: MailProvider,
    router: NineRouter | None,
    config: Settings,
    options: RunOptions,
    total: int,
    concurrency: int,
) -> int:
    """Jalankan `total` akun dengan maksimal `concurrency` browser sekaligus.

    Tiap akun launch browser baru dengan session_id baru → IP proxy baru dari
    pool DataImpulse. Rate-limit TokenHarbor (per-IP) otomatis di-bypass karena
    setiap akun sudah pakai IP berbeda.

    Stagger delay antar slot supaya tidak semua browser buka halaman bersamaan.
    """
    succeeded = 0
    sem = asyncio.Semaphore(concurrency)

    STAGGER_BASE_MIN, STAGGER_BASE_MAX = 8.0, 12.0
    JITTER_MAX = 5.0

    slot_delays = [0.0]
    for i in range(1, total):
        base = random.uniform(STAGGER_BASE_MIN, STAGGER_BASE_MAX)
        jitter = random.uniform(0, JITTER_MAX)
        slot_delays.append(slot_delays[-1] + base + jitter)

    print("\nLaunch schedule (perkiraan):")
    for i, d in enumerate(slot_delays, start=1):
        mins, secs = divmod(int(d), 60)
        ts = f"+{mins:02d}:{secs:02d}"
        print(f"  slot {i:2d}: {ts}" + (" (langsung)" if d == 0 else ""))
    if options.use_proxy:
        print("  (proxy aktif — tiap akun dapat IP baru otomatis)")

    async def _one(index: int) -> bool:
        d = slot_delays[index - 1]
        if d > 0:
            mins, secs = divmod(int(d), 60)
            print(f"[slot {index}] Delay launch {mins:02d}:{secs:02d} (scheduled)")
            await asyncio.sleep(d)
        async with sem:
            result = await run_account(mail, router, config, options, slot=index)
            status = "✅" if result else "❌"
            print(f"\n{status} Akun [{index}/{total}] selesai")
            return result

    tasks = [asyncio.create_task(_one(i)) for i in range(1, total + 1)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if r is True:
            succeeded += 1
        elif isinstance(r, Exception):
            print(f"❌ Task error: {r}")
    return succeeded
