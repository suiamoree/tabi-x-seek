"""Cek dependency + browser Camoufox sebelum modul lain di-import.

Dipanggil dari `bansos.py` paling awal. Kalau ada yang gagal dipasang, keluar
dengan pesan jelas alih-alih meledak di `import camoufox` beberapa baris nanti.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

from .config import AKUN_FILE, BASE_DIR, ENV_FILE

REQUIREMENTS = BASE_DIR / "requirements.txt"

# Nama paket pip → nama modul yang di-import. Untuk paket di sini keduanya sama,
# tapi dipisah supaya jelas mana yang dicek dan mana yang dipasang.
CHECKS = {
    "camoufox": "camoufox",
    "browserforge": "browserforge",
    "httpx": "httpx",
    "playwright": "playwright",
}


def use_utf8_stdout() -> None:
    """Console Windows default cp1252 tidak bisa mencetak ✓ ⚠ yang dipakai di log."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _missing_packages() -> list[str]:
    missing = []
    for package, module in CHECKS.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(package)
    return missing


def _run(args: list[str], what: str) -> bool:
    print(f"→ {what}...")
    if subprocess.run(args, check=False).returncode == 0:
        return True
    print(f"✗ {what} gagal")
    return False


def _install_missing() -> bool:
    missing = _missing_packages()
    if not missing:
        print("✓ Dependency lengkap")
        return True
    print(f"⚠  Dependency kurang: {', '.join(missing)}")
    if not REQUIREMENTS.exists():
        print(f"✗ {REQUIREMENTS.name} tidak ada, tidak bisa memasang otomatis")
        return False
    return _run(
        [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        f"pip install -r {REQUIREMENTS.name}",
    )


def _browser_ready() -> bool:
    """Camoufox mengunduh Firefox-nya sendiri, terpisah dari paket pip."""
    try:
        import camoufox.pkgman

        path = camoufox.pkgman.launch_path()
        return bool(path) and Path(path).exists()
    except Exception:
        return False


def _fetch_browser() -> bool:
    if _browser_ready():
        print("✓ Browser Camoufox siap")
        return True
    print("⚠  Browser Camoufox belum ada")
    return _run([sys.executable, "-m", "camoufox", "fetch"], "download browser Camoufox")


def run() -> None:
    use_utf8_stdout()
    if not _install_missing() or not _fetch_browser():
        print("   Perbaiki dulu lalu jalankan ulang.")
        sys.exit(1)

    if not ENV_FILE.exists():
        print(f"✗ {ENV_FILE.name} tidak ada — copy dari .env.example lalu isi")
        sys.exit(1)

    AKUN_FILE.touch(exist_ok=True)
