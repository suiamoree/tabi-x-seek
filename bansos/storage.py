"""Satu-satunya modul yang menyentuh file hasil.

Format `akun.txt` dirancang supaya bisa dibaca mata maupun di-parse script:

    # ==========================================================================
    # RUN 2026-09-04 08:05:23 | 2 akun | situs: Tabitoken, SeekAI | simpan: akun.txt + 9router
    # ==========================================================================
    email|password|username|Tabitoken=sk-...|SeekAI=sk-...

Header run diawali `#` supaya gampang dilewati parser, dan memberi penanda visual
untuk navigasi: satu blok = satu kali `python bansos.py`. Key diberi label nama
situs, bukan hanya urutan, karena run yang hanya memilih satu situs akan
menghasilkan baris dengan satu key — tanpa label, tidak ada cara tahu itu key
situs yang mana.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import AKUN_FILE

SEPARATOR = "|"
LABEL_SEPARATOR = "="
BANNER = "# " + "=" * 74


def _clean(value: str) -> str:
    """Buang separator dan newline dari sebuah field.

    API key bisa berasal dari input manual user saat pembacaan otomatis gagal, dan
    satu `|` yang ikut tertempel akan menggeser semua field di baris itu.
    """
    for junk in (SEPARATOR, "\n", "\r"):
        value = value.replace(junk, "")
    return value.strip()


def _write(path: Path, *lines: str) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def begin_run(total: int, site_names: list[str], targets: str, path: Path = AKUN_FILE) -> None:
    """Tulis header penanda run. Dipanggil sekali sebelum akun pertama."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = (
        f"# RUN {stamp} | {total} akun | situs: {', '.join(site_names) or '-'} | simpan: {targets}"
    )
    _write(path, "", BANNER, summary, BANNER)


def append_account(
    email: str,
    password: str,
    username: str,
    keys: list[tuple[str, str]],
    path: Path = AKUN_FILE,
) -> None:
    """Satu baris per akun: `email|password|username|Situs=key|Situs=key`."""
    fields = [_clean(email), _clean(password), _clean(username)]
    fields += [f"{_clean(name)}{LABEL_SEPARATOR}{_clean(key)}" for name, key in keys]
    _write(path, SEPARATOR.join(fields))
