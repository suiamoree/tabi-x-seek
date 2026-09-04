"""Client untuk temp-mail worker pribadi (Cloudflare Worker + D1).

Endpoint (GET, butuh `Authorization: Bearer <APP_PASSWORD>`):
  /domains                 → daftar domain aktif
  /emails/{address}?limit= → ringkasan inbox
  /inbox/{emailId}         → isi lengkap (html_content, text_content)

Password dikirim mentah di setiap request, jadi base URL wajib https.
"""

from __future__ import annotations

import random

import httpx

from ..config import HTTP_TIMEOUT
from .base import extract_code, poll_for_code, random_local_part

# Worker memisahkan "klien salah password" (401) dari "server lupa set secret" (503).
_AUTH_HINT = {
    401: "password salah atau header hilang — cek MAIL_WORKER_PASSWORD di .env",
    503: "worker belum di-set APP_PASSWORD (Worker secret / .dev.vars)",
}


class WorkerMail:
    def __init__(self, base_url: str, password: str = "", transport=None):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=HTTP_TIMEOUT,
            transport=transport,
            headers={"Authorization": f"Bearer {password}"} if password else {},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str):
        response = await self._client.get(path)
        hint = _AUTH_HINT.get(response.status_code)
        if hint:
            raise RuntimeError(f"worker {response.status_code}: {hint}")
        response.raise_for_status()
        body = response.json()
        if not body.get("success"):
            raise RuntimeError(body.get("error", {}).get("message", "unknown API error"))
        return body["result"]

    async def _domains(self) -> list[str]:
        raw = await self._get("/domains")
        domains = []
        for item in raw:
            # API pernah mengirim string, sekarang object — dukung keduanya.
            domains.append(item if isinstance(item, str) else item.get("domain", ""))
        return [d for d in domains if d]

    async def new_address(self) -> str:
        """Alamat langsung aktif — worker menerima apa pun di domain terdaftar."""
        domains = await self._domains()
        if not domains:
            raise RuntimeError("worker tidak punya domain aktif")
        return f"{random_local_part()}@{random.choice(domains)}"

    async def wait_for_code(self, address: str, after: float = 0.0) -> str | None:
        async def list_messages():
            summaries = await self._get(f"/emails/{address}?limit=20")
            return [(s["id"], float(s.get("received_at") or 0)) for s in summaries]

        async def read_code(message_id: str):
            email = await self._get(f"/inbox/{message_id}")
            return extract_code(
                email.get("subject"), email.get("text_content"), email.get("html_content")
            )

        return await poll_for_code(list_messages, read_code, after=after)
