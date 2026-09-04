"""Client HTTP untuk dashboard 9router.

Login mengembalikan respons tanpa body, autentikasinya lewat cookie:

    POST /api/auth/login  {"password": "..."}
    → 200, set-cookie: auth_token=...; Path=/; HttpOnly; SameSite=lax

httpx.AsyncClient menyimpan cookie itu dan mengirimnya otomatis di request
berikutnya, jadi tidak ada header Cookie yang disusun manual di sini.
"""

from __future__ import annotations

import httpx

from .config import HTTP_TIMEOUT, Settings

AUTH_COOKIE = "auth_token"


class NineRouter:
    def __init__(self, config: Settings, transport=None):
        self._password = config.ninerouter_password
        self._client = httpx.AsyncClient(
            base_url=config.ninerouter_url, timeout=HTTP_TIMEOUT, transport=transport
        )
        self.base_url = config.ninerouter_url
        self._taken_names: set[str] = set()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def login(self) -> bool:
        """Sukses = 200 dan cookie auth_token benar-benar masuk jar."""
        try:
            response = await self._client.post(
                "/api/auth/login", json={"password": self._password}
            )
        except httpx.HTTPError as exc:
            print(f"✗ 9router tidak bisa dihubungi ({self.base_url}): {exc}")
            return False

        if response.status_code != 200:
            detail = response.json().get("error") if response.content else response.reason_phrase
            print(f"✗ Login 9router ditolak (HTTP {response.status_code}): {detail}")
            return False
        if AUTH_COOKIE not in self._client.cookies:
            print(f"✗ Login 9router 200 tapi cookie {AUTH_COOKIE} tidak dikirim")
            return False

        print("✓ Login 9router berhasil")
        return True

    async def node_ids(self) -> set[str]:
        """ID provider node yang ada — dipakai memvalidasi config sebelum run."""
        try:
            response = await self._client.get("/api/provider-nodes")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"⚠️  Gagal ambil provider-nodes: {exc}")
            return set()
        return {node["id"] for node in response.json().get("nodes", []) if node.get("id")}

    async def load_existing_names(self) -> None:
        """Ambil nama connection yang sudah ada supaya tidak ada yang ditimpa."""
        self._taken_names = await self._existing_names()

    async def _existing_names(self) -> set[str]:
        try:
            response = await self._client.get("/api/providers")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"⚠️  Gagal ambil daftar connection: {exc}")
            return set()
        connections = response.json().get("connections") or []
        return {c["name"] for c in connections if c.get("name")}

    def _unique_name(self, name: str) -> str:
        """POST /api/providers dengan nama yang sudah ada menimpa connection lama.

        Nama diambil dari local part temp-mail yang acak jadi tabrakan hampir
        tidak mungkin, tapi menimpa key yang sudah ada tidak bisa dibatalkan.
        """
        if name not in self._taken_names:
            self._taken_names.add(name)
            return name
        suffix = 2
        while f"{name}-{suffix}" in self._taken_names:
            suffix += 1
        unique = f"{name}-{suffix}"
        print(f"⚠️  Nama '{name}' sudah dipakai di 9router → simpan sebagai '{unique}'")
        self._taken_names.add(unique)
        return unique

    async def validate(self, node_id: str, api_key: str) -> bool | None:
        """None = tidak bisa dipastikan (error/timeout), bukan berarti invalid."""
        try:
            response = await self._client.post(
                "/api/providers/validate", json={"provider": node_id, "apiKey": api_key}
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"⚠️  Validasi key gagal dijalankan: {exc}")
            return None
        return bool(response.json().get("valid"))

    async def push_key(self, node_id: str, name: str, api_key: str, model: str) -> bool:
        valid = await self.validate(node_id, api_key)
        print("   validasi key:", {True: "valid", False: "invalid", None: "tidak diketahui"}[valid])

        unique_name = self._unique_name(name)
        payload = {
            "provider": node_id,
            "name": unique_name,
            "apiKey": api_key,
            "defaultModel": model,
            "priority": 1,
            "proxyPoolId": None,
            "testStatus": "active" if valid else "unknown",
        }
        try:
            response = await self._client.post("/api/providers", json=payload)
        except httpx.HTTPError as exc:
            print(f"✗ Push key ke 9router gagal: {exc}")
            return False

        if response.status_code not in (200, 201):
            detail = response.json().get("error") if response.content else response.reason_phrase
            print(f"✗ Push key ditolak (HTTP {response.status_code}): {detail}")
            return False

        connection = response.json().get("connection") or {}
        if not connection.get("isActive"):
            print(f"⚠️  Connection tersimpan tapi tidak aktif: {connection.get('id')}")
            return False

        print(f"✓ Key masuk 9router sebagai '{unique_name}'")
        return True


async def connect(config: Settings) -> NineRouter | None:
    """Login lalu pastikan tiap node id di config benar-benar ada.

    Dijalankan sebelum akun pertama dibuat: kalau node id salah, lebih baik tahu
    sekarang daripada setelah membuang beberapa akun GitHub.
    """
    if not config.ninerouter_password:
        print("✗ NINEROUTER_PASSWORD belum diisi di .env — lihat .env.example")
        return None

    client = NineRouter(config)
    if not await client.login():
        await client.aclose()
        return None

    available = await client.node_ids()
    if available:
        for site in config.sites:
            if site.provider_node_id not in available:
                print(f"⚠️  Node id {site.name} tidak ada di 9router: {site.provider_node_id}")

    await client.load_existing_names()
    return client