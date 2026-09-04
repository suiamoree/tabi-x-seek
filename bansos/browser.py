"""Launch Camoufox + susun kredensial proxy DataImpulse.

Tiga hal yang diatur eksplisit di sini:

1. `proxy_username` — syntax parameter DataImpulse: parameter ditempel setelah
   login dengan pemisah `__` (dua underscore), key dan value dipisah titik,
   antar-parameter pakai `;`:

       http://login__cr.au;sessid.123:password@gw.dataimpulse.com:823

   `sessid` mengunci satu IP selama rata-rata 30 menit. Tanpa itu, port 823
   jalan di mode rotating: IP ganti tiap request, dan challenge Cloudflare tidak
   pernah selesai karena cookie cf_clearance terikat ke IP yang mengerjakannya.

2. `SCREEN_CONFIG` — geometri dipatok, bukan diacak. Camoufox defaultnya
   mengarang ukuran layar per-launch (1680x1050, 2560x1440, 3440x1440, ...), dan
   `Screen(...)` hanya batas untuk pengacakan itu, bukan nilai pasti. Menulis
   langsung ke `config` adalah satu-satunya cara mendapat angka tepat.

3. `MODES` — mode tampilan browser, dipilih di CLI sebelum run. Nilainya
   diteruskan apa adanya ke argumen `headless` Camoufox, termasuk `"virtual"`
   yang menjalankan browser di dalam display Xvfb (Linux saja).
"""

from __future__ import annotations

import random
import string
import time

from camoufox.addons import DefaultAddons
from camoufox.async_api import AsyncCamoufox
from camoufox.pkgman import OS_NAME

from .config import Settings

_SESSION_ALPHABET = string.ascii_lowercase + string.digits

# Ukuran jendela yang diminta.
WINDOW_WIDTH, WINDOW_HEIGHT = 1366, 720

# Layar dibuat sedikit lebih tinggi dari jendela. Jendela 1366x720 di layar yang
# persis 1366x720 berarti tidak ada taskbar sama sekali — CreepJS memakai
# `screen.height == screen.availHeight` sebagai penanda headless. 1366x768 juga
# resolusi laptop Windows yang paling umum, jadi tidak mencolok.
SCREEN_WIDTH, SCREEN_HEIGHT = 1366, 768
TASKBAR_HEIGHT = 40  # taskbar Windows
AVAIL_HEIGHT = SCREEN_HEIGHT - TASKBAR_HEIGHT

# Semua nilai turunan dihitung sekali supaya rantainya tetap konsisten:
# inner <= outer <= avail <= screen. Geometri yang mustahil (jendela lebih besar
# dari layar) langsung terbaca sebagai bot.
SCREEN_CONFIG = {
    "screen.width": SCREEN_WIDTH,
    "screen.height": SCREEN_HEIGHT,
    "screen.availWidth": SCREEN_WIDTH,
    "screen.availHeight": AVAIL_HEIGHT,
    "screen.availLeft": 0,
    "screen.availTop": 0,
    "window.outerWidth": WINDOW_WIDTH,
    "window.outerHeight": WINDOW_HEIGHT,
    # Jendela di tengah area yang tersedia, seperti jendela yang baru dibuka.
    "window.screenX": (SCREEN_WIDTH - WINDOW_WIDTH) // 2,
    "window.screenY": (AVAIL_HEIGHT - WINDOW_HEIGHT) // 2,
}


def new_session_id() -> str:
    """ID alnum saja — '.' dan ';' adalah pemisah parameter DataImpulse."""
    suffix = "".join(random.choices(_SESSION_ALPHABET, k=4))
    return f"acc{int(time.time())}{suffix}"


# ── Mode tampilan ─────────────────────────────────────────────────────────────
# Nilai dict diteruskan langsung ke argumen `headless` Camoufox.
#
# "virtual" menjalankan Firefox di dalam Xvfb: jendelanya tidak tampil, tapi
# browsernya berjalan dalam mode berjendela sungguhan, jadi tidak ada sinyal
# headless. Xvfb hanya ada di Linux — di Windows/macOS Camoufox melempar
# VirtualDisplayNotSupported, jadi pilihannya disaring lewat `available_modes`.
MODES = {
    "1": ("non-headless (jendela terlihat)", False),
    "2": ("virtual display (Xvfb, Linux saja)", "virtual"),
    "3": ("headless (paling mudah terdeteksi)", True),
}
DEFAULT_MODE = False
VIRTUAL_SUPPORTED = OS_NAME == "lin"


def available_modes() -> dict[str, tuple[str, bool | str]]:
    """Mode virtual dibuang di OS non-Linux — Xvfb tidak ada di sana."""
    if VIRTUAL_SUPPORTED:
        return dict(MODES)
    return {key: value for key, value in MODES.items() if value[1] != "virtual"}


def mode_label(mode: bool | str) -> str:
    for label, value in MODES.values():
        if value == mode:
            return label
    return str(mode)


def proxy_username(user: str, session_id: str, country: str = "") -> str:
    params = [f"cr.{country}"] if country else []
    params.append(f"sessid.{session_id}")
    return f"{user}__{';'.join(params)}"


def build_proxy(config: Settings, session_id: str) -> dict | None:
    """None kalau proxy tidak diaktifkan — script tetap jalan tanpa proxy."""
    if not config.proxy_configured:
        return None
    return {
        "server": f"http://{config.proxy_host}",
        "username": proxy_username(config.proxy_user, session_id, config.proxy_country),
        "password": config.proxy_pass,
    }


def _launch_kwargs(proxy: dict | None, headless: bool | str) -> dict:
    kwargs = {
        "headless": headless,
        "block_webrtc": True,
        # humanize=True: Camoufox menginterpolasi tiap gerakan kursor di level
        # browser, jadi tidak ada lompatan pointer instan ("rapid clicks").
        #
        # Angka, bukan True: nilainya adalah durasi maksimum per gerakan, dan
        # default `True` berarti sampai 1.5s. Karena interpolasinya per panggilan
        # `mouse.move`, tiap gerakan kita berbiaya segitu — warmup jadi 30s+ dan
        # selalu kena timeout, drag captcha jadi setengah menit dan kedaluwarsa.
        # 0.3s masih di rentang gerakan tangan manusia untuk jarak sependek ini.
        "humanize": 0.3,
        # Layar 1366x768 adalah resolusi laptop Windows; kalau OS-nya diacak ke
        # macOS, kombinasinya justru jadi tidak wajar.
        "os": "windows",
        "config": dict(SCREEN_CONFIG),
        # uBlock Origin dipasang Camoufox secara default dan memblokir skrip
        # analytics/ads. Situs target memakai skrip semacam itu untuk captcha dan
        # deteksi bot; kalau diblokir, halaman bisa menggantung atau menolak
        # OAuth. Selain itu addon yang terpasang sendiri sudah terdeteksi.
        "exclude_addons": [DefaultAddons.UBO],
        # Menulis screen.*/window.* langsung memicu peringatan bahwa Camoufox
        # biasanya mengurusnya sendiri. Di sini memang disengaja: ukuran harus
        # pasti, dan semua nilai turunannya sudah dibuat konsisten di atas.
        "i_know_what_im_doing": True,
        "locale": "en-US",
        "enable_cache": True,
        "firefox_user_prefs": {
            "widget.windows.window_occlusion_tracking.enabled": False,
            "dom.min_background_timeout_value": 10,
            # devtools.* dimatikan: GitHub menandai "use of developer tools".
            "devtools.selfxss.count": 0,
            "devtools.everOpened": False,
            "devtools.debugger.remote-enabled": False,
            # Firefox menolak navigator.clipboard.readText() dari halaman biasa
            # (butuh konfirmasi "Paste" dari user), dan itu yang membuat script
            # sering minta bantuan manual saat mengambil API key. Dua pref ini
            # yang dipakai Firefox sendiri untuk automated testing membuat
            # readText() langsung mengembalikan isi clipboard. Keduanya tidak
            # terlihat dari JS halaman, jadi bukan sinyal tambahan buat anti-bot.
            "dom.events.asyncClipboard.readText": True,
            "dom.events.testing.asyncClipboard": True,
        },
    }
    if proxy:
        kwargs["proxy"] = proxy
        # geoip menyelaraskan timezone/locale dengan IP proxy; mismatch
        # timezone-vs-IP adalah sinyal bot yang kuat. Hanya benar kalau IP-nya
        # stabil selama sesi — itulah gunanya sessid.
        kwargs["geoip"] = True
    return kwargs


async def launch(config: Settings, session_id: str, headless: bool | str = DEFAULT_MODE):
    """Return (manager, browser). Manager ditutup lewat `close`."""
    proxy = build_proxy(config, session_id)
    if proxy:
        print(f"🌐 Proxy sessid: {session_id}")
    elif config.proxy_enabled:
        print("🌐 Tanpa proxy (PROXY_USER/PROXY_PASS kosong di .env)")
    else:
        print("🌐 Tanpa proxy (PROXY_ENABLED=0)")

    print(f"🚀 Launching browser {WINDOW_WIDTH}x{WINDOW_HEIGHT} — {mode_label(headless)}...")
    manager = AsyncCamoufox(**_launch_kwargs(proxy, headless))
    browser = await manager.__aenter__()
    print("✓ Browser launched")
    return manager, browser


async def close(manager) -> None:
    try:
        await manager.__aexit__(None, None, None)
    except Exception:
        pass
