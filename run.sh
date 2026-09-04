#!/usr/bin/env bash
# Launcher Linux/macOS: cari Python, siapkan .env, jalankan.
# Bootstrap di dalam bansos.py yang memasang dependency dan mengunduh browser,
# jadi di sini cukup memastikan interpreternya ada dan .env sudah dibuat.
set -euo pipefail

cd "$(dirname "$0")"

PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "[X] Python tidak ditemukan di PATH."
    echo "    Debian/Ubuntu: sudo apt install python3 python3-venv"
    exit 1
fi

if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "[X] Butuh Python 3.10+, yang terpasang: $("$PY" --version 2>&1)"
    exit 1
fi

if [ ! -f .env ]; then
    if [ ! -f .env.example ]; then
        echo "[X] .env dan .env.example tidak ada."
        exit 1
    fi
    cp .env.example .env
    echo "[!] .env belum ada - dibuat dari .env.example"
    echo "    Isi dulu GITHUB_PASSWORD dan NINEROUTER_PASSWORD, lalu jalankan lagi."
    exit 1
fi

# Mode browser 'virtual' memakai Xvfb. Diperingatkan di sini, bukan digagalkan:
# mode itu hanya salah satu pilihan dan yang lain tetap jalan tanpa Xvfb.
if [ "$(uname -s)" = "Linux" ] && ! command -v Xvfb >/dev/null 2>&1; then
    echo "[i] Xvfb tidak terpasang - mode browser 'virtual' tidak akan tersedia."
    echo "    Pasang dengan: sudo apt install xvfb"
fi

exec "$PY" bansos.py "$@"
