"""Alur per situs: consent → OAuth GitHub → buat API key → ambil key.

Identik untuk semua entry di `config.Settings.sites`.
"""

from __future__ import annotations

import asyncio
import re

from . import github
from .config import CONSENT_DELAY, DOM_READ_ATTEMPTS, OAUTH_ATTEMPTS, GithubAccount, Site
from .human import human_delay
from .page import (
    click_first_visible,
    fill_input,
    find_visible,
    goto,
    has_text,
    retry_after_refresh,
    settle,
    wait_for_url_contains,
)
from .prompt import MANUAL, ask, is_auto
from .selectors import (
    API_KEY_MIN_LENGTH,
    API_KEY_PATTERN,
    KEY_TRUNCATION_MARKS,
    OAUTH_FAILED_TEXT,
    SITE,
)


async def _accept_consent(page) -> bool:
    """Centang User Agreement kalau ada (SeekAI), lalu jeda.

    Checkbox-nya `span[role=checkbox]`; `input#legal-consent` disembunyikan pakai
    clip-path jadi tidak bisa diklik. Sudah tercentang → tidak diklik lagi supaya
    tidak toggle balik. Consent harus dicentang sebelum Continue with GitHub,
    kalau tidak tombol OAuth-nya ditolak server.
    """
    box = await find_visible(page, SITE["consent_checkbox"])
    if box is None:
        return False

    try:
        if await box.get_attribute("aria-checked") == "true":
            print("✓ Consent checkbox sudah tercentang")
            return True
    except Exception:
        pass

    print("→ Centang consent checkbox (User Agreement)...")
    if not await click_first_visible(
        page, SITE["consent_checkbox"], label="consent checkbox", escalate=False
    ):
        return False

    print(f"→ Delay {CONSENT_DELAY}s setelah consent...")
    await asyncio.sleep(CONSENT_DELAY)
    return True


async def _click_continue(page, site: Site) -> bool:
    """Klik 'Continue with GitHub' sampai halaman berpindah ke GitHub."""
    for attempt in range(1, OAUTH_ATTEMPTS + 1):
        print(f"→ Klik Continue with GitHub ({attempt}/{OAUTH_ATTEMPTS})...")
        await click_first_visible(page, SITE["github_continue"], optional=True)

        if await wait_for_url_contains(page, "github.com", timeout=10):
            return True

        # Toast ini muncul saat captcha/rate limit menolak permintaan OAuth.
        if await has_text(page, OAUTH_FAILED_TEXT):
            print(f"⚠️  {OAUTH_FAILED_TEXT}")

        # Tanpa toast & tanpa redirect ke GitHub: app sudah pernah diauthorize.
        if site.host in page.url and "sign-up" not in page.url:
            return True

    return False


async def _login_if_asked(page, account: GithubAccount) -> bool:
    """Login lagi kalau GitHub memintanya di tengah OAuth.

    Terjadi walau login sudah berhasil sebelumnya: cookie sesi tidak selalu
    langsung diakui di endpoint OAuth, jadi `/login/oauth/authorize` bisa
    menampilkan form login lagi. Tanpa penanganan ini alurnya berhenti di situ —
    tombol Authorize tidak akan pernah ada.

    Return False hanya kalau login-nya sendiri gagal; halaman yang tidak meminta
    login bukan kegagalan.
    """
    if not await github.on_login_page(page):
        return True

    print("⚠️  GitHub minta login lagi di tengah OAuth — login dulu...")
    if not await github.login(page, account.username, account.password):
        return False
    await settle(page)
    return True


async def _authorize_app(page) -> bool:
    """Klik Authorize hanya kalau memang di halaman consent OAuth."""
    if "login/oauth/authorize" not in page.url.lower():
        return True

    print("→ Halaman consent OAuth, klik Authorize...")
    if not await click_first_visible(
        page, SITE["github_authorize"], label="Authorize", escalate=False
    ):
        return False
    await asyncio.sleep(human_delay(2.0, 3.0))
    return True


async def _wait_dashboard(page, site: Site, timeout: float = 30.0) -> bool:
    return await wait_for_url_contains(
        page, f"{site.host}/dashboard", f"{site.host}/overview", timeout=timeout
    )


async def _oauth_flow(page, site: Site, account: GithubAccount) -> bool:
    """consent → Continue with GitHub → (login lagi kalau diminta) → Authorize → dashboard.

    Satu kesatuan supaya bisa diulang utuh setelah hard refresh: refresh
    mengosongkan checkbox consent dan bisa mengembalikan halaman ke sign-up, jadi
    mengulang bagian akhirnya saja tidak cukup. Aman dijalankan ulang setelah OAuth
    berhasil — consent dan tombolnya sudah tidak ada, dan URL dashboard langsung
    memenuhi syarat selesai.
    """
    if await _wait_dashboard(page, site, timeout=1.0):
        return True

    # Percobaan ulang bisa dimulai dari halaman mana saja — termasuk dari dashboard
    # GitHub, kalau rantai OAuth-nya putus setelah login ulang. Balik ke halaman
    # situs dulu, karena tombol Continue with GitHub hanya ada di sana.
    if site.host not in page.url:
        print(f"→ Bukan di {site.host} lagi, buka ulang halaman situs...")
        await goto(page, site.signup_url)

    await _accept_consent(page)
    if not await _click_continue(page, site):
        return False

    # Setelah mendarat di GitHub, sesi bisa terbaca belum login walau login
    # sebelumnya berhasil. Ditangani sebelum mencari tombol Authorize, karena di
    # halaman login tombol itu tidak ada.
    if not await _login_if_asked(page, account):
        return False

    await _authorize_app(page)

    # Landing di dashboard = bukti OAuth sukses, jadi ditunggu; bukan goto.
    print(f"→ Menunggu dashboard {site.name}...")
    return await _wait_dashboard(page, site)

async def _create_key(page, site: Site, key_name: str) -> bool:
    """Buka /keys → Create API Key → isi nama → Save.

    Semua langkah `escalate=False`: yang membungkusnya adalah
    `retry_after_refresh` di `collect_key`, jadi hard refresh dan pertanyaan ke
    user cukup terjadi sekali di lapisan itu.
    """
    print(f"→ Buka halaman keys: {site.keys_url}")
    await goto(page, site.keys_url)
    if not await wait_for_url_contains(page, site.keys_url, timeout=20):
        print("✗ Halaman keys tidak terbuka")
        return False
    await asyncio.sleep(human_delay(1, 2))

    print("→ Klik Create API Key...")
    if not await click_first_visible(
        page, SITE["create_key"], label="Create API Key", escalate=False
    ):
        return False
    await asyncio.sleep(3)

    print(f"→ Input nama key: {key_name}")
    if not await fill_input(page, SITE["key_name"], key_name, label="key name"):
        return False
    await asyncio.sleep(1)

    print("→ Klik Save changes...")
    if not await click_first_visible(
        page, SITE["save"], label="Save changes", escalate=False
    ):
        return False
    await asyncio.sleep(3)
    return True


# ═══ Ambil nilai API key ══════════════════════════════════════════════════════

# Semua tempat key bisa muncul: value input/textarea (key baru biasanya ditaruh di
# input readonly), atribut data-* yang dibaca tombol copy, lalu teks halaman
# sebagai jaring terakhir. Pencocokan pola dilakukan di Python supaya polanya
# tetap satu di selectors.py.
_SCRAPE_JS = """() => {
  const out = [];
  for (const el of document.querySelectorAll('input, textarea')) {
    if (el.value) out.push(el.value);
  }
  for (const el of document.querySelectorAll('[data-clipboard-text], [data-copy], [data-value]')) {
    for (const attr of ['data-clipboard-text', 'data-copy', 'data-value']) {
      const v = el.getAttribute(attr);
      if (v) out.push(v);
    }
  }
  if (document.body) out.push(document.body.innerText || '');
  return out;
}"""

# Tempel clipboard ke textarea sendiri, untuk browser yang menolak
# navigator.clipboard.readText(). Elemen harus benar-benar ter-render supaya bisa
# menerima fokus dan event paste, jadi dipakai opacity kecil, bukan display:none.
_PASTE_JS = """() => {
  let el = document.getElementById('__bansos_paste');
  if (!el) {
    el = document.createElement('textarea');
    el.id = '__bansos_paste';
    el.style.cssText =
      'position:fixed;left:0;bottom:0;width:140px;height:28px;opacity:0.01;z-index:2147483647';
    document.body.appendChild(el);
  }
  el.value = '';
  el.focus();
}"""

_READ_PASTE_JS = """() => {
  const el = document.getElementById('__bansos_paste');
  const value = el ? el.value : '';
  if (el) el.remove();
  return value;
}"""


def pick_key(candidates: list[str]) -> str | None:
    """Kandidat terpanjang yang cocok pola key, cukup panjang, dan tidak bertopeng.

    Tiga hal yang membuat sebuah nilai ditolak:

    - **Terlalu pendek.** Halaman daftar key menampilkan versi terpotong
      (`sk-AbCd1234EfG...`) yang tetap cocok polanya.
    - **Bertopeng.** UI menyembunyikan tengah key dengan bullet atau asterisk
      (`sk-abc••••••••xyz`, `sk-abc********xyz`) dan jumlah karakter topengnya
      tidak tetap. Yang diperiksa adalah karakter tepat sebelum dan sesudah
      match — karakter topeng bukan alnum, jadi tidak pernah masuk ke match
      itu sendiri, dan panjang topengnya jadi tidak perlu diketahui.
    - **Diapit ellipsis.** `sk-abc...` dan `...xyz` sama-sama potongan tampilan.

    Ini yang membuat pembacaan lewat DOM aman dipakai sebagai jalur utama: nilai
    bertopeng tidak akan lolos hanya karena panjangnya cukup.
    """
    best = None
    for text in candidates:
        if not isinstance(text, str):
            continue
        for match in API_KEY_PATTERN.finditer(text):
            value = match.group(0)
            if len(value) < API_KEY_MIN_LENGTH or _is_truncated(text, match):
                continue
            if best is None or len(value) > len(best):
                best = value
    return best


def _is_truncated(text: str, match: re.Match[str]) -> bool:
    """True kalau match diapit penanda topeng/potongan."""
    before = text[max(0, match.start() - 3) : match.start()]
    after = text[match.end() : match.end() + 3]
    return any(
        mark in before or mark in after for mark in KEY_TRUNCATION_MARKS
    )


def accept_key(key: str | None, seen: set[str], source: str = "") -> str | None:
    """None kalau key kosong atau sudah pernah diambil di run ini.

    Key tiap situs dan tiap akun selalu berbeda — dua yang identik berarti
    pembacaannya salah, bukan situsnya kebetulan mengeluarkan key yang sama.
    Penyebab paling sering: clipboard OS masih memegang key sebelumnya karena
    tombol Copy tidak benar-benar menyalin. Menolaknya di sini mencegah satu key
    tersimpan dua kali dan menimpa connection lain di 9router.
    """
    if not key:
        return None
    if key in seen:
        print(f"⚠️  Key dari {source or 'halaman'} sama dengan yang sudah diambil — ditolak")
        return None
    return key


async def _dom_key(page) -> str | None:
    """Baca key langsung dari halaman — tanpa clipboard, tanpa izin, tanpa klik."""
    try:
        values = await page.evaluate(_SCRAPE_JS)
    except Exception as exc:
        print(f"⚠️  Gagal membaca DOM halaman keys: {exc}")
        return None
    return pick_key(values if isinstance(values, list) else [])


async def _poll_dom_key(page, seen: set[str], attempts: int = DOM_READ_ATTEMPTS) -> str | None:
    """Baca DOM beberapa kali — key sering baru dirender sesaat setelah Save."""
    for attempt in range(1, attempts + 1):
        key = accept_key(await _dom_key(page), seen, source="halaman")
        if key:
            return key
        if attempt < attempts:
            await asyncio.sleep(human_delay(0.8, 1.6))
    return None


async def _clipboard_via_api(page) -> str:
    try:
        return await page.evaluate("async () => await navigator.clipboard.readText()") or ""
    except Exception as exc:
        print(f"⚠️  navigator.clipboard.readText() ditolak: {exc}")
        return ""


async def _clipboard_via_paste(page) -> str:
    """Ctrl+V ke textarea sendiri — jalan walau readText() diblokir."""
    try:
        await page.evaluate(_PASTE_JS)
        await asyncio.sleep(0.2)
        await page.keyboard.press("Control+V")
        await asyncio.sleep(0.4)
        return await page.evaluate(_READ_PASTE_JS) or ""
    except Exception as exc:
        print(f"⚠️  Paste clipboard gagal: {exc}")
        try:
            await page.evaluate(_READ_PASTE_JS)
        except Exception:
            pass
        return ""


async def _clear_clipboard(page) -> None:
    """Kosongkan clipboard sebelum klik Copy.

    Tanpa ini, klik Copy yang gagal tanpa error meninggalkan isi clipboard lama,
    dan key akun sebelumnya terbaca sebagai key akun ini. `accept_key` juga
    menolaknya, tapi mengosongkan lebih dulu membuat kegagalannya terbaca sebagai
    "clipboard kosong", bukan "key duplikat".
    """
    try:
        await page.evaluate("async () => await navigator.clipboard.writeText('')")
    except Exception:
        pass


async def _clipboard_key(page, seen: set[str], click: bool = True) -> str | None:
    """Fallback: klik Copy lalu baca clipboard. readText() dulu, paste cadangan.

    Clipboard adalah sumber paling rapuh di alur ini — satu proses OS, dipakai
    bersama semua browser, dan kliknya bisa "berhasil" tanpa menyalin apa pun.
    """
    if click:
        await _clear_clipboard(page)
        if not await click_first_visible(
            page, SITE["copy_key"], label="Copy key", optional=True
        ):
            return None
    await asyncio.sleep(human_delay(0.4, 0.9))
    for read in (_clipboard_via_api, _clipboard_via_paste):
        key = accept_key(pick_key([await read(page)]), seen, source="clipboard")
        if key:
            return key
    return None


async def capture_key(page, seen: set[str]) -> str | None:
    """Baca DOM (utama) → tombol Copy + clipboard (fallback) → DOM sekali lagi.

    DOM jadi sumber utama karena key baru ditampilkan utuh di halaman: tidak butuh
    izin clipboard maupun klik yang bisa gagal diam-diam, dan tidak terpengaruh
    keadaan clipboard OS yang dipakai bersama. Tombol Copy hanya dipakai kalau DOM
    benar-benar tidak menghasilkan apa pun.
    """
    key = await _poll_dom_key(page, seen)
    if key:
        print("✓ Key terbaca dari halaman")
        return key

    print("→ Key tidak ada di halaman — fallback ke tombol Copy + clipboard...")
    key = await _clipboard_key(page, seen)
    if key:
        print("✓ Key terbaca dari clipboard")
        return key

    # Sebagian situs baru mengisi field-nya setelah tombol Copy diklik.
    return accept_key(await _dom_key(page), seen, source="halaman")


async def _create_and_capture(page, site: Site, key_name: str, seen: set[str]) -> str | None:
    if not await _create_key(page, site, key_name):
        return None
    return await capture_key(page, seen)

async def _ask_key_manually(page, site: Site, seen: set[str]) -> str | None:
    """Jalur terakhir: user yang klik Copy, atau menempel key-nya sendiri.

    Mode auto tidak melewati sini — `retry_after_refresh` sudah melempar
    StepSkipped sebelum sampai ke pertanyaan apa pun.
    """
    await ask("   Tekan Enter setelah klik tombol Copy di browser: ")
    key = await _clipboard_key(page, seen, click=False) or await _poll_dom_key(page, seen, 1)
    if key:
        return key

    typed = (await ask(f"   Tempel API key {site.name} di sini: ")).strip()
    if not typed:
        return None
    if not pick_key([typed]):
        print("⚠️  Yang ditempel tidak berbentuk API key utuh — tetap dipakai")
    if typed in seen:
        print("⚠️  Key itu sudah dipakai untuk situs lain di run ini — dibatalkan")
        return None
    return typed

async def collect_key(
    page, site: Site, account: GithubAccount, seen: set[str]
) -> str | None:
    """Sign-up via GitHub → buat API key → ambil key. None kalau gagal.

    Tiap langkah lewat `retry_after_refresh`: gagal → hard refresh (maks 2x) →
    baru tanya user, atau langsung skip di mode auto. Langkah yang dilewati keluar
    sebagai StepSkipped dan ditangani `runner`, supaya situs berikutnya tetap
    dikerjakan.

    `seen` berisi key yang sudah diambil sepanjang run; key yang muncul dua kali
    berarti pembacaannya salah — lihat `accept_key`.
    """
    print(f"\n{'─' * 60}")
    print(f"SITE: {site.name} ({site.host})")
    print(f"{'─' * 60}")

    async def _open() -> bool:
        await goto(page, site.signup_url)
        return await wait_for_url_contains(page, site.host, timeout=30)

    await retry_after_refresh(page, f"buka halaman {site.name}", _open)
    await asyncio.sleep(human_delay(1.5, 3.0))

    await retry_after_refresh(
        page, f"OAuth {site.name}", lambda: _oauth_flow(page, site, account)
    )

    # Gagal → hard refresh → buat key baru sekali lagi. Key yang tampil sekali lalu
    # hilang tidak bisa dibaca ulang, jadi pemulihannya membuat key baru, bukan
    # mencari yang lama.
    key = await retry_after_refresh(
        page,
        f"API key {site.name}",
        lambda: _create_and_capture(page, site, account.username, seen),
    )
    if key is MANUAL:
        key = await capture_key(page, seen)
    if not key and not is_auto():
        key = await _ask_key_manually(page, site, seen)

    if not key:
        print(f"✗ API key {site.name} kosong")
        return None

    seen.add(key)
    print(f"✓ API key {site.name}: {key}")
    return key
