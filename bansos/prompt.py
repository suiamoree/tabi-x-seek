"""Prompt ke user, plus saklar mode jalan (semi vs auto).

Mode semi: langkah yang mentok diserahkan ke user. Mode auto: tidak ada yang
ditanyakan sama sekali — langkah yang mentok di-skip supaya batch tetap jalan
tanpa ditunggui.

Saklarnya di sini karena ini satu-satunya modul yang berbicara dengan user, jadi
tidak ada pemeriksaan mode yang tersebar ke modul lain. Nilainya diset sekali di
`cli` sebelum akun pertama dibuat dan tidak berubah selama run.
"""

from __future__ import annotations

import asyncio

MANUAL = object()  # sentinel: user bilang sudah menangani elemennya sendiri

_AUTO = False


def set_auto(enabled: bool) -> None:
    global _AUTO
    _AUTO = enabled


def is_auto() -> bool:
    return _AUTO


async def ask(prompt: str) -> str:
    """input() di thread terpisah supaya koneksi browser tidak ikut ke-freeze."""
    return (await asyncio.to_thread(input, prompt)).strip()


async def ask_retry(label: str):
    """Prompt tunggal untuk semua langkah yang mentok.

    Return: True=coba lagi | False=skip | MANUAL=user sudah kerjakan sendiri.
    """
    if _AUTO:
        print(f"   ⏭  Mode auto — '{label}' di-skip")
        return False

    print(f"   Langkah tertahan: {label}")
    answer = (await ask("   [Enter]=coba lagi  |  s=skip  |  m=sudah saya kerjakan manual: ")).lower()
    if answer == "s":
        return False
    if answer == "m":
        return MANUAL
    return True
