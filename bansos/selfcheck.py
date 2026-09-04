"""Self-check tanpa framework: `python -m bansos.selfcheck`.

Yang dites hanya logika murni dan client HTTP (lewat MockTransport). Alur browser
tidak bisa dites otomatis — itu diverifikasi manual dengan satu akun.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import tempfile
from pathlib import Path

import httpx

from . import page as page_mod
from . import prompt
from .bootstrap import use_utf8_stdout
from .browser import (
    AVAIL_HEIGHT,
    MODES,
    SCREEN_CONFIG,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    VIRTUAL_SUPPORTED,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    _launch_kwargs,
    available_modes,
    build_proxy,
    mode_label,
    new_session_id,
    proxy_username,
)
from .config import HARD_REFRESH_ATTEMPTS, RunOptions, Settings, Site
from .errors import StepSkipped
from .github import username_from_local_part
from .mail.base import extract_code, plain_text, random_local_part
from .mail.mailtm import MailTmMail, _epoch
from .mail.worker import WorkerMail
from .ninerouter import NineRouter
from .prompt import MANUAL
from .sites import accept_key, pick_key
from .storage import append_account, begin_run

TABI_NODE = "openai-compatible-chat-1e0cda01-0d1e-4272-9bd8-8f16200efc00"


def _config(**overrides) -> Settings:
    base = {
        "github_password": "pw",
        "mail_provider": "worker",
        "mail_worker_url": "https://worker.test",
        "mail_worker_password": "app-pw",
        "mailtm_base_url": "https://api.mail.tm",
        "ninerouter_url": "http://192.168.0.105:20127",
        "ninerouter_password": "secret",
        "proxy_enabled": True,
        "proxy_host": "gw.dataimpulse.com:823",
        "proxy_user": "user",
        "proxy_pass": "pass",
        "proxy_country": "",
        "sites": (Site("Tabitoken", "tabitoken.com", "https://tabitoken.com/sign-up", TABI_NODE, "m"),),
    }
    return Settings(**{**base, **overrides})


def check_proxy() -> None:
    """Bug intinya: syntax parameter DataImpulse harus `user__key.value;key.value`."""
    assert proxy_username("user", "acc1") == "user__sessid.acc1"
    assert proxy_username("user", "acc1", "id") == "user__cr.id;sessid.acc1"

    session = new_session_id()
    assert session.isalnum(), session  # '.' dan ';' adalah pemisah parameter

    proxy = build_proxy(_config(), "acc1")
    assert proxy == {
        "server": "http://gw.dataimpulse.com:823",
        "username": "user__sessid.acc1",
        "password": "pass",
    }, proxy
    assert build_proxy(_config(proxy_enabled=False), "acc1") is None
    assert build_proxy(_config(proxy_user=""), "acc1") is None


def check_browser_geometry() -> None:
    """Jendela harus 1366x720 dan geometrinya tidak boleh mustahil.

    Camoufox mengarang ukuran layar per-launch dan `Screen(...)` hanya batas
    pengacakan, bukan nilai pasti — jadi geometri ditulis langsung ke `config`.
    """
    assert (WINDOW_WIDTH, WINDOW_HEIGHT) == (1366, 720)
    assert SCREEN_CONFIG["window.outerWidth"] == WINDOW_WIDTH
    assert SCREEN_CONFIG["window.outerHeight"] == WINDOW_HEIGHT

    # inner <= outer <= avail <= screen; jendela lebih besar dari layar = bot.
    assert AVAIL_HEIGHT <= SCREEN_HEIGHT
    assert WINDOW_WIDTH <= SCREEN_CONFIG["screen.availWidth"] <= SCREEN_WIDTH
    assert WINDOW_HEIGHT <= AVAIL_HEIGHT

    # screen.height == availHeight artinya tidak ada taskbar — penanda headless.
    assert SCREEN_CONFIG["screen.availHeight"] < SCREEN_CONFIG["screen.height"]

    # Jendela di tengah area yang tersedia, tidak menggantung di luar layar.
    assert SCREEN_CONFIG["window.screenX"] >= 0
    assert SCREEN_CONFIG["window.screenY"] >= 0
    assert SCREEN_CONFIG["window.screenX"] + WINDOW_WIDTH <= SCREEN_WIDTH
    assert SCREEN_CONFIG["window.screenY"] + WINDOW_HEIGHT <= AVAIL_HEIGHT

    kwargs = _launch_kwargs(None, headless=True)
    # uBlock Origin dipasang Camoufox secara default dan memblokir skrip
    # analytics yang dipakai situs target untuk captcha dan deteksi bot.
    assert [addon.name for addon in kwargs["exclude_addons"]] == ["UBO"]
    # Geometri eksplisit memicu peringatan; ini disengaja, jadi harus di-ack.
    assert kwargs["i_know_what_im_doing"] is True
    assert kwargs["config"]["window.outerWidth"] == WINDOW_WIDTH
    # dict(SCREEN_CONFIG): launch_options memodifikasi config yang diberikan.
    assert kwargs["config"] is not SCREEN_CONFIG
    # Layar 1366x768 adalah resolusi Windows; OS tidak diacak agar tetap wajar.
    assert kwargs["os"] == "windows"
    assert "proxy" not in kwargs and "geoip" not in kwargs

    with_proxy = _launch_kwargs({"server": "http://x"}, headless=False)
    assert with_proxy["geoip"] is True

    # navigator.clipboard.readText() ditolak Firefox tanpa dua pref ini, dan itu
    # satu-satunya cara mengambil API key yang hanya ada di clipboard.
    prefs = kwargs["firefox_user_prefs"]
    assert prefs["dom.events.asyncClipboard.readText"] is True
    assert prefs["dom.events.testing.asyncClipboard"] is True

def check_browser_modes() -> None:
    """Mode CLI diteruskan apa adanya ke argumen `headless` Camoufox."""
    values = [value for _, value in MODES.values()]
    assert values == [False, "virtual", True], values
    assert _launch_kwargs(None, headless="virtual")["headless"] == "virtual"
    assert mode_label("virtual").startswith("virtual display")

    # Xvfb hanya ada di Linux; di OS lain pilihannya tidak boleh ditawarkan sama
    # sekali, karena Camoufox melempar VirtualDisplayNotSupported saat launch.
    offered = [value for _, value in available_modes().values()]
    assert ("virtual" in offered) is VIRTUAL_SUPPORTED, offered
    assert False in offered and True in offered

def check_key_extraction() -> None:
    """Key utuh diambil; versi terpotong dan bertopeng ditolak."""
    full = "sk-" + "AbCd1234EfGh5678IjKl9012MnOp3456QrSt7890UvWx"
    assert len(full) == 47, len(full)

    assert pick_key([full]) == full
    assert pick_key([f"Your key: {full} — copy it now"]) == full
    # Daftar key menampilkan versi terpotong; itu bukan key yang bisa dipakai.
    assert pick_key(["sk-AbCd1234EfG...", "sk-abc"]) is None
    # Yang terpanjang menang: potongan dan key utuh bisa ada di halaman yang sama.
    assert pick_key(["sk-AbCd1234EfG...", full]) == full
    assert pick_key([]) is None
    assert pick_key([None, 123]) is None  # type: ignore[list-item]


def check_masked_key_rejected() -> None:
    """Nilai bertopeng dari DOM tidak boleh lolos hanya karena panjangnya cukup.

    UI menyembunyikan tengah key dengan bullet/asterisk dan jumlah karakter
    topengnya berubah-ubah, jadi yang diperiksa adalah tetangga langsung match,
    bukan panjang topengnya.
    """
    head = "sk-" + "A" * 44          # cukup panjang untuk lolos ambang
    tail = "B" * 44
    real = "sk-" + "C" * 48

    for mask in ("*", "****", "*" * 12, "•", "••••••", "●●●", "…", "..."):
        masked = f"{head}{mask}{tail}"
        assert pick_key([masked]) is None, (mask, pick_key([masked]))

    # Topeng di depan juga potongan tampilan, bukan key.
    assert pick_key([f"****{head}"]) is None
    assert pick_key([f"{head}…"]) is None

    # Key sungguhan di halaman yang sama tetap terambil walau ada baris bertopeng.
    page_text = f"Existing: {head}********{tail}\nNew key: {real}\n"
    assert pick_key([page_text]) == real

    # Pemisah biasa bukan topeng: key di dalam JSON/kutip harus tetap terbaca.
    assert pick_key([f'{{"apiKey":"{real}"}}']) == real
    assert pick_key([f"key = {real};"]) == real


def check_key_uniqueness() -> None:
    """Key yang sama untuk dua situs = pembacaan salah, bukan kebetulan.

    Penyebab paling sering: clipboard OS masih memegang key situs sebelumnya
    karena tombol Copy tidak benar-benar menyalin. Tanpa penolakan ini, satu key
    tersimpan dua kali dan connection kedua di 9router menimpa yang pertama.
    """
    tabi = "sk-" + "T" * 44
    seek = "sk-" + "S" * 44
    seen: set[str] = set()

    # Situs pertama (Tabitoken) diterima dan dicatat.
    assert accept_key(tabi, seen) == tabi
    seen.add(tabi)

    # Situs kedua membaca nilai yang sama → ditolak, yang pertama tetap dipegang.
    assert accept_key(tabi, seen) is None
    assert accept_key(seek, seen) == seek

    assert accept_key(None, seen) is None
    assert accept_key("", seen) is None


# ═══ Eskalasi: gagal → hard refresh → coba lagi → baru tanya user ═════════════


class _FakeLocator:
    """Selalu 'tidak ketemu' — cukup untuk melewati find_visible dan has_text."""

    @property
    def first(self):
        return self

    async def count(self) -> int:
        return 0

    async def is_visible(self) -> bool:
        return False

    async def scroll_into_view_if_needed(self, **_) -> None:
        return None


class _FakePage:
    """Page minimal: mencatat berapa kali halaman dimuat ulang."""

    frames: list = []

    def __init__(self, url: str = "https://example.test/keys"):
        self.url = url
        self.reloads = 0

    def locator(self, _selector):
        return _FakeLocator()

    async def reload(self, **_) -> None:
        self.reloads += 1

    async def goto(self, url: str, **_) -> None:
        self.url = url

    async def wait_for_load_state(self, **_) -> None:
        return None

    async def set_extra_http_headers(self, _headers) -> None:
        return None


async def check_retry_escalation() -> None:
    """Urutan eskalasi: coba → hard refresh (maks 2x) → baru tanya user."""
    answers: list = []

    async def _fake_ask_retry(_label):
        return answers.pop(0)

    original_ask_retry, original_delay = page_mod.ask_retry, page_mod.human_delay
    page_mod.ask_retry = _fake_ask_retry
    page_mod.human_delay = lambda *_args, **_kw: 0.0
    try:
        await _run_escalation_cases(answers)
    finally:
        page_mod.ask_retry, page_mod.human_delay = original_ask_retry, original_delay


def _fails(times: int):
    """Action yang gagal `times` kali lalu berhasil. Mengembalikan (action, calls)."""
    calls = {"n": 0}

    async def action():
        calls["n"] += 1
        return calls["n"] > times

    return action, calls


async def _run_escalation_cases(answers: list) -> None:
    retry = page_mod.retry_after_refresh
    budget = HARD_REFRESH_ATTEMPTS

    # Sukses langsung: halaman tidak boleh dimuat ulang sama sekali.
    page = _FakePage()
    action, calls = _fails(0)
    assert await retry(page, "step", action) is True
    assert (page.reloads, calls["n"]) == (0, 1)

    # Gagal sekali: satu hard refresh cukup, user tidak diganggu.
    page = _FakePage()
    action, calls = _fails(1)
    assert await retry(page, "step", action) is True
    assert (page.reloads, calls["n"]) == (1, 2)

    # Gagal dua kali: refresh kedua masih dalam jatah, tetap tanpa prompt.
    page = _FakePage()
    action, calls = _fails(2)
    assert await retry(page, "step", action) is True
    assert (page.reloads, calls["n"]) == (2, 3)

    # Selalu gagal: jatah refresh habis, baru sampai ke user; 's' menghentikannya.
    page = _FakePage()
    action, calls = _fails(99)
    answers.append(False)
    try:
        await retry(page, "step", action)
    except StepSkipped:
        pass
    else:
        raise AssertionError("pilihan skip harus melempar StepSkipped")
    assert (page.reloads, calls["n"]) == (budget, budget + 1)

    # 'm' = user sudah kerjakan sendiri → MANUAL, bukan kegagalan.
    page = _FakePage()
    action, _ = _fails(99)
    answers.append(MANUAL)
    assert await retry(page, "step", action) is MANUAL

    # refresh=False untuk langkah yang kehilangan data kalau halaman dimuat ulang.
    page = _FakePage()
    action, calls = _fails(99)
    answers.append(False)
    try:
        await retry(page, "step", action, refresh=False)
    except StepSkipped:
        pass
    assert (page.reloads, calls["n"]) == (0, 1)


async def check_auto_mode_skips() -> None:
    """Mode auto tidak boleh menunggu input: langkah yang mentok langsung skip."""
    page = _FakePage()
    action, calls = _fails(99)
    original_delay, page_mod.human_delay = page_mod.human_delay, lambda *_a, **_k: 0.0
    prompt.set_auto(True)
    try:
        await page_mod.retry_after_refresh(page, "step", action)
    except StepSkipped:
        pass
    else:
        raise AssertionError("mode auto harus melempar StepSkipped tanpa bertanya")
    finally:
        prompt.set_auto(False)
        page_mod.human_delay = original_delay

    # Jatah hard refresh tetap dipakai penuh — auto bukan berarti menyerah cepat.
    assert (page.reloads, calls["n"]) == (HARD_REFRESH_ATTEMPTS, HARD_REFRESH_ATTEMPTS + 1)
    assert prompt.is_auto() is False


def check_mail_parsing() -> None:
    # Worker: text_content / html_content sebagai string.
    assert extract_code(None, "your code is 12345678") == "12345678"
    assert extract_code(None, None, "<b>87654321</b>") == "87654321"
    # mail.tm: html sebagai list of string.
    assert extract_code(None, None, ["<p>1234", "5678</p>"]) is None
    assert extract_code(None, None, ["<b>87654321</b>"]) == "87654321"
    assert extract_code("Kode 24681357", None) == "24681357"
    # Angka panjang bukan OTP.
    assert extract_code(None, "invoice 123456789012") is None
    assert extract_code(None, None) is None

    assert plain_text(None, "<p>hi</p>  <p>there</p>") == "hi there"
    assert plain_text(None, ["<p>hi</p>", "<p>there</p>"]) == "hi there"
    assert random_local_part()[0].isalpha()

    assert _epoch("2022-04-01T00:00:00.000Z") == 1648771200.0
    assert _epoch(None) == 0.0
    assert _epoch("bukan tanggal") == 0.0


def check_username() -> None:
    assert username_from_local_part("Ab3-c_d") == "ab3cd"
    assert username_from_local_part("k9xyz") == "k9xyz"


def check_storage() -> None:
    """Header run + satu baris per akun, key diberi label nama situs."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "akun.txt"
        begin_run(2, ["Tabitoken", "SeekAI"], "akun.txt + 9router", path=path)
        append_account("a@b.c", "pw", "user1", [("Tabitoken", "k1"), ("SeekAI", "k2")], path=path)
        # Run yang hanya memilih satu situs: labelnya yang memberi tahu situs mana.
        append_account("d@e.f", "pw", "user2", [("SeekAI", "k3")], path=path)
        # Key manual dari user bisa membawa '|' atau newline yang menggeser field.
        append_account("g@h.i", "pw", "user3", [("Tabitoken", "sk-a|b\n")], path=path)
        lines = path.read_text(encoding="utf-8").splitlines()

    assert lines[0] == "", lines[0]
    assert lines[1].startswith("# ====="), lines[1]
    assert "RUN " in lines[2] and "2 akun" in lines[2], lines[2]
    assert "situs: Tabitoken, SeekAI" in lines[2], lines[2]
    assert "simpan: akun.txt + 9router" in lines[2], lines[2]
    assert lines[4:] == [
        "a@b.c|pw|user1|Tabitoken=k1|SeekAI=k2",
        "d@e.f|pw|user2|SeekAI=k3",
        "g@h.i|pw|user3|Tabitoken=sk-ab",
    ], lines[4:]

    # Baris header diawali '#' supaya parser bisa melewatinya dengan satu cek.
    accounts = [line for line in lines if line and not line.startswith("#")]
    assert len(accounts) == 3, accounts


def check_run_options() -> None:
    """Label tujuan simpan ikut ditulis di header run, jadi harus tepat."""
    assert RunOptions().targets == "akun.txt + 9router"
    assert RunOptions(push_router=False).targets == "akun.txt"
    assert RunOptions(save_file=False).targets == "9router"
    assert RunOptions(save_file=False, push_router=False).targets == "tidak disimpan"

    # Proxy dipilih per run; defaultnya tidak dipakai kalau tidak diminta.
    assert RunOptions().use_proxy is False
    assert RunOptions(use_proxy=True).use_proxy is True

    # seen_keys tidak boleh dibagi antar instance — itu state per run.
    first, second = RunOptions(), RunOptions()
    first.seen_keys.add("sk-x")
    assert second.seen_keys == set()


def check_proxy_override() -> None:
    """Pilihan proxy di CLI diterapkan lewat salinan Settings, bukan global.

    `build_proxy` membaca `proxy_enabled`, jadi mematikan proxy untuk satu run
    cukup dengan mengganti field itu — tidak ada jalur lain yang perlu tahu.
    """
    enabled = _config(proxy_enabled=True)
    assert build_proxy(enabled, "acc1") is not None

    disabled = dataclasses.replace(enabled, proxy_enabled=False)
    assert build_proxy(disabled, "acc1") is None
    # Settings aslinya tidak ikut berubah.
    assert build_proxy(enabled, "acc1") is not None


# ═══ Client HTTP (tanpa jaringan nyata) ═══════════════════════════════════════

def _mailtm_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/domains":
        return httpx.Response(200, json={"hydra:member": [
            {"domain": "nonaktif.test", "isActive": False},
            {"domain": "aktif.test", "isActive": True},
        ]})
    if path == "/accounts":
        return httpx.Response(201, json={"id": "acc", "address": json.loads(request.content)["address"]})
    if path == "/token":
        return httpx.Response(200, json={"id": "acc", "token": "tok123"})
    if path == "/messages":
        assert request.headers["Authorization"] == "Bearer tok123"
        return httpx.Response(200, json={"hydra:member": [
            {"id": "old", "createdAt": "2020-01-01T00:00:00.000Z"},
            {"id": "new", "createdAt": "2030-01-01T00:00:00.000Z"},
        ]})
    if path == "/messages/new":
        return httpx.Response(200, json={"subject": "Verify", "text": None, "html": ["<b>13572468</b>"]})
    if path == "/messages/old":
        raise AssertionError("email lama seharusnya disaring oleh `after`")
    raise AssertionError(f"path tak terduga: {path}")


async def check_mailtm_client() -> None:
    mail = MailTmMail("https://api.mail.tm", transport=httpx.MockTransport(_mailtm_handler))
    address = await mail.new_address()
    assert address.endswith("@aktif.test"), address
    code = await mail.wait_for_code(address, after=_epoch("2025-01-01T00:00:00.000Z"))
    assert code == "13572468", code
    await mail.aclose()


def _worker_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    assert request.headers.get("Authorization") == "Bearer app-pw", request.headers
    if path == "/domains":
        # API pernah mengirim string, sekarang object — keduanya harus jalan.
        return httpx.Response(200, json={"success": True, "result": ["a.test", {"domain": "b.test"}]})
    if path.startswith("/emails/"):
        return httpx.Response(200, json={"success": True, "result": [
            {"id": "old", "received_at": 1000},
            {"id": "new", "received_at": 9999999999},
        ]})
    if path == "/inbox/new":
        return httpx.Response(200, json={"success": True, "result": {
            "subject": "GitHub", "text_content": None, "html_content": "<b>97531864</b>",
        }})
    if path == "/inbox/old":
        raise AssertionError("email lama seharusnya disaring oleh `after`")
    raise AssertionError(f"path tak terduga: {path}")


async def check_worker_client() -> None:
    mail = WorkerMail(
        "https://worker.test", "app-pw", transport=httpx.MockTransport(_worker_handler)
    )
    address = await mail.new_address()
    assert address.split("@")[1] in ("a.test", "b.test"), address
    assert await mail.wait_for_code(address, after=5000) == "97531864"
    await mail.aclose()


async def check_worker_auth_errors() -> None:
    """401/503 harus jadi pesan yang bisa ditindaklanjuti, bukan HTTPStatusError."""
    for status, fragment in ((401, "password salah"), (503, "APP_PASSWORD")):
        mail = WorkerMail(
            "https://worker.test",
            "salah",
            transport=httpx.MockTransport(lambda _, s=status: httpx.Response(s)),
        )
        try:
            await mail.new_address()
        except RuntimeError as exc:
            assert fragment in str(exc), exc
        else:
            raise AssertionError(f"status {status} seharusnya melempar RuntimeError")
        await mail.aclose()


def _router_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/api/auth/login":
        assert json.loads(request.content) == {"password": "secret"}
        # Login nyata mengembalikan 200 tanpa body, autentikasi lewat cookie.
        return httpx.Response(
            200, headers={"set-cookie": "auth_token=jwt; Path=/; HttpOnly; SameSite=lax"}
        )
    if path == "/api/provider-nodes":
        return httpx.Response(200, json={"nodes": [{"id": TABI_NODE, "name": "TabiAI"}]})
    if path == "/api/providers/validate":
        return httpx.Response(200, json={"valid": True})
    if path == "/api/providers" and request.method == "POST":
        body = json.loads(request.content)
        assert body == {
            "provider": TABI_NODE,
            "name": "user1-tabitoken",
            "apiKey": "sk-abc",
            "defaultModel": "m",
            "priority": 1,
            "proxyPoolId": None,
            "testStatus": "active",
        }, body
        assert request.headers.get("cookie") == "auth_token=jwt"
        return httpx.Response(201, json={"connection": {"id": "conn1", "isActive": True}})
    if path == "/api/providers":
        return httpx.Response(200, json={"connections": [{"name": "user0-seekai"}]})
    raise AssertionError(f"path tak terduga: {path}")


async def check_router_client() -> None:
    router = NineRouter(_config(), transport=httpx.MockTransport(_router_handler))
    assert await router.login() is True
    assert await router.node_ids() == {TABI_NODE}
    await router.load_existing_names()
    assert await router.push_key(TABI_NODE, "user1-tabitoken", "sk-abc", "m") is True
    # Nama kedua bertabrakan dengan yang sudah tersimpan → harus di-suffix,
    # karena POST dengan nama sama menimpa connection lama.
    assert router._unique_name("user0-seekai") == "user0-seekai-2"
    assert router._unique_name("user1-tabitoken") == "user1-tabitoken-2"
    await router.aclose()


async def check_router_login_without_cookie() -> None:
    """200 tanpa cookie bukan sukses — request berikutnya pasti 401."""
    router = NineRouter(
        _config(), transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    assert await router.login() is False
    await router.aclose()


async def main() -> None:
    use_utf8_stdout()
    check_proxy()
    check_browser_geometry()
    check_browser_modes()
    check_key_extraction()
    check_masked_key_rejected()
    check_key_uniqueness()
    await check_retry_escalation()
    await check_auto_mode_skips()
    check_mail_parsing()
    check_username()
    check_storage()
    check_run_options()
    check_proxy_override()
    await check_mailtm_client()
    await check_worker_client()
    await check_worker_auth_errors()
    await check_router_client()
    await check_router_login_without_cookie()
    print("bansos selfcheck OK")


if __name__ == "__main__":
    asyncio.run(main())
