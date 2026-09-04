"""Settings terpusat — semua nilai environment-specific dibaca dari .env.

Satu `Settings` dibuat sekali di `settings()` dan diteruskan lewat argumen;
tidak ada `os.getenv()` yang tersebar di modul lain.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
AKUN_FILE = BASE_DIR / "akun.txt"

# ── Batas waktu ───────────────────────────────────────────────────────────────
# 'networkidle' tidak dipakai sebagai kondisi goto: GitHub menjaga koneksi
# analytics terbuka jadi tidak pernah idle, dan goto akan menggantung.
NAV_TIMEOUT = 30.0
SETTLE_TIMEOUT = 6.0

# Playwright di Firefox kadang tidak pernah menyelesaikan mouse.move/wheel dan
# is_visible() saat halaman masih sibuk. Tidak ada error yang dilempar, jadi
# try/except tidak menolong — hanya timeout eksplisit.
#
# 12s, bukan 8s: `humanize` Camoufox menghaluskan tiap mouse.move di level browser
# dan satu panggilan berbiaya ~0.2-0.8s, jadi warmup 3 gerakan + scroll butuh
# ruang lebih dari sekadar batas jaringan.
WARMUP_TIMEOUT = 12.0
LOCATOR_CALL_TIMEOUT = 3.0
FIND_BUDGET = 8.0

# Jumlah titik yang dikirim saat drag slider captcha. Sengaja kecil: Camoufox
# sudah menginterpolasi tiap gerakan, dan tiap panggilan mouse.move berbiaya
# ~0.2-0.8s — 50 langkah berarti drag setengah menit dan captcha kedaluwarsa.
DRAG_STEPS_MIN, DRAG_STEPS_MAX = 6, 10

# Challenge Cloudflare biasanya selesai sendiri di Camoufox selama IP stabil.
CF_CHALLENGE_TIMEOUT = 60.0
CF_POLL_INTERVAL = 2.0

# Berapa kali sebuah langkah diulang setelah hard refresh sebelum menyerah.
# Dua sudah cukup: kemacetan yang tidak sembuh setelah dua kali muat ulang bersih
# hampir selalu bukan soal render, jadi refresh ketiga hanya membuang waktu.
HARD_REFRESH_ATTEMPTS = 2

# Jeda setelah centang consent — form SeekAI butuh waktu enable tombol OAuth.
CONSENT_DELAY = 5.0
OAUTH_ATTEMPTS = 3

# Berapa kali halaman /keys dibaca untuk mencari nilai key sebelum jatuh ke
# clipboard. Key baru sering baru dirender sesaat setelah Save, dan membaca DOM
# beberapa kali jauh lebih murah daripada mengandalkan tombol Copy.
DOM_READ_ATTEMPTS = 3

OTP_TIMEOUT = 180.0
OTP_POLL_INTERVAL = 5.0

# Jeda setelah login GitHub, sebelum langkah berikutnya. Sesi yang baru dibuat
# butuh waktu sampai cookie-nya dipakai konsisten di seluruh alur; melanjutkan
# seketika membuat halaman OAuth berikutnya kadang masih melihat keadaan belum
# login dan menampilkan form login lagi.
POST_LOGIN_DELAY_MIN, POST_LOGIN_DELAY_MAX = 4.0, 6.0

HTTP_TIMEOUT = 20.0


@dataclass(frozen=True)
class Site:
    """Satu situs penyedia API key. Nambah situs = tambah satu entry."""

    name: str
    host: str
    signup_url: str
    provider_node_id: str
    model: str

    @property
    def keys_url(self) -> str:
        return f"https://{self.host}/keys"


@dataclass(frozen=True)
class GithubAccount:
    """Kredensial satu akun GitHub yang baru dibuat.

    Dibawa sampai ke alur per-situs karena dua hal di sana membutuhkannya: nama
    API key memakai username-nya, dan GitHub bisa meminta login lagi di tengah
    OAuth sehingga passwordnya harus tersedia di titik itu.
    """

    username: str
    password: str


@dataclass
class RunOptions:
    """Pilihan yang ditanyakan di CLI sebelum akun pertama dibuat.

    `seen_keys` dipakai bersama seluruh run, bukan per akun: tombol Copy menulis ke
    clipboard OS yang sama untuk semua browser, jadi satu klik yang gagal tanpa
    error bisa membuat key akun sebelumnya terbaca lagi sebagai key akun ini.
    """

    browser_mode: bool | str = False
    save_file: bool = True
    push_router: bool = True
    use_proxy: bool = False
    seen_keys: set[str] = field(default_factory=set)

    @property
    def targets(self) -> str:
        """Deskripsi tujuan simpan, ikut ditulis di header run `akun.txt`."""
        names = [n for n, on in (("akun.txt", self.save_file), ("9router", self.push_router)) if on]
        return " + ".join(names) or "tidak disimpan"


@dataclass(frozen=True)
class Settings:
    github_password: str
    mail_provider: str
    mail_worker_url: str
    mail_worker_password: str
    mailtm_base_url: str
    ninerouter_url: str
    ninerouter_password: str
    proxy_enabled: bool
    proxy_host: str
    proxy_user: str
    proxy_pass: str
    proxy_country: str
    sites: tuple[Site, ...]

    @property
    def proxy_configured(self) -> bool:
        return bool(self.proxy_enabled and self.proxy_user and self.proxy_pass)


def load_env(path: Path = ENV_FILE) -> None:
    """Loader .env minimal — kredensial tidak boleh masuk source code.

    Variabel yang sudah ada di environment tidak ditimpa, supaya bisa di-override
    dari shell tanpa mengedit file.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"✗ {name} belum diisi di {ENV_FILE.name} — lihat .env.example")
        sys.exit(1)
    return value


def _sites(default_model: str) -> tuple[Site, ...]:
    """Node id dikonfirmasi dari respons POST /api/providers di 9router."""
    return (
        Site(
            name="Tabitoken",
            host="tabitoken.com",
            signup_url="https://tabitoken.com/sign-up?aff=3NhN",
            provider_node_id="openai-compatible-chat-1e0cda01-0d1e-4272-9bd8-8f16200efc00",
            model=default_model,
        ),
        Site(
            name="SeekAI",
            host="seekai.cc",
            signup_url="https://seekai.cc/sign-up?aff=s2N9",
            provider_node_id="openai-compatible-chat-91520b61-f4c9-4020-a30a-57f92c733777",
            model=default_model,
        ),
    )


@lru_cache(maxsize=1)
def settings() -> Settings:
    """Baca .env sekali, keluar dengan pesan jelas kalau ada yang wajib kosong."""
    load_env()
    provider = os.getenv("MAIL_PROVIDER", "worker").strip().lower()
    if provider not in ("worker", "mailtm"):
        print(f"✗ MAIL_PROVIDER='{provider}' tidak dikenal — pakai 'worker' atau 'mailtm'")
        sys.exit(1)

    # Tidak ada default: URL worker itu milik masing-masing orang, dan default yang
    # menunjuk ke worker orang lain berarti password terkirim ke sana.
    worker_url = os.getenv("MAIL_WORKER_URL", "").strip().rstrip("/")
    if provider == "worker":
        if not worker_url:
            print("✗ MAIL_WORKER_URL belum diisi di .env — wajib bila MAIL_PROVIDER=worker")
            sys.exit(1)
        # Password dikirim mentah tiap request; http:// membocorkannya di jaringan.
        if worker_url.startswith("http://") and "127.0.0.1" not in worker_url:
            print("⚠ MAIL_WORKER_URL pakai http:// — password worker terkirim tanpa enkripsi")

    return Settings(
        github_password=_required("GITHUB_PASSWORD"),
        mail_provider=provider,
        mail_worker_url=worker_url,
        mail_worker_password=(
            _required("MAIL_WORKER_PASSWORD") if provider == "worker" else ""
        ),
        mailtm_base_url=os.getenv("MAILTM_BASE_URL", "https://api.mail.tm").rstrip("/"),
        ninerouter_url=os.getenv("NINEROUTER_URL", "http://192.168.0.105:20127").rstrip("/"),
        # Bukan `_required`: run yang hanya menyimpan ke akun.txt tidak menyentuh
        # 9router sama sekali. `ninerouter.connect` yang menolak kalau kosong.
        ninerouter_password=os.getenv("NINEROUTER_PASSWORD", "").strip(),
        proxy_enabled=_flag("PROXY_ENABLED"),
        proxy_host=os.getenv("PROXY_HOST", "gw.dataimpulse.com:823").strip(),
        proxy_user=os.getenv("PROXY_USER", "").strip(),
        proxy_pass=os.getenv("PROXY_PASS", "").strip(),
        proxy_country=os.getenv("PROXY_COUNTRY", "").strip().lower(),
        sites=_sites(os.getenv("DEFAULT_MODEL", "claude-opus-5-thinking").strip()),
    )
