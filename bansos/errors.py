"""Exception khusus alur bansos."""

from __future__ import annotations


class BotBlocked(Exception):
    """GitHub menampilkan 'unusual activity' — IP + fingerprint harus diganti.

    Blokirnya terikat pada IP dan fingerprint browser, bukan pada page, jadi
    retry di dalam browser yang sama selalu gagal. Dilempar ke runner supaya
    browser di-relaunch dengan session proxy (IP) dan fingerprint baru.
    """


class EmailRejected(Exception):
    """GitHub menolak alamat email (domain temp-mail masuk daftar blokir)."""


class StepSkipped(Exception):
    """Sebuah langkah dilewati — user memilih 'skip', atau mode auto menyerah.

    Dilempar, bukan dikembalikan sebagai None, supaya keputusan itu langsung
    keluar dari seluruh rangkaian retry. Tanpa ini, lapisan retry di atasnya akan
    memuat ulang halaman dan mengulang langkah yang sama sekali lagi.
    """
