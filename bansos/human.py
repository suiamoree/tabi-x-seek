"""Profil gerak mirip manusia: delay acak, drag slider, warmup.

Interpolasi antar titik diserahkan ke Camoufox (`humanize` di `browser.py`), yang
menghaluskan tiap `mouse.move` di level browser. Karena itu jumlah panggilan
`mouse.move` di sini dijaga sedikit: tiap panggilan berbiaya ~0.2-0.8s, jadi kurva
yang dipecah sendiri jadi puluhan titik membuat satu gerakan makan puluhan detik.

`guard` juga di sini karena keduanya soal waktu, dan menaruhnya di `page.py`
akan membuat import melingkar (page butuh delay, human butuh guard).
"""


from __future__ import annotations

import asyncio
import random

from .config import DRAG_STEPS_MAX, DRAG_STEPS_MIN, WARMUP_TIMEOUT


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


async def drag_slider(page, container, handle) -> bool:
    """Drag handle sampai ujung kanan track, dengan sedikit variasi manusiawi.

    Jumlah langkahnya sengaja sedikit (bukan puluhan frame): Camoufox menghaluskan
    tiap `mouse.move` di level browser dan tiap panggilan berbiaya ~0.2-0.8s, jadi
    50 langkah berarti drag yang makan setengah menit — captcha-nya kedaluwarsa
    lebih dulu. Yang tetap dipertahankan: approach dari titik agak jauh, kecepatan
    ease-in-out, satu micro-pause, overshoot lalu koreksi, dan hold sebelum mouse
    up. Interpolasi antar titiknya dikerjakan Camoufox.
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

    # Approach: mulai dari titik agak jauh, bukan teleport ke tengah handle.
    await page.mouse.move(start_x - random.uniform(60, 130), y + random.uniform(-45, 45))
    await asyncio.sleep(human_delay(0.25, 0.7))
    await page.mouse.move(start_x, y)
    await asyncio.sleep(human_delay(0.15, 0.45))

    await page.mouse.down()
    await asyncio.sleep(human_delay(0.12, 0.32))

    overshoot = random.uniform(4, 11)
    steps = random.randint(DRAG_STEPS_MIN, DRAG_STEPS_MAX)
    pause_at = random.randint(2, max(2, steps - 2))

    for i in range(1, steps + 1):
        t = i / steps
        # Ease-in-out kubik: akselerasi di awal, deselerasi di akhir.
        eased = 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
        drift = random.uniform(-1.5, 1.5)
        await page.mouse.move(start_x + span * eased + overshoot * eased, y + drift)
        if i == pause_at:
            await asyncio.sleep(human_delay(0.12, 0.3))

    # Koreksi balik dari overshoot.
    await asyncio.sleep(human_delay(0.08, 0.2))
    await page.mouse.move(end_x, y + random.uniform(-0.8, 0.8))

    await asyncio.sleep(human_delay(0.12, 0.35))
    await page.mouse.up()
    await asyncio.sleep(human_delay(1.2, 2.4))
    return True


async def warmup(page, moves: int = 3) -> None:
    """Gerakan mouse + scroll acak sebelum berinteraksi.

    Sinyal 'rapid taps/clicks' muncul karena bot langsung klik tanpa gerakan
    pointer sama sekali. Warmup mengisi jejak input yang wajar.

    Interpolasinya diserahkan ke Camoufox (`humanize` di browser.py), bukan
    dihitung di Python. Camoufox menghaluskan **setiap** `mouse.move` di level
    browser, jadi kurva yang dipecah sendiri jadi 8-16 titik membuat satu kurva
    memakan 8-16 kali biaya itu — terukur ~0.7s per titik, yang membuat warmup
    lama molor sampai 30s+ dan selalu kena timeout.
    """

    async def _run():
        width, height = 1200, 700
        for _ in range(moves):
            await page.mouse.move(random.uniform(120, width), random.uniform(100, height))
            await asyncio.sleep(human_delay(0.15, 0.5))

        for _ in range(random.randint(1, 2)):
            await page.mouse.wheel(0, random.randint(120, 420))
            await asyncio.sleep(human_delay(0.3, 0.9))
        await page.mouse.wheel(0, -random.randint(80, 260))
        await asyncio.sleep(human_delay(0.3, 0.8))

    await guard(_run(), WARMUP_TIMEOUT, label="warmup")
