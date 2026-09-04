<h1 align="center">Tabi x Seek Automation</h1>

<p align="center">
  <b>Email sekali pakai → akun GitHub → OAuth → API key → 9router → <code>akun.txt</code></b><br>
  Satu perintah, N akun. Mode auto jalan tanpa ditunggui;<br>
  mode semi berhenti dan bertanya kalau mentok.
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="Camoufox" src="https://img.shields.io/badge/browser-Camoufox-FF7139?logo=firefox&logoColor=white">
  <img alt="Playwright" src="https://img.shields.io/badge/driver-Playwright-2EAD33?logo=playwright&logoColor=white">
  <img alt="Tanpa framework tes" src="https://img.shields.io/badge/tes-assert%20biasa-6E7681">
</p>

Otomasi pembuatan akun batch: bikin alamat email sekali pakai, daftar GitHub,
login OAuth ke situs penyedia API key ([Tabitoken](https://tabitoken.com) dan
[SeekAI](https://seekai.cc)), ambil API key-nya, lalu kirim ke dashboard
[9router](http://192.168.0.105:20127) dan/atau simpan ke `akun.txt`.

Browsernya [Camoufox](https://github.com/daijro/camoufox) — Firefox sungguhan
dengan fingerprint yang disamarkan, dijalankan lewat Playwright. Sebelum run, CLI
menanyakan situs mana yang dikerjakan, hasilnya disimpan ke mana, **mode jalan**
(semi atau auto), dan **mode browser** (non-headless, virtual display Xvfb, atau
headless).

> [!WARNING]
> Script ini mengotomasi pendaftaran akun di layanan pihak ketiga. Pastikan kamu
> paham ketentuan layanan masing-masing situs sebelum memakainya, dan baca
> [Batasan & known issues](#-batasan--known-issues) lebih dulu — beberapa hal
> memang tidak bisa diperbaiki dari sisi script.

## Isi

| | |
| --- | --- |
| 🧭 [Alur kerja](#-alur-kerja) | Apa yang terjadi per akun |
| 📦 [Persiapan](#-persiapan) | Install, `run.bat` / `run.sh` |
| 🔧 [Konfigurasi](#-konfigurasi) | Isi `.env` |
| 🚀 [Menjalankan](#-menjalankan) | Situs, tujuan simpan, dua mode |
| 🩹 [Kalau sebuah langkah gagal](#-kalau-sebuah-langkah-gagal) | Retry, hard refresh, semi vs auto |
| 📤 [Hasil](#-hasil) | Format `akun.txt` + 9router |
| 🚨 [Batasan & known issues](#-batasan--known-issues) | **Baca ini** |
| 🧩 [Struktur kode](#-struktur-kode) | File apa mengurus apa |
| 🔍 [Cara kerjanya di dalam](#-cara-kerjanya-di-dalam) | Bagian yang tidak jelas dari kodenya |
| 🧰 [Troubleshooting](#-troubleshooting) | Pesan error → penyebab |
| ✅ [Self-check](#-self-check) | `python -m bansos.selfcheck` |
| ➕ [Menambah situs baru](#-menambah-situs-baru) | Satu entry di `config.py` |
| 🔐 [Catatan keamanan](#-catatan-keamanan) | Kredensial mentah di disk |

## 🧭 Alur kerja

```mermaid
flowchart TD
    Entry["bansos.py"] --> Boot["bootstrap: cek deps, download browser"]
    Boot --> Cli["cli: jumlah, situs, tujuan simpan, 2 mode"]
    Cli --> Router["ninerouter: login, cek node id"]
    Router --> Loop["runner: satu akun, satu browser, satu IP"]
    Loop --> Mail["mail: bikin alamat sekali pakai"]
    Mail --> Gh["github: signup, slider captcha, OTP, login"]
    Gh --> Sites["sites: consent, OAuth, buat API key"]
    Sites --> Push["9router: POST /api/providers"]
    Sites --> Save["akun.txt"]
    Loop -->|kena blokir anti-bot| Loop
```

Urutan per akun, lebih detail:

1. Browser baru dijalankan dengan satu session proxy (satu IP tetap).
2. Buka `github.com` dulu, gerakkan mouse sebentar, baru klik ke halaman signup.
   Membuka `/signup` langsung tanpa referer adalah pola bot.
3. Selesaikan slider captcha GitHub.
4. **Baru** generate alamat email. Kalau captcha gagal, alamat tidak terbuang.
5. Isi email, password, username, submit, ambil kode OTP 8 digit dari inbox.
6. Login GitHub.
7. Untuk tiap situs yang dipilih: centang consent, klik `Continue with GitHub`,
   Authorize, buka `/keys`, buat API key, baca nilainya dari halaman.
8. Key dikirim ke 9router dan/atau satu baris ditulis ke `akun.txt`, sesuai tujuan
   simpan yang dipilih.

Tiap langkah di atas mengikuti pola yang sama saat gagal: coba beberapa kali →
hard refresh sampai 2x → baru menyerah. Menyerahnya berarti bertanya ke kamu
(mode semi) atau melewati langkah itu (mode auto). Detailnya di
[Kalau sebuah langkah gagal](#-kalau-sebuah-langkah-gagal).

## 📦 Persiapan

Butuh Python 3.10 atau lebih baru.

| Cara | Perintah |
| --- | --- |
| Windows | dobel-klik **`run.bat`** |
| Linux / macOS | `chmod +x run.sh` sekali, lalu **`./run.sh`** |
| Manual | `python bansos.py` |

Launcher-nya mencari Python di PATH, membuat `.env` dari `.env.example` kalau
belum ada, lalu menjalankan script. `run.bat` menahan jendela terbuka di akhir
supaya pesan errornya terbaca kalau dijalankan dari Explorer.

```powershell
cd F:\Coding\python\tabi-x-seek
Copy-Item .env.example .env
notepad .env          # isi yang wajib, lihat bagian Konfigurasi
python bansos.py
```

Dependency dan browser tidak perlu dipasang manual. Saat pertama dijalankan,
`bansos.py` memanggil `bootstrap` yang:

- mengecek `camoufox`, `browserforge`, `httpx`, `playwright`; yang kurang dipasang
  lewat `pip install -r requirements.txt`
- mengunduh browser Camoufox (`python -m camoufox fetch`) kalau belum ada —
  ukurannya sekitar 200 MB, sekali saja
- membuat `akun.txt` kalau belum ada
- berhenti dengan pesan jelas kalau `.env` belum dibuat

Kalau mau pasang manual lebih dulu:

```powershell
pip install -r requirements.txt
python -m camoufox fetch
```

## 🔧 Konfigurasi

Semua nilai dibaca dari `.env`. Tidak ada kredensial di dalam kode.

### Wajib

| Variabel | Keterangan |
| --- | --- |
| `GITHUB_PASSWORD` | Password yang dipakai untuk semua akun GitHub yang dibuat |
| `NINEROUTER_URL` | Alamat dashboard 9router, contoh `http://192.168.0.105:20127` |
| `NINEROUTER_PASSWORD` | Password login dashboard 9router. Hanya dibutuhkan kalau hasilnya di-push ke 9router |
| `MAIL_WORKER_URL` | URL Worker temp-mail milikmu sendiri. Wajib bila `MAIL_PROVIDER=worker` |
| `MAIL_WORKER_PASSWORD` | Hanya wajib bila `MAIL_PROVIDER=worker` |

Script berhenti dengan pesan yang menyebut nama variabelnya kalau salah satu
kosong, jadi tidak ada kegagalan misterius di tengah jalan.

### Penyedia email sekali pakai

`MAIL_PROVIDER` memilih salah satu dari dua penyedia:

| Nilai | Penyedia | Catatan |
| --- | --- | --- |
| `worker` | Inbox pribadi (Cloudflare Worker + D1) | Butuh `MAIL_WORKER_URL` dan `MAIL_WORKER_PASSWORD` |
| `mailtm` | [mail.tm](https://mail.tm) | Gratis, tanpa API key, batas 8 request per detik |

```ini
MAIL_PROVIDER=worker
MAIL_WORKER_URL=https://temp-mail.example.workers.dev
MAIL_WORKER_PASSWORD=       # sama dengan APP_PASSWORD di Worker secret
MAILTM_BASE_URL=https://api.mail.tm
```

> [!IMPORTANT]
> Pakai `worker`. Dengan `mailtm`, akun GitHub yang baru selesai didaftarkan
> **langsung di-suspend** — lihat
> [Akun mail.tm langsung kena ban GitHub](#akun-mailtm-langsung-kena-ban-github).
> `mailtm` hanya berguna untuk mengetes alur script-nya.

Ketentuan pakai mail.tm juga meminta atribusi balik ke mail.tm bila API-nya
dipakai.

### Proxy (opsional)

```ini
PROXY_ENABLED=0                        # 1 untuk mengaktifkan
PROXY_USER=
PROXY_PASS=
PROXY_HOST=gw.dataimpulse.com:823
PROXY_COUNTRY=                         # kode negara 2 huruf, contoh: id
```

`PROXY_ENABLED=0` membuat script jalan langsung tanpa proxy — berguna untuk debug
tanpa membakar kuota bandwidth. Detail soal kenapa syntax username-nya penting ada
di [Cara kerjanya di dalam](#-cara-kerjanya-di-dalam).

### Opsional lainnya

| Variabel | Default | Keterangan |
| --- | --- | --- |
| `DEFAULT_MODEL` | `claude-opus-5-thinking` | Model yang disimpan bersama tiap connection di 9router |
| `DISPLAY`, `WAYLAND_DISPLAY` | — | Hanya untuk Linux. Mode jalan dan mode browser dipilih di CLI, bukan di `.env` |

## 🚀 Menjalankan

```powershell
python bansos.py       # atau run.bat / ./run.sh
```

Lima pertanyaan sebelum jalan:

| Pertanyaan | Pilihan |
| --- | --- |
| Jumlah akun | angka ≥ 1 |
| Situs yang dikerjakan | semua, Tabitoken saja, atau SeekAI saja |
| Simpan hasil ke | `akun.txt` + 9router, `akun.txt` saja, atau 9router saja |
| [Mode jalan](#mode-jalan) | semi atau auto |
| [Mode browser](#mode-browser) | non-headless, virtual display, atau headless |

Semua punya default yang bisa diambil dengan Enter. Kalau 9router ikut dipilih,
script login dan memastikan node id tiap situs benar-benar ada di dashboard
sebelum akun pertama dibuat — kalau ada yang salah, kamu tahu sekarang, bukan
setelah membuang beberapa akun. Memilih "akun.txt saja" tidak menyentuh 9router
sama sekali, jadi `NINEROUTER_PASSWORD` boleh kosong.

### Mode jalan

| Pilihan | Arti |
| --- | --- |
| `1` **semi** | Default. Langkah yang mentok setelah dua kali hard refresh diserahkan ke kamu: coba lagi, skip, atau kamu kerjakan sendiri di jendela browser |
| `2` **auto** | Tidak ada prompt sama sekali. Langkah yang mentok langsung di-skip dan script lanjut. Cocok untuk batch besar yang ditinggal |

Mode auto tetap memakai jatah hard refresh yang sama — bedanya hanya apa yang
terjadi setelah jatah itu habis. Efek sampingnya: satu situs yang gagal berarti
akun itu hanya membawa key dari situs lain, dan akun yang gagal di langkah GitHub
dilewati sepenuhnya. Ringkasan akhir tetap menyebut berapa yang berhasil.

### Mode browser

| Pilihan | Arti |
| --- | --- |
| `1` non-headless | Jendela Firefox terlihat. Default — kamu bisa mengawasi dan membantu manual kalau script mentok |
| `2` virtual display | Firefox berjalan di dalam layar virtual [Xvfb](https://en.wikipedia.org/wiki/Xvfb): jendelanya tidak tampil, tapi browsernya tetap berjalan dalam mode berjendela sungguhan, jadi tidak ada sinyal headless. **Linux saja** |
| `3` headless | Paling ringan, tapi paling mudah terdeteksi |

Pilihan `2` hanya ditawarkan di Linux, karena Xvfb tidak ada di Windows/macOS.
Kalau Xvfb belum terpasang: `sudo apt install xvfb`.

> [!TIP]
> Kombinasi paling masuk akal: **semi + non-headless** untuk uji coba dan batch
> kecil, **auto + virtual display** (Linux) untuk batch besar yang ditinggal.
> Auto + headless paling ringan, tapi headless juga paling mudah terdeteksi.

Contoh keluaran:

```
✓ Dependency lengkap
✓ Browser Camoufox siap
============================================================
TABI X SEEK AUTOMATION
============================================================
Mau generate berapa akun? 2

Situs yang dikerjakan:
  1. semua (Tabitoken, SeekAI)  ← default
  2. Tabitoken saja
  3. SeekAI saja
Pilih [1/2/3] (Enter = default):

Simpan hasil ke:
  1. akun.txt + 9router  ← default
  2. akun.txt saja — tanpa menyentuh 9router
  3. 9router saja — tidak menulis file
Pilih [1/2/3] (Enter = default):

Mode jalan:
  1. semi — script tanya kalau ada langkah yang mentok  ← default
  2. auto — tanpa prompt, langkah yang mentok di-skip
Pilih [1/2] (Enter = default):

Mode browser:
  1. non-headless (jendela terlihat)  ← default
  3. headless (paling mudah terdeteksi)
  (mode virtual butuh Xvfb, hanya tersedia di Linux)
Pilih [1/3] (Enter = default):

→ Jumlah akun  : 2
→ Situs        : Tabitoken, SeekAI
→ Simpan ke    : akun.txt + 9router
→ Mode jalan   : semi (eskalasi ke user)
→ Mode browser : non-headless (jendela terlihat)
✓ Login 9router berhasil
📬 Temp-mail: worker pribadi (https://temp-mail.example.workers.dev)

[1/2] Memproses akun...
🌐 Proxy sessid: acc1788439482c3m8
🚀 Launching browser 1366x720 — non-headless (jendela terlihat)...
✓ Browser launched
→ Warmup: buka github.com dulu...
→ Cek slider captcha...
✓ Slider captcha lolos
→ Email digenerate setelah captcha lolos: mb0cj855y9hz@contoh.store
```

## 🩹 Kalau sebuah langkah gagal

Setiap langkah — buka halaman, klik tombol, isi field, tunggu redirect, ambil API
key — mengikuti urutan yang sama:

1. Coba beberapa kali dengan jeda di antaranya.
2. Masih gagal → **hard refresh** halaman (reload tanpa cache), lalu ulangi
   langkahnya dari awal. Maksimal 2 kali: kemacetan yang tidak sembuh setelah dua
   kali muat ulang bersih hampir selalu bukan soal render, jadi refresh ketiga
   hanya membuang waktu.
3. Jatah habis → mode semi bertanya, mode auto men-skip langkahnya.

Di mode semi:

```
✗ [Create API Key] tidak ketemu setelah 3x percobaan.
   Selector yang dicoba: ["button:has-text('Create API Key')", ...]
↻ [API key Tabitoken] mentok — hard refresh 1/2, lalu coba lagi
→ Hard refresh (tanpa cache)...
↻ [API key Tabitoken] mentok — hard refresh 2/2, lalu coba lagi
→ Hard refresh (tanpa cache)...
   Langkah tertahan: API key Tabitoken
   [Enter]=coba lagi  |  s=skip  |  m=sudah saya kerjakan manual:
```

- **Enter** — coba lagi dari awal, dengan jatah hard refresh baru
- **s** — lewati; situs itu dianggap gagal dan script lanjut ke situs berikutnya
- **m** — kamu sudah klik atau mengisinya sendiri di jendela browser, script
  lanjut ke langkah berikutnya

Di mode auto, baris terakhirnya diganti satu baris log dan script langsung lanjut:

```
   ⏭  Mode auto — 'API key Tabitoken' di-skip
```

Langkah yang mengisi form (signup GitHub, kotak OTP) tetap ikut pola ini, tapi
refresh-nya mengulang pengisian dari awal, bukan hanya menekan tombol submit
lagi — halaman yang dimuat ulang mengosongkan field yang sudah terisi.

Slider captcha dan challenge Cloudflare juga di-hard-refresh dulu, dengan satu
pengecualian: setelah kamu menyelesaikan captcha manual, halaman tidak dimuat
ulang lagi supaya hasilnya tidak ikut hilang.

## 📤 Hasil

Dua tujuan, dipilih di CLI: `akun.txt` + 9router (default), `akun.txt` saja, atau
9router saja.

**9router** — tiap key dikirim ke `POST /api/providers` dan langsung aktif.
Nama connection-nya `{username}-{situs}`, misalnya `k9xyzab-tabitoken`.

**`akun.txt`** — tiap run diawali header bertanda `#`, lalu satu baris per akun:

```
# ==========================================================================
# RUN 2026-09-04 08:12:41 | 2 akun | situs: Tabitoken, SeekAI | simpan: akun.txt + 9router
# ==========================================================================
mb0cj855y9hz@contoh.store|rahasia|mb0cj855y9hz|Tabitoken=sk-abc123...|SeekAI=sk-def456...
p087n94awa0m@contoh.store|rahasia|p087n94awa0m|Tabitoken=sk-ghi789...|SeekAI=sk-jkl012...

# ==========================================================================
# RUN 2026-09-04 09:40:03 | 1 akun | situs: SeekAI | simpan: akun.txt
# ==========================================================================
lvpu6fjoz2zx@contoh.store|rahasia|lvpu6fjoz2zx|SeekAI=sk-mno345...
```

Formatnya: `email|password|username|Situs=key|Situs=key`. Key diberi label nama
situs, bukan hanya urutan — run yang memilih satu situs menghasilkan baris dengan
satu key, dan tanpa label tidak ada cara tahu itu key situs yang mana.

Untuk membaca file ini dari script, lewati baris yang diawali `#`:

```powershell
Get-Content akun.txt | Where-Object { $_ -and -not $_.StartsWith('#') }
```

File ini masuk `.gitignore`. Isinya kredensial mentah, jangan di-commit.

## 🚨 Batasan & known issues

Hal-hal di bawah ini **tidak bisa ditambal dari sisi script** — sebagian ada di
layanan pihak ketiga, sebagian memang batas dari pendekatannya. Yang ditandai
"terjadi" sudah pernah kejadian saat dipakai; sisanya batasan desain.

### Akun mail.tm langsung kena ban GitHub

> [!CAUTION]
> **Terjadi.** Dengan `MAIL_PROVIDER=mailtm`, akun GitHub yang baru selesai
> didaftarkan langsung di-suspend — bukan beberapa saat kemudian, tapi persis
> setelah registrasi. Alurnya berhenti di situ: tidak sampai OAuth, tidak ada API
> key, dan akunnya tidak terpakai.

Dugaan penyebabnya: domain mail.tm dipakai massal jadi ikut terpantau di sisi
GitHub. Yang pasti, script tidak bisa mencegahnya — signup-nya sendiri diterima,
banned-nya datang dari sisi GitHub setelah itu.

| Situasi | Yang terjadi |
| --- | --- |
| Domain ditolak di form signup | Terdeteksi otomatis. Script berhenti lewat `EmailRejected` dan tidak membuang captcha yang sudah lolos |
| Akun jadi lalu langsung di-suspend | **Tidak terdeteksi.** Script lanjut ke langkah berikutnya dan gagal di sana |
| Cara menghindari | `MAIL_PROVIDER=worker` dengan domain sendiri |

Domain sendiri lewat Cloudflare Worker tidak dipakai orang lain, jadi tidak
membawa reputasi buruk. Praktisnya: pakai `worker`. `mailtm` hanya berguna untuk
mengetes alur script-nya, bukan untuk menghasilkan akun.

### Akun GitHub tetap bisa kena flag walau semuanya benar

Tanpa proxy, semua akun datang dari satu IP. GitHub menoleransi beberapa akun,
lalu mulai menampilkan `We detected unusual activity`. Script menanganinya dengan
relaunch memakai fingerprint baru — tapi **tanpa proxy IP-nya tetap sama, jadi
relaunch tidak menolong.** Isi `PROXY_*` di `.env` kalau mau bikin banyak.

Blokir yang datang belakangan juga mungkin: akun jadi, lalu di-suspend setelah
GitHub mengaitkan beberapa akun ke satu IP atau satu pola fingerprint. Tidak
terdeteksi dari dalam script.

### Slider captcha tidak selalu lolos otomatis

Drag-nya dibuat mirip manusia (kurva bezier, ease-in-out, micro-pause, overshoot
lalu koreksi) dan biasanya lolos. Tapi kalau GitHub sedang sensitif — biasanya
setelah beberapa akun dari IP yang sama — mode semi akan meminta kamu
menyelesaikannya manual, dan mode auto men-skip akun itu. Script tidak mencoba
mengakali captcha-nya.

### Mode auto membuang akun yang mentok tanpa bertanya

Itu memang tujuannya, tapi konsekuensinya perlu diketahui: langkah yang gagal
di-skip, jadi satu akun bisa berakhir dengan key dari sebagian situs saja, atau
tidak tersimpan sama sekali kalau yang gagal ada di langkah GitHub. Yang berhasil
tetap masuk `akun.txt` dan 9router; yang gagal hanya muncul sebagai `❌` di log.
Untuk batch pertama di lingkungan baru, pakai semi dulu.

### Key yang hanya tampil sekali tidak bisa diambil ulang

Situs target menampilkan nilai API key satu kali saja. Kalau pembacaan gagal di
ketiga jalurnya (DOM, clipboard, paste), key lama tidak bisa dibaca lagi —
pemulihannya membuat key **baru** setelah hard refresh. Akibatnya bisa ada key
menggantung di akun situs yang tidak tercatat di mana pun. Tidak berbahaya, hanya
sampah.

### Key duplikat ditolak, tapi situs keduanya ikut gagal

Kalau dua situs menghasilkan nilai key yang sama, itu pembacaan yang salah — biasa
karena clipboard OS masih memegang key sebelumnya. Yang dipegang adalah key
pertama (Tabitoken, karena dikerjakan lebih dulu) dan situs kedua dianggap gagal.
Aman untuk data, tapi berarti satu key hilang dari akun itu. Prioritas DOM di atas
clipboard membuat ini jarang terjadi, tidak menghilangkannya.

### Rate limit mail.tm bikin lambat, bukan gagal

mail.tm membatasi 8 request per detik per IP. Interval polling OTP sudah 5 detik
jadi aman, dan 429 diperlakukan sebagai retry. Efeknya hanya OTP yang datang lebih
lambat saat layanannya sibuk.

### Selector bisa basi kapan saja

Situs target dan halaman GitHub bisa berubah tanpa pemberitahuan. Kalau satu
langkah tiba-tiba selalu mentok padahal sebelumnya lancar, kemungkinan besar
selectornya berubah — semuanya ada di satu file,
[bansos/selectors.py](bansos/selectors.py), tiap entry adalah daftar alternatif
yang dicoba berurutan.

### Yang tidak bisa dites otomatis

`python -m bansos.selfcheck` menutupi logika murni dan client HTTP, tapi alur
browser sungguhan (signup GitHub, slider captcha, OAuth, pengambilan key) butuh
membuat akun asli. Jalankan dengan 1 akun untuk mengujinya.

### Belum ada

Bukan rusak, memang belum dikerjakan:

- **Tidak ada paralel.** Akun dikerjakan satu per satu. Beberapa browser sekaligus
  memang lebih cepat, tapi juga lebih cepat kena flag.
- **Tidak ada resume.** Dihentikan di tengah berarti akun yang belum selesai tidak
  dilanjutkan; yang sudah tersimpan di `akun.txt` tetap aman.
- **Key tidak diverifikasi ulang.** 9router memvalidasi sekali saat push dan
  hasilnya hanya dicatat di log. Key yang mati belakangan tidak terdeteksi.
- **`akun.txt` hanya ditambah.** Tidak ada dedupe, tidak ada penghapusan akun mati.

## 🧩 Struktur kode

`bansos.py` di root hanya 20 baris: jalankan bootstrap, lalu serahkan ke paket.
Bootstrap harus selesai sebelum modul lain di-import, karena modul lain memakai
`camoufox` yang mungkin belum terpasang.

```
bansos.py              entry point
run.bat / run.sh       launcher: cek Python, siapkan .env, jalankan
bansos/
  bootstrap.py         cek dependency, download browser, siapkan file
  config.py            Settings dari .env, RunOptions, semua konstanta timeout
  selectors.py         semua selector CSS + pola API key, satu tempat
  errors.py            BotBlocked, EmailRejected, StepSkipped

  browser.py           launch Camoufox, mode tampilan, geometri jendela, proxy
  human.py             delay acak, kurva mouse, drag slider, warmup
  page.py              cari elemen, klik, isi, navigasi, hard refresh, eskalasi
  captcha.py           slider captcha GitHub
  prompt.py            prompt ke user + saklar mode jalan (semi/auto)

  github.py            signup, captcha, OTP, login
  sites.py             consent, OAuth, buat API key, ambil + validasi nilai key
  mail/
    base.py            kontrak MailProvider + logika bersama
    worker.py          inbox pribadi
    mailtm.py          mail.tm
  ninerouter.py        client HTTP dashboard 9router
  storage.py           satu-satunya modul yang menulis akun.txt
  runner.py            satu akun end-to-end + retry saat kena blokir
  cli.py               tanya opsi run, jalankan, ringkas hasil
  selfcheck.py         tes tanpa framework
```

Pemisahannya: `page.py` tidak tahu apa-apa soal GitHub, `github.py` tidak tahu
apa-apa soal 9router, dan `storage.py` satu-satunya yang menyentuh file hasil.
Menambah situs berarti menambah satu entry di `config.py`, bukan menambah fungsi.

## 🔍 Cara kerjanya di dalam

Bagian-bagian yang tidak langsung terlihat dari kodenya. Semua sudah diverifikasi
di browser sungguhan.

<details>
<summary><b>Satu browser = satu IP</b> — kenapa <code>sessid</code> wajib</summary>

Challenge Cloudflare butuh IP yang tidak berpindah dari awal sampai akhir: ambil
halaman → ambil payload dari `/cdn-cgi/challenge-platform/` → kirim jawaban → dapat
cookie `cf_clearance`. Cookie itu terikat ke IP, User-Agent, dan fingerprint TLS
yang mendapatkannya, jadi IP yang berganti di tengah alur membuat challenge
mengulang terus.

Port `823` DataImpulse defaultnya **rotating** — IP ganti setiap request. Yang
menguncinya adalah parameter `sessid`, ditempel ke username dengan pemisah `__`
(dua underscore), key dan value dipisah titik, antar-parameter pakai `;`:

```
http://login__cr.id;sessid.abc123:password@gw.dataimpulse.com:823
```

Dua request lewat proxy, `sessid` dikenali vs tidak:

```
sessid dikenali       -> 78.137.206.171, 78.137.206.171
sessid tidak dikenali -> 191.108.15.228, 109.53.81.82
```

`runner` membuat satu `sessid` per percobaan, jadi satu browser tetap di satu IP
dan retry setelah kena blokir benar-benar mendapat IP baru.
</details>

<details>
<summary><b>Ad blocker dimatikan</b> — uBlock justru memblokir captcha</summary>

Camoufox memasang uBlock Origin secara default; itu dinonaktifkan lewat
`exclude_addons=[DefaultAddons.UBO]`. Skrip analytics yang diblokir uBlock justru
bagian dari mekanisme captcha dan deteksi bot di situs target — kalau diblokir,
halaman bisa menggantung atau menolak OAuth. Addon yang terpasang sendiri juga
bisa terbaca sebagai anomali.

```
uBlock aktif  -> semua skrip ads/analytics diblokir
exclude UBO   -> pagead2.googlesyndication.com, static.doubleclick.net,
                 www.googletagmanager.com semuanya termuat
```
</details>

<details>
<summary><b>Jendela dipatok 1366x720</b> — bukan diacak</summary>

Camoufox mengarang ukuran layar setiap kali dijalankan (1680x1050, 2560x1440,
3440x1440, ...), dan `Screen(...)` hanya **batas** untuk pengacakan itu, bukan
nilai pasti. Jadi geometrinya ditulis langsung ke `config`:

| Properti | Nilai |
| --- | --- |
| `window.outerWidth` / `outerHeight` | 1366 x 720 |
| `screen.width` / `height` | 1366 x 768 |
| `screen.availWidth` / `availHeight` | 1366 x 728 |
| `window.screenX` / `screenY` | jendela di tengah area yang tersedia |

Layarnya 768 piksel, bukan 720, karena `screen.height == screen.availHeight`
berarti tidak ada taskbar sama sekali — CreepJS memakai itu sebagai penanda
headless. 1366x768 juga resolusi laptop Windows paling umum. Rantai
`inner <= outer <= avail <= screen` dijaga konsisten; jendela yang lebih besar
dari layarnya sendiri adalah geometri mustahil. `os` dipatok ke `windows`, karena
layar 1366x768 yang mengaku macOS justru tidak wajar.

```
screen  [1366, 768]   outer  [1366, 720]   inner  [1366, 663]
avail   [1366, 728]   pos    [0, 4]        dpr    1
```
</details>

<details>
<summary><b>Email digenerate setelah captcha lolos</b></summary>

Alamat email baru dibuat setelah slider captcha selesai, bukan di awal. Kalau
captcha atau blokir anti-bot gagal dilewati, tidak ada alamat yang terbuang.
</details>

<details>
<summary><b>Navigasi tidak menunggu <code>networkidle</code></b></summary>

`page.goto()` memakai `wait_until="domcontentloaded"`. GitHub menjaga koneksi
analytics tetap terbuka sehingga jaringan tidak pernah benar-benar idle, dan
`networkidle` akan menggantung sampai timeout — terlihat seperti script hang.
Setelah navigasi, `goto` otomatis memeriksa challenge Cloudflare, jadi tidak ada
halaman yang lolos tanpa diperiksa.
</details>

<details>
<summary><b>Satu jalur eskalasi</b> — hard refresh sebelum menyerah</summary>

Semua langkah yang bisa mentok lewat satu fungsi, `page.retry_after_refresh()`:
coba → hard refresh (jatah `HARD_REFRESH_ATTEMPTS`, default 2) → baru menyerah.
Tanpa itu, urutan tersebut harus ditulis ulang di tiap modul dan gampang terlewat.

Menyerahnya lewat `prompt.ask_retry()`, satu-satunya tempat yang tahu mode jalan:
mode semi bertanya ke user, mode auto mengembalikan "skip" tanpa bertanya. Jadi
tidak ada pemeriksaan `if auto` yang tersebar di modul alur.

Hard refresh-nya bukan `page.reload()` biasa. Playwright tidak punya opsi
bypass-cache, dan `Ctrl+Shift+R` lewat `page.keyboard` tidak menolong karena
tombolnya masuk ke konten halaman, bukan ke UI browser. Yang dikirim browser
sungguhan saat hard refresh adalah header `Cache-Control: no-cache` dan
`Pragma: no-cache` — itu yang dipasang sebentar sebelum reload lalu dilepas lagi,
karena header no-cache yang menempel di setiap request justru anomali.

Dua hal yang membuatnya tidak merusak:

- **Refresh dilewati** untuk langkah yang kehilangan datanya kalau halaman dimuat
  ulang. Klik submit dan pengisian field tidak me-refresh sendiri; lapisan di
  atasnya yang me-refresh lalu mengisi ulang form dari awal.
- **Skip berhenti seketika.** Jawaban `s` (atau keputusan mode auto) dilempar
  sebagai `StepSkipped`, bukan dikembalikan sebagai kegagalan biasa — kalau
  dikembalikan, lapisan retry di atasnya akan memuat ulang halaman dan mengulang
  hal yang sama.
</details>

<details>
<summary><b>Nilai API key dibaca dari DOM</b>, tombol Copy hanya fallback</summary>

Halaman `/keys` dibaca sampai 3 kali (`DOM_READ_ATTEMPTS`) sebelum tombol Copy
disentuh sama sekali. Pembacaan itu mengumpulkan value semua `input`/`textarea`,
atribut `data-clipboard-text`/`data-copy`/`data-value`, dan teks halaman, lalu
mencocokkan pola key.

Alasan DOM jadi jalur utama: clipboard adalah satu sumber milik OS yang dipakai
bersama semua browser, dan klik Copy bisa "berhasil" tanpa menyalin apa pun.
Di run panjang itu berarti key akun sebelumnya masih ada di clipboard dan terbaca
sebagai key akun berikutnya — bug yang tidak menghasilkan error, hanya data salah.

Kalau DOM benar-benar kosong, fallback-nya klik Copy lalu baca clipboard:
`navigator.clipboard.readText()` dulu, dan kalau ditolak, Ctrl+V ke `textarea`
sementara milik script sendiri. Sebelum klik, clipboard dikosongkan dengan
`writeText('')` supaya klik yang gagal terbaca sebagai "clipboard kosong", bukan
mengembalikan key lama. Agar `readText()` jalan, dua pref Firefox diaktifkan di
`browser.py`: `dom.events.asyncClipboard.readText` dan
`dom.events.testing.asyncClipboard` — tanpa keduanya Firefox meminta konfirmasi
"Paste" dari user, yang tidak akan pernah datang di alur otomatis.

```
clipboard OS      : sk-AAAABBBB...LLLL
readText() OS     : 'sk-AAAABBBB...LLLL'
writeText()       : ok
readText() self   : 'sk-ZZZZ1111...abcd'
paste ke textarea : 'sk-ZZZZ1111...abcd'
```

Dua saringan sebelum sebuah nilai diterima sebagai key:

- **Bentuknya** harus berpola `sk-` dengan panjang minimal 40 karakter. Daftar key
  menampilkan versi terpotong (`sk-AbCd1234EfG...`) yang juga cocok polanya; key
  sungguhan 51 karakter sedangkan potongannya sekitar 10-15.
- **Belum pernah muncul** di run ini. Key Tabitoken dan SeekAI tidak mungkin sama,
  dan dua akun tidak mungkin mendapat key identik — nilai yang berulang berarti
  pembacaannya salah, hampir selalu clipboard yang basi. `accept_key` menolaknya,
  jadi key pertama (Tabitoken, yang dikerjakan lebih dulu) yang dipegang dan situs
  kedua dihitung gagal. Tanpa itu, `POST /api/providers` yang kedua akan menimpa
  connection pertama dengan key yang sama.
</details>

<details>
<summary><b>Nama connection 9router dijaga unik</b></summary>

`POST /api/providers` dengan nama yang sudah ada **menimpa** connection lama,
bukan menambah. Daftar nama diambil sekali saat startup; kalau ada tabrakan,
namanya diberi suffix (`user1-tabitoken-2`) dengan peringatan di log. Tanpa ini,
satu nama yang kebetulan sama akan menghapus key yang sudah tersimpan.
</details>

## 🧰 Troubleshooting

| Pesan / gejala | Penyebab & tindakan |
| --- | --- |
| `Please enable JS and disable any ad blocker` | Halaman challenge Cloudflare. Pastikan `PROXY_HOST` masih port `823` dan `PROXY_USER` tidak diubah manual — script menyusun `sessid` sendiri. Kalau paket proxy-mu tidak mendukung `sessid`, pakai port sticky `gw.dataimpulse.com:10000` |
| `We detected unusual activity` | IP + fingerprint sudah ditandai. Script relaunch dengan identitas baru sampai 3 kali. Tanpa proxy IP-nya tetap sama, jadi isi `PROXY_*` di `.env` |
| OTP tidak masuk | `worker`: cek `MAIL_WORKER_PASSWORD` cocok dengan `APP_PASSWORD` di Worker — errornya membedakan password salah (401) dari secret yang belum di-set (503). `mailtm`: hanya lambat karena rate limit, 429 di-retry sendiri |
| `Login 9router 200 tapi cookie auth_token tidak dikirim` | Biasanya `NINEROUTER_URL` salah port — dashboard ada di `20127` |
| `Node id <situs> tidak ada di 9router` | Provider node dihapus atau dibuat ulang dengan id berbeda. Ambil id barunya dari URL halaman provider, perbarui `provider_node_id` di `config.py` |
| Browser tidak muncul di Linux | Set `DISPLAY=:0` di `.env`, atau pilih mode `2` (virtual display) saat run |
| `Please install Xvfb to use headless mode` | Mode virtual dipilih tapi Xvfb belum ada: `sudo apt install xvfb` |
| API key tetap tidak terbaca | Mode semi: tempel sendiri di prompt terakhir. Kalau situsnya mengubah prefix dari `sk-`, lebarkan `API_KEY_PATTERN` di [bansos/selectors.py](bansos/selectors.py) — jangan turunkan `API_KEY_MIN_LENGTH`, itu yang menahan key terpotong ikut terbaca |
| Satu langkah selalu mentok padahal dulu lancar | Selector berubah. Semuanya ada di [bansos/selectors.py](bansos/selectors.py) |
| Banyak akun `❌` tanpa alasan jelas | Kemungkinan jalan di mode auto: langkah yang mentok di-skip tanpa penjelasan panjang. Ulangi satu akun di mode semi untuk melihat langkah mana yang berhenti |

## ✅ Self-check

```powershell
python -m bansos.selfcheck
```

Assert biasa, tanpa framework. Yang diperiksa: syntax username proxy, geometri
jendela + pref clipboard, mapping mode browser, ekstraksi API key (utuh diterima,
terpotong ditolak), penolakan key duplikat antar situs, urutan eskalasi (dua hard
refresh dulu, baru user), mode auto (skip tanpa prompt, jatah refresh tetap penuh),
ekstraksi kode OTP untuk kedua bentuk payload, client mail.tm/worker/9router lewat
`httpx.MockTransport`, format `akun.txt` (header run + baris berlabel situs), dan
label tujuan simpan `RunOptions`.

Alur browser sungguhan tidak ikut — lihat
[Yang tidak bisa dites otomatis](#yang-tidak-bisa-dites-otomatis).

## ➕ Menambah situs baru

Kalau alurnya sama (sign-up → Continue with GitHub → Authorize → `/keys` →
Create API Key), cukup tambah satu entry di `_sites()` pada
[bansos/config.py](bansos/config.py):

```python
Site(
    name="NamaSitus",
    host="namasitus.com",
    signup_url="https://namasitus.com/sign-up",
    provider_node_id="openai-compatible-chat-<uuid dari 9router>",
    model=default_model,
),
```

`provider_node_id` diambil dari URL halaman provider di dashboard 9router.
Kalau selectornya berbeda, tambahkan sebagai alternatif di `SITE` pada
[bansos/selectors.py](bansos/selectors.py) — tiap entry adalah daftar yang dicoba
berurutan.

## 🔐 Catatan keamanan

> [!IMPORTANT]
> `akun.txt` berisi password dan API key dalam bentuk teks biasa. Bersama `.env`,
> keduanya sudah masuk `.gitignore` — jangan pernah di-commit.

- Password worker email dikirim sebagai Bearer token di setiap request, jadi
  `MAIL_WORKER_URL` wajib `https`. Script memperingatkan kalau kamu memakai
  `http` ke host non-lokal.
- Password 9router dibaca dari `.env` dan script selalu login ulang. Tidak ada
  token yang di-hardcode.
- Password GitHub sama untuk semua akun yang dibuat (`GITHUB_PASSWORD`). Kalau
  satu bocor, semuanya bocor.

