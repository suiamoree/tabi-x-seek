"""Alur GitHub: buka signup, lolos captcha, isi form, OTP, login."""

from __future__ import annotations

import asyncio
import time

from .captcha import handle_slider
from .errors import EmailRejected
from .human import human_delay, warmup
from .mail import MailProvider
from .page import (
    click_first_visible,
    fill_input,
    find_visible,
    goto,
    has_any_text,
    nudge_field,
    raise_if_bot_blocked,
    reload,
    retry_after_refresh,
    settle,
)
from .selectors import (
    EMAIL_REJECTED_TEXTS,
    GITHUB_HOME,
    GITHUB_LOGIN,
    GITHUB_SIGNUP,
    OTP_INPUTS,
)


def username_from_local_part(local_part: str) -> str:
    """GitHub hanya menerima alnum + dash; local part temp-mail sudah alnum."""
    return "".join(c for c in local_part.lower() if c.isalnum())


# ═══ Buka halaman signup ══════════════════════════════════════════════════════

async def _on_signup_page(page, budget: float = 8.0) -> bool:
    """Sudah di form signup?

    URL tidak dipakai sebagai bukti: `/signup?ref_cta=...` bisa terbuka tanpa
    form ter-render, dan homepage logged-out juga punya field email di hero CTA
    sehingga `email_input` pun bisa false positive. Yang unik milik form signup
    adalah field username (`input#login`).
    """
    return await find_visible(page, GITHUB_SIGNUP["username_input"], budget) is not None


async def _wait_signup_form(page, timeout: float = 15.0) -> bool:
    """Budget per-poll dibuat pendek supaya loop benar-benar mengulang."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await _on_signup_page(page, budget=2.0):
            return True
        await asyncio.sleep(0.5)
    return False


async def open_signup(page, escalate: bool = True) -> bool:
    """Masuk halaman signup lewat homepage, bukan deep-link.

    Jalurnya penting, bukan cuma tujuannya. `goto` langsung ke `/signup` ditolak
    DataDome dengan HTTP 403 dan halaman blokir di iframe `captcha-delivery.com`,
    walau memakai fingerprint yang sama dan walau referer diisi manual — terbukti
    di probe: goto telanjang 403 + iframe blokir, goto dengan referer 403,
    sedangkan klik dari homepage 200 dengan form ter-render.

    Yang membedakan bukan header, tapi jejak navigasinya: klik dari homepage
    membawa sinyal in-page (event pointer, history entry, token yang ditanam
    halaman) yang tidak bisa ditiru oleh navigasi top-level.

    `escalate=False` saat dipanggil dari dalam langkah lain yang sudah punya
    eskalasinya sendiri, supaya user tidak ditanya dua kali bertingkat.
    """

    async def _attempt() -> bool:
        print("→ Buka github.com dulu (deep-link ke /signup diblokir)...")
        if not await goto(page, GITHUB_HOME):
            return False
        await raise_if_bot_blocked(page)
        await warmup(page)

        link = await find_visible(page, GITHUB_SIGNUP["signup_link"])
        if link is None:
            print("⚠️  Link Sign up tidak ketemu di homepage")
            return False

        print("→ Klik link Sign up dari homepage...")
        try:
            await link.click(timeout=5000)
        except Exception as exc:
            print(f"⚠️  Klik Sign up gagal: {exc}")
            return False
        await settle(page)
        await raise_if_bot_blocked(page)

        if await _wait_signup_form(page):
            print(f"✓ Form signup siap: {page.url}")
            return True

        # Sampai di /signup tapi form tidak pernah render → reload sekali; SPA
        # GitHub kadang gagal mount saat navigasi dari homepage. Reload aman di
        # sini karena URL-nya sudah punya jejak navigasi yang diterima.
        print(f"⚠️  Form signup belum render (url={page.url})")
        if "signup" in page.url.lower():
            print("→ Reload halaman signup...")
            await reload(page)
            await raise_if_bot_blocked(page)
            if await _wait_signup_form(page):
                print(f"✓ Form signup siap setelah reload: {page.url}")
                return True
        return False

    if not escalate:
        return await _attempt()
    return bool(await retry_after_refresh(page, "buka halaman signup GitHub", _attempt))


# ═══ Submit form ══════════════════════════════════════════════════════════════

async def _submitted(page) -> bool:
    """Form dianggap tembus kalau kotak OTP sudah muncul."""
    if await find_visible(page, OTP_INPUTS) is not None:
        return True
    url = page.url.lower()
    return "email-verification" in url or "launch_code" in url


async def _nudge_all(page, email: str, username: str, password: str) -> None:
    """Validasi GitHub jalan per-field, bukan global, jadi ketiganya di-nudge."""
    for label, selectors, value in (
        ("email", GITHUB_SIGNUP["email_input"], email),
        ("password", GITHUB_SIGNUP["password_input"], password),
        ("username", GITHUB_SIGNUP["username_input"], username),
    ):
        await nudge_field(page, selectors, value, label=label)
        await asyncio.sleep(human_delay(0.3, 0.7))


async def _submit_form(page, email: str, username: str, password: str, attempts: int = 4) -> bool:
    """Klik Create account sampai kotak OTP muncul.

    Kliknya dua kali per attempt: klik pertama sering hanya memicu validasi atau
    memindahkan fokus (GitHub baru meng-enable tombol setelah event input
    terakhir diproses), jadi klik kedua yang men-submit. Klik kedua di-skip kalau
    OTP sudah muncul supaya form tidak disubmit dua kali.

    `escalate=False` di tiap klik: eskalasi (hard refresh + tanya user) diurus
    `_fill_and_submit` di lapisan luar, yang mengisi ulang form setelah refresh.
    """
    for attempt in range(1, attempts + 1):
        print(f"→ Klik Create account ({attempt}/{attempts})...")
        clicked = False
        for press in (1, 2):
            if not await click_first_visible(
                page,
                GITHUB_SIGNUP["submit_button"],
                label="Create account",
                optional=(press == 2),
                escalate=False,
            ):
                break
            clicked = True
            await asyncio.sleep(human_delay(1.2, 2.0))
            if await _submitted(page):
                break
            if press == 1:
                print("   klik ke-2 (tombol baru enable setelah validasi)...")

        if not clicked:
            return False

        await asyncio.sleep(human_delay(1.0, 2.0))
        await raise_if_bot_blocked(page)
        if await has_any_text(page, EMAIL_REJECTED_TEXTS):
            raise EmailRejected(email)

        # Captcha bisa muncul setelah submit, bukan sebelum.
        await handle_slider(page, appear_timeout=5.0)

        if await _submitted(page):
            print("✓ Form submitted")
            return True

        print("⚠️  Submit belum tembus, ketik ulang 1 char di tiap field...")
        await _nudge_all(page, email, username, password)
    return False


async def _fill_form(page, email: str, username: str, password: str) -> bool:
    for label, selectors, value in (
        ("email", GITHUB_SIGNUP["email_input"], email),
        ("password", GITHUB_SIGNUP["password_input"], password),
        ("username", GITHUB_SIGNUP["username_input"], username),
    ):
        print(f"→ Input {label}...")
        if not await fill_input(page, selectors, value, label=f"github signup {label}"):
            return False

    if await has_any_text(page, EMAIL_REJECTED_TEXTS):
        raise EmailRejected(email)
    return True


async def _fill_and_submit(page, email: str, username: str, password: str) -> bool:
    """Isi ketiga field lalu submit — satu kesatuan supaya bisa diulang utuh.

    Dipanggil ulang setelah hard refresh, dan refresh mengosongkan form serta bisa
    memunculkan captcha lagi, jadi keduanya ditangani di sini.
    """
    if await _submitted(page):
        return True
    if not await _on_signup_page(page, budget=3.0) and not await open_signup(
        page, escalate=False
    ):
        return False
    if not await handle_slider(page, appear_timeout=5.0):
        return False
    if not await _fill_form(page, email, username, password):
        return False
    return await _submit_form(page, email, username, password)


async def register(page, mail: MailProvider, password: str) -> tuple[str, str] | None:
    """Buka signup → lolos captcha → BARU generate email → isi form → submit.

    Email digenerate belakangan supaya alamat temp-mail tidak terbuang saat
    captcha atau blokir gagal dilewati.
    """
    if not await open_signup(page):
        return None
    await warmup(page, moves=2)

    if not await handle_slider(page):
        print("✗ Captcha belum lolos — email tidak digenerate")
        return None
    await raise_if_bot_blocked(page)

    email = await mail.new_address()
    username = username_from_local_part(email.split("@")[0])
    print(f"→ Email digenerate setelah captcha lolos: {email}")
    print(f"   Username: {username}")

    submitted = await retry_after_refresh(
        page,
        "submit form signup GitHub",
        lambda: _fill_and_submit(page, email, username, password),
    )
    return (email, username) if submitted else None


# ═══ OTP & login ══════════════════════════════════════════════════════════════

async def _fill_otp(page, code: str) -> bool:
    """Isi kotak launch code satu per satu. GitHub submit sendiri di digit terakhir.

    Semua digit harus kebagian kotak: kalau kotaknya belum ter-render, sebagian
    terisi dan form tidak pernah tersubmit — itu dilaporkan gagal, bukan sukses.
    """
    filled = 0
    for i, digit in enumerate(code):
        try:
            field = page.locator(f"#launch-code-{i}")
            if await field.count() == 0:
                break
            await field.fill(digit)
            filled += 1
            await asyncio.sleep(0.1)
        except Exception as exc:
            print(f"⚠️  Gagal mengisi digit OTP ke-{i}: {exc}")
            return False
    if filled < len(code):
        print(f"⚠️  Hanya {filled}/{len(code)} kotak OTP yang ter-render")
        return False
    return True


async def submit_otp(page, mail: MailProvider, address: str, sent_after: float) -> bool:
    """Ambil launch code dari inbox, isi kotak OTP.

    Kode tetap valid setelah halaman dimuat ulang, jadi kegagalan mengisi aman
    diulang lewat `retry_after_refresh` tanpa meminta OTP baru.
    """
    print(f"→ Menunggu OTP di inbox {address}...")
    code = await mail.wait_for_code(address, after=sent_after)
    if not code:
        print("✗ OTP tidak masuk dalam batas waktu")
        return False

    print(f"→ OTP diterima: {code}")
    if not await retry_after_refresh(page, "isi kotak OTP", lambda: _fill_otp(page, code)):
        return False

    await asyncio.sleep(1)
    print("✓ OTP filled")
    return True


async def _do_login(page, username: str, password: str) -> bool:
    """Login kalau form-nya ada. Form yang hilang = sudah masuk, itu juga sukses."""
    await settle(page)
    if await find_visible(page, GITHUB_LOGIN["login_input"], budget=4.0) is None:
        print("✓ Sudah login (form login tidak ada)")
        return True

    print("→ Login GitHub...")
    if not await fill_input(
        page, GITHUB_LOGIN["login_input"], username, label="github login username"
    ):
        return False
    if not await fill_input(
        page, GITHUB_LOGIN["password_input"], password, label="github login password"
    ):
        return False
    if not await click_first_visible(
        page, GITHUB_LOGIN["submit_button"], label="Sign in", escalate=False
    ):
        return False

    await asyncio.sleep(3)
    # Form login yang masih terpampang = kredensial belum diterima.
    return await find_visible(page, GITHUB_LOGIN["login_input"], budget=4.0) is None


async def login(page, username: str, password: str) -> bool:
    if not await retry_after_refresh(
        page, "login GitHub", lambda: _do_login(page, username, password)
    ):
        return False
    print("✓ Logged in")
    return True
