"""Slider captcha GitHub (octocaptcha)."""

from __future__ import annotations

import asyncio
import time

from .config import HARD_REFRESH_ATTEMPTS
from .human import drag_slider, human_delay
from .page import find_visible, hard_reload, reload, retry_after_refresh
from .selectors import SLIDER

async def _wait_for_container(page, timeout: float):
    """Captcha dirender belakangan dan sering di dalam iframe octocaptcha."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        container = await find_visible(page, SLIDER["container"])
        if container is not None:
            return container
        await asyncio.sleep(0.5)
    return None


async def _slide_until_gone(page, container, attempts: int) -> bool:
    """Drag lalu refresh untuk verifikasi — GitHub force reload saat captcha lolos."""
    for attempt in range(1, attempts + 1):
        print(f"→ Slider captcha terdeteksi, sliding ({attempt}/{attempts})...")
        handle = await find_visible(page, SLIDER["handle"])
        if handle is None or not await drag_slider(page, container, handle):
            return False

        await asyncio.sleep(human_delay(1.5, 2.8))
        print("→ Refresh untuk verifikasi captcha lolos...")
        await reload(page)

        container = await find_visible(page, SLIDER["container"])
        if container is None:
            print("✓ Slider captcha lolos")
            return True
    return False


async def _gone(page) -> bool:
    return await find_visible(page, SLIDER["container"], budget=3.0) is None


async def handle_slider(page, appear_timeout: float = 10.0, attempts: int = 3) -> bool:
    """Blokir sampai captcha benar-benar hilang. True = halaman sudah bersih.

    Urutannya: drag → hard refresh (maks 2x, tiap kali drag lagi) → baru tanya
    user. Hard refresh dijalankan di sini, bukan lewat `retry_after_refresh`,
    karena setelah refresh captcha harus ditunggu muncul dari awal — container yang
    lama sudah tidak ada.
    """
    print("→ Cek slider captcha...")
    container = await _wait_for_container(page, appear_timeout)
    if container is None:
        print("✓ Tidak ada slider captcha")
        return True

    if await _slide_until_gone(page, container, attempts):
        return True

    for refresh in range(1, HARD_REFRESH_ATTEMPTS + 1):
        print(f"↻ Slider captcha belum lolos — hard refresh {refresh}/{HARD_REFRESH_ATTEMPTS}...")
        await hard_reload(page)
        container = await _wait_for_container(page, appear_timeout)
        if container is None:
            print("✓ Slider captcha hilang setelah hard refresh")
            return True
        if await _slide_until_gone(page, container, attempts):
            return True

    # Sampai sini otomatis sudah habis akal: minta user, tanpa hard refresh lagi
    # supaya captcha yang baru saja diselesaikan manual tidak ikut hilang.
    # StepSkipped dibiarkan naik ke `runner` — akun tanpa captcha lolos tidak bisa
    # dilanjutkan, dan menangkapnya di sini membuat lapisan retry di atas bertanya
    # hal yang sama sekali lagi.
    await retry_after_refresh(
        page, "slider captcha GitHub", lambda: _gone(page), refresh=False
    )
    print("✓ Slider captcha lolos")
    return True
