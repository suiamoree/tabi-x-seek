"""Client untuk https://api.mail.tm — gratis, tanpa API key.

Alur: GET /domains → POST /accounts → POST /token → GET /messages dengan
Authorization: Bearer. Batas 8 request/detik per IP; 429 diperlakukan sebagai
sinyal untuk mundur sebentak, bukan error fatal.

Atribusi: layanan disediakan oleh mail.tm (https://mail.tm).
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime

import httpx

from ..config import HTTP_TIMEOUT
from .base import extract_code, poll_for_code, random_local_part, random_password

RATE_LIMIT_BACKOFF = 1.5


def _epoch(iso: str | None) -> float:
    """'2022-04-01T00:00:00.000Z' → epoch. fromisoformat tidak menerima 'Z'."""
    if not iso:
        return 0.0
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


class MailTmMail:
    def __init__(self, base_url: str, transport=None):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=HTTP_TIMEOUT, transport=transport)
        self._tokens: dict[str, str] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, *, token: str | None = None, json=None):
        headers = {"Authorization": f"Bearer {token}"} if token else None
        while True:
            response = await self._client.request(method, path, json=json, headers=headers)
            if response.status_code == 429:
                await asyncio.sleep(RATE_LIMIT_BACKOFF)
                continue
            response.raise_for_status()
            return response.json() if response.content else {}

    async def _domains(self) -> list[str]:
        body = await self._request("GET", "/domains")
        return [d["domain"] for d in body.get("hydra:member", []) if d.get("isActive")]

    async def new_address(self) -> str:
        """Buat akun lalu simpan token-nya; inbox baru bisa dibaca setelah itu."""
        domains = await self._domains()
        if not domains:
            raise RuntimeError("mail.tm tidak punya domain aktif")

        address = f"{random_local_part()}@{random.choice(domains)}"
        password = random_password()
        credentials = {"address": address, "password": password}
        await self._request("POST", "/accounts", json=credentials)
        token = (await self._request("POST", "/token", json=credentials)).get("token")
        if not token:
            raise RuntimeError(f"mail.tm tidak mengembalikan token untuk {address}")
        self._tokens[address] = token
        return address

    async def wait_for_code(self, address: str, after: float = 0.0) -> str | None:
        token = self._tokens.get(address)
        if not token:
            raise RuntimeError(f"belum ada token mail.tm untuk {address}")

        async def list_messages():
            body = await self._request("GET", "/messages", token=token)
            return [(m["id"], _epoch(m.get("createdAt"))) for m in body.get("hydra:member", [])]

        async def read_code(message_id: str):
            message = await self._request("GET", f"/messages/{message_id}", token=token)
            # `html` di mail.tm berbentuk list of string, bukan string.
            return extract_code(message.get("subject"), message.get("text"), message.get("html"))

        return await poll_for_code(list_messages, read_code, after=after)
