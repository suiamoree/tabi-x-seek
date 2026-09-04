"""Profil gerak mirip manusia: delay acak, kurva bezier, drag slider, warmup.

`guard` juga di sini karena keduanya soal waktu, dan menaruhnya di `page.py`
akan membuat import melingkar (page butuh delay, human butuh guard).
"""

from __future__ import annotations

import asyncio
import random

from .config import WARMUP_TIMEOUT


def human_delay(min_sec: float = 0.5, max_sec: float = 1.5) -> float:
    return random.uniform(min_sec, max_sec)


async def guard(coro, timeout: float, label: str = ""):
    """Batas waktu untuk operasi yang bisa diam tanpa melempar error.

    mouse.move/wheel dan count()/is_visible() di Firefox kadang tidak pernah
    kembali saat halaman masih sibuk. Tidak ada exception yang dilempar, jadi
    try/except tidak menolong — satu-satunya jalan keluar adalah timeout.
    Return None kalau lewat batas; pemanggil memutuskan artinya.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        if label:
            print(f"⚠️  [{label}] timeout {timeout}s — dilanjut")
        return None
    except Exception:
        return None


async def move_along_curve(page, x0: float, y0: float, x1: float, y1: float, steps: int) -> None:
    """Bezier kuadratik dengan control point acak — tangan manusia tidak lurus."""
    cx = (x0 + x1) / 2 + random.uniform(-25, 25)
    cy = (y0 + y1) / 2 + random.uniform(-18, 18)
    for i in range(1, steps + 1):
        t = i / steps
        inv = 1 - t
        x = inv * inv * x0 + 2 * inv * t * cx + t * t * x1
        y = inv * inv * y0 + 2 * inv * t * cy + t * t * y1
        await page.mouse.move(x, y)
        await asyncio.sleep(human_delay(0.008, 0.025))


async def drag_slider(page, container, handle) -> bool:
    """Drag handle sampai ujung kanan track dengan profil gerak manusia.

    Yang membuat drag terlihat manusiawi: approach melengkung (bukan teleport ke
    tengah handle), kecepatan ease-in-out, 1-3 micro-pause di tengah drag, jitter
    vertikal yang berjalan (random walk, bukan noise per frame), overshoot lalu
    koreksi balik, dan hold sebelum mouse up.
    """
    handle_box = await handle.bounding_box()
    track_box = await container.bounding_box()
    if not handle_box or not track_box:
        return False

    start_x = handle_box["x"] + handle_box["width"] / 2
    y = handle_box["y"] + handle_box["height"] / 2
    end_x = track_box["x"] + track_box["width"] - handle_box["width"] / 2 - 2
    span = end_x - start_x
    if span < 5:
        return False

    # Approach: mulai dari titik acak agak jauh, gerak melengkung ke handle.
    await page.mouse.move(start_x - random.uniform(60, 130), y + random.uniform(-45, 45))
    await asyncio.sleep(human_delay(0.25, 0.7))
    await move_along_curve(page, start_x - 80, y - 20, start_x, y, random.randint(10, 16))
    await asyncio.sleep(human_delay(0.15, 0.45))

    await page.mouse.down()
    await asyncio.sleep(human_delay(0.12, 0.32))

    overshoot = random.uniform(4, 11)
    steps = random.randint(45, 70)
    pauses = sorted(random.sample(range(8, steps - 6), random.randint(1, 3)))
    drift = 0.0

    for i in range(1, steps + 1):
        t = i / steps
        # Ease-in-out kubik: akselerasi di awal, deselerasi di akhir.
        eased = 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
        drift = max(-2.5, min(2.5, drift + random.uniform(-0.6, 0.6)))
        await page.mouse.move(start_x + span * eased + overshoot * eased, y + drift)

        if i in pauses:
            await asyncio.sleep(human_delay(0.09, 0.26))
        else:
            # Frame di tengah drag lebih cepat daripada di ujung.
            fast = 0.2 < t < 0.8
            await asyncio.sleep(human_delay(0.008, 0.022) if fast else human_delay(0.02, 0.05))

    # Koreksi balik dari overshoot, pelan-pelan.
    await asyncio.sleep(human_delay(0.08, 0.2))
    back_steps = random.randint(4, 8)
    target = end_x + overshoot
    for i in range(1, back_steps + 1):
        await page.mouse.move(target - overshoot * (i / back_steps), y + random.uniform(-0.8, 0.8))
        await asyncio.sleep(human_delay(0.02, 0.06))

    await asyncio.sleep(human_delay(0.12, 0.35))
    await page.mouse.up()
    await asyncio.sleep(human_delay(1.2, 2.4))
    return True


async def warmup(page, moves: int = 3) -> None:
    """Gerakan mouse + scroll acak sebelum berinteraksi.

    Sinyal 'rapid taps/clicks' muncul karena bot langsung klik tanpa gerakan
    pointer sama sekali. Warmup mengisi jejak input yang wajar.

    Dibungkus timeout: mouse.move/wheel di Firefox bisa menggantung tanpa error
    saat halaman masih sibuk, dan warmup bukan langkah yang wajib sukses.
    """

    async def _run():
        width, height = 1200, 700
        x, y = random.uniform(200, width), random.uniform(150, height)
        for _ in range(moves):
            nx, ny = random.uniform(120, width), random.uniform(100, height)
            await move_along_curve(page, x, y, nx, ny, random.randint(8, 16))
            x, y = nx, ny
            await asyncio.sleep(human_delay(0.15, 0.5))

        for _ in range(random.randint(1, 3)):
            await page.mouse.wheel(0, random.randint(120, 420))
            await asyncio.sleep(human_delay(0.3, 0.9))
        await page.mouse.wheel(0, -random.randint(80, 260))
        await asyncio.sleep(human_delay(0.3, 0.8))

    await guard(_run(), WARMUP_TIMEOUT, label="warmup")
