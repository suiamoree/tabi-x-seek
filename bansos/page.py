"""Primitive interaksi halaman: cari elemen, klik, isi, navigasi, deteksi blokir.

Semua pencarian elemen dibatasi waktu berlapis: tiap panggilan locator dibatasi
LOCATOR_CALL_TIMEOUT dan keseluruhan pencarian dibatasi FIND_BUDGET, supaya satu
frame yang macet tidak menahan seluruh proses.
"""

from __future__ import annotations

import asyncio
import random
import time

from .config import (
    CF_CHALLENGE_TIMEOUT,
    CF_POLL_INTERVAL,
    FIND_BUDGET,
    HARD_REFRESH_ATTEMPTS,
    LOCATOR_CALL_TIMEOUT,
    NAV_TIMEOUT,
    SETTLE_TIMEOUT,
)
from .errors import BotBlocked, StepSkipped
from .human import guard, human_delay
from .prompt import MANUAL, ask, ask_retry, is_auto
from .selectors import (
    BOT_BLOCK_TEXTS,
    CLOUDFLARE_CHALLENGE,
    CLOUDFLARE_TEXTS,
)


# ═══ Pencarian elemen ═════════════════════════════════════════════════════════

async def find_visible(page, selectors: list[str], budget: float = FIND_BUDGET):
    """Selector pertama yang visible, dicari di main frame lalu semua iframe."""
    deadline = time.monotonic() + budget
    try:
        frames = [page, *page.frames[1:]]
    except Exception:
        frames = [page]

    for frame in frames:
        for selector in selectors:
            if time.monotonic() > deadline:
                return None
            try:
                loc = frame.locator(selector).first
                if not await guard(loc.count(), LOCATOR_CALL_TIMEOUT):
                    continue
                await guard(loc.scroll_into_view_if_needed(timeout=1000), LOCATOR_CALL_TIMEOUT)
                if await guard(loc.is_visible(), LOCATOR_CALL_TIMEOUT):
                    return loc
            except Exception:
                continue
    return None


async def resolve_locator(
    page, selectors: list[str], label: str, retries: int = 3, escalate: bool = True
):
    """Cari elemen → hard refresh (maks 2x) → cari lagi → baru tanya user.

    `escalate=False` untuk langkah yang sudah dibungkus `retry_after_refresh`: di
    sana refresh dan pertanyaan ke user diurus lapisan luar, jadi di sini cukup
    melaporkan tidak ketemu. Tanpa itu user ditanya dua kali untuk satu kegagalan.

    Return: Locator | None (tidak ketemu; pemanggil yang memutuskan) | MANUAL.
    Raise: StepSkipped kalau langkahnya dilewati (pilihan user atau mode auto).
    """
    while True:
        for refresh_count in range(HARD_REFRESH_ATTEMPTS + 1):
            for attempt in range(1, retries + 1):
                loc = await find_visible(page, selectors)
                if loc is not None:
                    return loc
                print(f"⚠️  [{label}] tidak ketemu (attempt {attempt}/{retries})")
                await asyncio.sleep(human_delay(1.0, 2.0))

            print(f"\n✗ [{label}] tidak ketemu setelah {retries}x percobaan.")
            print(f"   Selector yang dicoba: {selectors}")
            if not escalate:
                return None
            if refresh_count < HARD_REFRESH_ATTEMPTS:
                await refresh_before_ask(page, label, refresh_count + 1)

        choice = await ask_retry(label)
        if choice is False:
            raise StepSkipped(label)
        if choice is MANUAL:
            return MANUAL


async def _try_click(loc, timeout: int, label: str) -> bool:
    try:
        await asyncio.sleep(human_delay(0.3, 0.8))
        await loc.click(timeout=timeout)
    except Exception as exc:
        print(f"⚠️  [{label}] click gagal ({exc}), coba force click...")
        try:
            await loc.click(timeout=timeout, force=True)
        except Exception:
            return False
    await asyncio.sleep(human_delay(0.5, 1.2))
    return True


async def click_first_visible(
    page,
    selectors: list[str],
    timeout: int = 5000,
    retries: int = 3,
    label: str = "",
    optional: bool = False,
    escalate: bool = True,
) -> bool:
    """optional=True: tidak ketemu langsung False tanpa retry/prompt."""
    label = label or selectors[0]
    if optional:
        loc = await find_visible(page, selectors)
        if loc is None:
            return False
    else:
        loc = await resolve_locator(page, selectors, label, retries, escalate=escalate)
        if loc is None:
            return False
        if loc is MANUAL:
            return True

    if await _try_click(loc, timeout, label):
        return True
    if optional or not escalate:
        return False

    # Elemen ketemu tapi tidak mau diklik: ketutup overlay, atau node-nya sudah
    # dirender ulang sehingga handle-nya basi. Muat ulang lalu coba sekali lagi
    # dengan escalate=False supaya tidak berputar.
    await refresh_before_ask(page, label)
    return await click_first_visible(
        page, selectors, timeout, retries, label, optional, escalate=False
    )


async def fill_input(
    page,
    selectors: list[str],
    value: str,
    retries: int = 3,
    label: str = "",
    escalate: bool = False,
) -> bool:
    """escalate default False: mengisi field selalu bagian dari langkah yang lebih
    besar, dan memuat ulang di tengah pengisian menghapus field yang sudah terisi.
    Lapisan luar (`retry_after_refresh`) yang mengulang pengisian dari awal."""
    label = label or selectors[0]
    loc = await resolve_locator(page, selectors, label, retries, escalate=escalate)
    if loc is None:
        return False
    if loc is MANUAL:
        return True

    try:
        await asyncio.sleep(human_delay(0.2, 0.5))
        await loc.click()
        await asyncio.sleep(human_delay(0.1, 0.3))
        await loc.press("Control+a")
        await asyncio.sleep(human_delay(0.1, 0.2))
        await loc.press("Backspace")
        await asyncio.sleep(human_delay(0.1, 0.3))
        for char in value:
            await loc.type(char, delay=random.randint(40, 120))
        await asyncio.sleep(human_delay(0.3, 0.6))
        return True
    except Exception as exc:
        print(f"⚠️  [{label}] gagal diisi: {exc}")
        return False


async def nudge_field(page, selectors: list[str], value: str, label: str = "") -> bool:
    """Hapus 1 char terakhir lalu ketik ulang.

    GitHub meng-enable submit lewat event input/change. Kalau field diisi tapi
    event-nya tidak sampai, tombol terlihat ter-klik padahal form tidak jalan;
    mengetik ulang satu char memicu validasinya lagi.
    """
    loc = await find_visible(page, selectors)
    if loc is None or not value:
        return False
    try:
        await loc.click()
        await loc.press("End")
        await asyncio.sleep(human_delay(0.1, 0.3))
        await loc.press("Backspace")
        await asyncio.sleep(human_delay(0.2, 0.5))
        await loc.type(value[-1], delay=random.randint(60, 140))
        await asyncio.sleep(human_delay(0.4, 0.8))
        return True
    except Exception as exc:
        print(f"⚠️  Nudge {label or selectors[0]} gagal: {exc}")
        return False


# ═══ Teks & URL ═══════════════════════════════════════════════════════════════

async def has_text(page, text: str) -> bool:
    try:
        return await page.locator(f"text={text}").count() > 0
    except Exception:
        return False


async def has_any_text(page, texts: list[str]) -> bool:
    for text in texts:
        if await has_text(page, text):
            return True
    return False


async def wait_for_url_contains(page, *fragments: str, timeout: float = 30.0) -> bool:
    """Tunggu URL memuat salah satu fragment. True kalau sudah/berhasil sampai."""
    lowered = [f.lower() for f in fragments]
    if any(f in page.url.lower() for f in lowered):
        return True
    try:
        await page.wait_for_url(
            lambda url: any(f in url.lower() for f in lowered), timeout=timeout * 1000
        )
        return True
    except Exception:
        return False


# ═══ Navigasi ═════════════════════════════════════════════════════════════════

async def settle(page, timeout: float = SETTLE_TIMEOUT) -> None:
    """Tunggu jaringan menenang, tapi lanjut saja kalau tidak pernah idle."""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout * 1000)
    except Exception:
        pass
    await asyncio.sleep(human_delay(0.8, 1.8))


async def goto(page, url: str, timeout: float = NAV_TIMEOUT) -> bool:
    """Navigasi dengan batas waktu tegas, lalu tunggu DOM + jaringan menenang.

    `wait_until="networkidle"` sengaja tidak dipakai sebagai kondisi goto:
    GitHub menjaga koneksi analytics/live-update terbuka, jadi tidak pernah idle
    dan goto menggantung sampai timeout.
    """
    print(f"→ goto {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
    except Exception as exc:
        print(f"⚠️  goto {url} gagal/timeout: {exc}")
        return False
    await settle(page)
    await pass_cloudflare(page)
    return True


# Header yang dikirim browser sungguhan saat Ctrl+Shift+R. `page.keyboard` tidak
# bisa dipakai untuk itu: Playwright mengirim tombol ke konten halaman, bukan ke
# UI browser, jadi tidak ada reload yang terjadi. Header dilepas setelah selesai
# supaya request berikutnya kembali seperti browsing biasa — header no-cache yang
# menempel di tiap request justru anomali.
NO_CACHE_HEADERS = {"Cache-Control": "no-cache", "Pragma": "no-cache"}


async def _reload_once(page, timeout: float, no_cache: bool = False) -> bool:
    """Reload mentah tanpa pemeriksaan Cloudflare.

    Dipisah supaya `pass_cloudflare` bisa memuat ulang halaman tanpa memanggil
    dirinya sendiri lewat `reload`.
    """
    if no_cache:
        try:
            await page.set_extra_http_headers(NO_CACHE_HEADERS)
        except Exception:
            pass
    try:
        await page.reload(wait_until="domcontentloaded", timeout=timeout * 1000)
        ok = True
    except Exception as exc:
        print(f"⚠️  reload gagal/timeout: {exc}")
        ok = False
    finally:
        if no_cache:
            try:
                await page.set_extra_http_headers({})
            except Exception:
                pass
    await settle(page)
    return ok


async def reload(page, timeout: float = NAV_TIMEOUT) -> bool:
    ok = await _reload_once(page, timeout)
    await pass_cloudflare(page)
    return ok


async def hard_reload(page, timeout: float = NAV_TIMEOUT) -> bool:
    """Muat ulang tanpa cache; kalau reload gagal, navigasi ulang ke URL yang sama."""
    url = page.url
    if not url or url.startswith("about:"):
        # Belum pernah ada halaman yang termuat — tidak ada yang bisa direfresh.
        return False

    print("→ Hard refresh (tanpa cache)...")
    ok = await _reload_once(page, timeout, no_cache=True)
    await pass_cloudflare(page)
    if ok:
        return True
    return await goto(page, url, timeout)

async def refresh_before_ask(page, label: str, attempt: int = 1) -> None:
    """Hard refresh + jeda render, sebelum sebuah langkah menyerah.

    Sebagian besar kemacetan berasal dari halaman setengah ter-render atau bundle
    JS yang gagal mount, dan itu selesai sendiri setelah dimuat ulang — tidak
    perlu mengganggu user.

    Blokir anti-bot sengaja tidak diperiksa di sini: `BotBlocked` akan
    me-relaunch seluruh browser dan membuang key yang sudah dikumpulkan tapi
    belum di-push. github.py yang memeriksanya, di titik yang aman.
    """
    print(f"↻ [{label}] mentok — hard refresh {attempt}/{HARD_REFRESH_ATTEMPTS}, lalu coba lagi")
    await hard_reload(page)
    await asyncio.sleep(human_delay(1.5, 3.0))


async def retry_after_refresh(page, label: str, action, refresh: bool = True):
    """Coba → hard refresh (maks 2x) → kalau tetap gagal serahkan ke user.

    Satu-satunya jalur eskalasi di seluruh script: tiap langkah yang bisa berhenti
    dan bertanya ke user melewati sini dulu, jadi urutan itu tidak perlu ditulis
    ulang di tiap modul. Nilai kembalian `action` diteruskan apa adanya supaya
    langkah yang menghasilkan string (mis. API key) juga bisa memakainya.

    Jatah refresh dihitung per pemanggilan, bukan per putaran prompt: user yang
    memilih "coba lagi" mendapat jatah baru, sedangkan mode auto habis jatah →
    langsung skip lewat `ask_retry`.

    `refresh=False` untuk langkah yang kehilangan data kalau halaman dimuat ulang,
    atau yang justru menghapus hal yang mau dibaca (captcha yang baru diselesaikan
    manual).

    Return: hasil `action` yang truthy | MANUAL (user sudah kerjakan sendiri).
    Raise: StepSkipped kalau langkahnya dilewati (pilihan user atau mode auto).
    """
    while True:
        result = await action()
        if result:
            return result

        if refresh:
            for attempt in range(1, HARD_REFRESH_ATTEMPTS + 1):
                await refresh_before_ask(page, label, attempt)
                result = await action()
                if result:
                    return result

        choice = await ask_retry(label)
        if choice is False:
            raise StepSkipped(label)
        if choice is MANUAL:
            return MANUAL


# ═══ Halaman penghalang ═══════════════════════════════════════════════════════

async def on_cloudflare_challenge(page) -> bool:
    if await find_visible(page, CLOUDFLARE_CHALLENGE, budget=2.0) is not None:
        return True
    return await has_any_text(page, CLOUDFLARE_TEXTS)


async def wait_out_cloudflare(page, timeout: float = CF_CHALLENGE_TIMEOUT) -> bool:
    """Poll sampai interstitial hilang. False = masih ada setelah lewat batas.

    Camoufox adalah Firefox asli, jadi challenge biasanya selesai sendiri selama
    IP-nya stabil sepanjang alur (lihat `browser.proxy_username`). Tidak ada
    usaha mengakali challenge di sini — hanya menunggu.
    """
    if not await on_cloudflare_challenge(page):
        return True

    print(f"→ Challenge Cloudflare terdeteksi, menunggu (maks {timeout:.0f}s)...")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(CF_POLL_INTERVAL)
        if not await on_cloudflare_challenge(page):
            print("✓ Challenge Cloudflare lolos")
            return True
    return False


async def pass_cloudflare(page, timeout: float = CF_CHALLENGE_TIMEOUT) -> bool:
    """Tunggu challenge lolos → muat ulang (maks 2x) → baru serahkan ke user.

    Reload memakai `_reload_once`, bukan `reload`/`hard_reload`: keduanya
    memanggil fungsi ini lagi di akhir dan challenge yang belum lolos akan
    membuat rekursi tanpa dasar.
    """
    if await wait_out_cloudflare(page, timeout):
        return True

    for attempt in range(1, HARD_REFRESH_ATTEMPTS + 1):
        print(f"↻ Challenge Cloudflare belum lolos — muat ulang {attempt}/{HARD_REFRESH_ATTEMPTS}...")
        await _reload_once(page, NAV_TIMEOUT, no_cache=True)
        if await wait_out_cloudflare(page, timeout):
            return True

    if is_auto():
        print("⚠️  Challenge Cloudflare belum lolos — mode auto, lanjut apa adanya")
        return False

    while True:
        print("\n⚠️  Challenge Cloudflare belum lolos.")
        print("   Kalau proxy aktif, IP yang berganti tiap request bikin challenge")
        print("   tidak pernah selesai — cek PROXY_HOST dan sessid di .env.")
        if (await ask("   Selesaikan manual lalu [Enter]  |  s=lanjut paksa: ")).lower() == "s":
            return False
        if await wait_out_cloudflare(page, timeout):
            return True


async def bot_blocked(page) -> bool:
    """'We detected unusual activity' — retry selector tidak akan menolong."""
    return await has_any_text(page, BOT_BLOCK_TEXTS)


async def raise_if_bot_blocked(page) -> None:
    if not await bot_blocked(page):
        return
    print("\n" + "=" * 60)
    print("🚫 GitHub blokir: 'We detected unusual activity'")
    print("   IP + fingerprint sudah ditandai → relaunch dengan identitas baru")
    print("=" * 60)
    raise BotBlocked()
