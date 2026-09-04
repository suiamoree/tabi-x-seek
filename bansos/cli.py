"""Entry point: tanya opsi run, jalankan, ringkas hasil.

`prompt.set_auto` dipanggil sebelum akun pertama dibuat, jadi seluruh alur di
bawahnya tahu apakah boleh bertanya ke user tanpa perlu meneruskan flag.
"""

from __future__ import annotations

import dataclasses
import traceback

from . import browser, ninerouter, prompt, runner, storage
from .config import RunOptions, Settings, Site, settings
from .mail import make_mail
from .prompt import ask


async def _pick(title: str, options: dict[str, tuple[str, object]], default_key: str, note: str = ""):
    """Prompt pilihan bernomor. Enter = `default_key`. Mengulang sampai valid."""
    print(f"\n{title}:")
    for key, (label, _) in options.items():
        suffix = "  ← default" if key == default_key else ""
        print(f"  {key}. {label}{suffix}")
    if note:
        print(f"  ({note})")

    while True:
        raw = await ask(f"Pilih [{'/'.join(options)}] (Enter = default): ")
        key = raw or default_key
        if key in options:
            return options[key][1]
        print(f"✗ Pilih salah satu: {', '.join(options)}")


async def _account_count() -> int:
    raw = await ask("Mau generate berapa akun? ")
    if not raw.isdigit() or int(raw) < 1:
        print("✗ Input harus angka >= 1")
        return 0
    return int(raw)


async def _pick_sites(available: tuple[Site, ...]) -> tuple[Site, ...]:
    """Semua situs, atau satu saja. Urutan aslinya dipertahankan."""
    options: dict[str, tuple[str, tuple[Site, ...]]] = {
        "1": (f"semua ({', '.join(site.name for site in available)})", available)
    }
    for index, site in enumerate(available, start=2):
        options[str(index)] = (f"{site.name} saja", (site,))
    return await _pick("Situs yang dikerjakan", options, default_key="1")


async def _pick_targets() -> tuple[bool, bool]:
    """Return (simpan ke akun.txt, push ke 9router)."""
    return await _pick(
        "Simpan hasil ke",
        {
            "1": ("akun.txt + 9router", (True, True)),
            "2": ("akun.txt saja — tanpa menyentuh 9router", (True, False)),
            "3": ("9router saja — tidak menulis file", (False, True)),
        },
        default_key="1",
    )


async def _run_mode() -> bool:
    """True = auto (tanpa prompt sama sekali), False = semi (eskalasi ke user)."""
    return await _pick(
        "Mode jalan",
        {
            "1": ("semi — script tanya kalau ada langkah yang mentok", False),
            "2": ("auto — tanpa prompt, langkah yang mentok di-skip", True),
        },
        default_key="1",
    )


async def _browser_mode() -> bool | str:
    modes = browser.available_modes()
    default = next(key for key, (_, value) in modes.items() if value == browser.DEFAULT_MODE)
    note = "" if browser.VIRTUAL_SUPPORTED else "mode virtual butuh Xvfb, hanya tersedia di Linux"
    return await _pick("Mode browser", modes, default_key=default, note=note)


async def _ask_options(config: Settings) -> tuple[Settings, RunOptions, int] | None:
    """Semua pertanyaan sebelum run. None kalau jumlah akun tidak valid.

    `config` dikembalikan dalam bentuk baru dengan `sites` yang sudah disaring,
    jadi sisa alur tidak perlu tahu bahwa user pernah memilih subset.
    """
    total = await _account_count()
    if not total:
        return None

    chosen = await _pick_sites(config.sites)
    save_file, push_router = await _pick_targets()
    prompt.set_auto(await _run_mode())
    options = RunOptions(
        browser_mode=await _browser_mode(), save_file=save_file, push_router=push_router
    )

    mode = "auto (tanpa prompt)" if prompt.is_auto() else "semi (eskalasi ke user)"
    print(f"\n→ Jumlah akun  : {total}")
    print(f"→ Situs        : {', '.join(site.name for site in chosen)}")
    print(f"→ Simpan ke    : {options.targets}")
    print(f"→ Mode jalan   : {mode}")
    print(f"→ Mode browser : {browser.mode_label(options.browser_mode)}")
    return dataclasses.replace(config, sites=chosen), options, total


async def main() -> None:
    print("=" * 60)
    print("TABI X SEEK AUTOMATION")
    print("=" * 60)

    asked = await _ask_options(settings())
    if asked is None:
        return
    config, options, total = asked

    router = None
    if options.push_router:
        router = await ninerouter.connect(config)
        if router is None:
            print("   Cek NINEROUTER_URL dan NINEROUTER_PASSWORD di .env, lalu ulangi.")
            print("   Atau pilih 'akun.txt saja' kalau memang belum mau push ke 9router.")
            return

    if options.save_file:
        storage.begin_run(total, [site.name for site in config.sites], options.targets)

    mail = make_mail(config)
    succeeded = 0

    try:
        for index in range(1, total + 1):
            print(f"\n[{index}/{total}] Memproses akun...")
            if await runner.run_account(mail, router, config, options):
                succeeded += 1
                print(f"✅ Akun [{index}/{total}] berhasil")
            else:
                print(f"❌ Akun [{index}/{total}] gagal")

        print(f"\n{'=' * 60}")
        print(f"✅ SELESAI — {succeeded}/{total} akun berhasil")
        print("=" * 60)
        print(f"Tersimpan di: {options.targets}")
    except KeyboardInterrupt:
        print("\n⚠  Dihentikan user")
    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        traceback.print_exc()
    finally:
        await mail.aclose()
        if router is not None:
            await router.aclose()
