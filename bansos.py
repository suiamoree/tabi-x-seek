"""bansos.py — entry point Tabi x Seek Automation.

Bootstrap dijalankan sebelum `bansos.cli` di-import supaya dependency dan browser
Camoufox sudah siap saat import pertama terjadi.

Generate N akun via temp-mail → register GitHub → OAuth ke situs penyedia API key
→ push key ke 9router → simpan batch ke akun.txt.
"""

import asyncio

from bansos import bootstrap

bootstrap.run()

from bansos import cli  # noqa: E402 — harus setelah bootstrap

if __name__ == "__main__":
    asyncio.run(cli.main())
