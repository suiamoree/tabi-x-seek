"""Kontrak dan logika bersama untuk semua penyedia temp-mail.

Yang beda antar penyedia hanya panggilan HTTP-nya. Ekstraksi kode, pembentukan
local part, dan loop polling identik, jadi tinggal di sini.
"""

from __future__ import annotations

import asyncio
import random
import re
import string
import time
from typing import Awaitable, Callable, Protocol

from ..config import OTP_POLL_INTERVAL, OTP_TIMEOUT

# GitHub launch code = 8 digit. Lookaround mencegah nyangkut di angka panjang.
OTP_PATTERN = re.compile(r"(?<!\d)(\d{8})(?!\d)")
TOKENHARBOR_VERIFY_PATTERN = re.compile(r"https?://tokenharbor\.ai/verify-email\?token=[A-Za-z0-9._~-]+")
# Agnes AI verification code = 6 digit.
AGNES_OTP_PATTERN = re.compile(r"(?<!\d)(\d{6})(?!\d)")

_LOCAL_ALPHABET = string.ascii_lowercase + string.digits
_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


# Kata kunci di subject/sender yang menandai email dari Agnes atau TokenHarbor.
# Dipakai oleh provider_mail_present di tiap implementasi.
PROVIDER_KEYWORDS = re.compile(
    r"agnes|tokenharbor|token\s*harbor",
    re.IGNORECASE,
)


class MailProvider(Protocol):
    """Satu inbox sekali pakai."""

    async def new_address(self) -> str: ...

    async def inbox_empty(self, address: str) -> bool: ...

    async def provider_mail_present(self, address: str) -> bool:
        """True kalau inbox sudah pernah dapat email dari Agnes atau TokenHarbor."""
        ...

    async def wait_for_code(self, address: str, after: float = 0.0, pattern: re.Pattern | None = None) -> str | None: ...

    async def wait_for_link(
        self, address: str, pattern: re.Pattern[str], after: float = 0.0
    ) -> str | None: ...

    async def aclose(self) -> None: ...


async def new_fresh_address(mail: "MailProvider", max_attempts: int = 10) -> str:
    """Generate alamat email yang belum pernah menerima email dari Agnes atau TokenHarbor.

    Email yang sudah dapat email dari kedua provider itu berarti sudah pernah
    didaftarkan — provider menolak "email already registered". Email yang dapat
    email dari sumber lain masih aman dipakai.
    """
    for _ in range(max_attempts):
        address = await mail.new_address()
        if not await mail.provider_mail_present(address):
            return address
        print(f"\u26a0\ufe0f  Inbox {address} sudah pernah dapat email Agnes/TokenHarbor — generate ulang")
    raise RuntimeError(f"Tidak dapat menemukan alamat email bebas setelah {max_attempts} percobaan")


def random_local_part(length: int = 12) -> str:
    """Diawali huruf supaya aman dipakai ulang sebagai username GitHub."""
    head = random.choice(string.ascii_lowercase)
    return head + "".join(random.choices(_LOCAL_ALPHABET, k=length - 1))


def random_password(length: int = 16) -> str:
    """Password akun inbox (mail.tm). Tidak disimpan; hanya untuk ambil token."""
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=length))


def _as_text(value) -> str:
    """mail.tm mengirim `html` sebagai list of string, worker sebagai string."""
    if isinstance(value, list):
        return " ".join(str(part) for part in value)
    return str(value or "")


def plain_text(text: str | None, html=None) -> str:
    body = text or _HTML_TAG.sub(" ", _as_text(html))
    return _WHITESPACE.sub(" ", body).strip()


def extract_code(
    subject: str | None,
    text: str | None,
    html=None,
    pattern: re.Pattern[str] = OTP_PATTERN,
) -> str | None:
    match = pattern.search(f"{subject or ''} {plain_text(text, html)}")
    return match.group(1) if match else None


async def poll_for_code(
    list_messages: Callable[[], Awaitable[list[tuple[str, float]]]],
    read_code: Callable[[str], Awaitable[str | None]],
    after: float = 0.0,
    timeout: float = OTP_TIMEOUT,
    interval: float = OTP_POLL_INTERVAL,
) -> str | None:
    """Poll inbox sampai ada email berisi kode.

    `list_messages` mengembalikan [(message_id, epoch_diterima)], terbaru dulu
    atau tidak, tidak penting. `after` menyaring email yang datang sebelum
    signup dimulai supaya kode lama tidak terpakai.
    """
    deadline = time.monotonic() + timeout
    seen: set[str] = set()

    while time.monotonic() < deadline:
        try:
            messages = await list_messages()
        except Exception as exc:
            print(f"   inbox poll error: {exc}")
            messages = []

        for message_id, received_at in messages:
            if message_id in seen or received_at < after:
                continue
            seen.add(message_id)
            try:
                code = await read_code(message_id)
            except Exception as exc:
                print(f"   gagal baca email {message_id}: {exc}")
                continue
            if code:
                return code

        await asyncio.sleep(interval)

    return None
