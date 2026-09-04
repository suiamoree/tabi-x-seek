"""Semua selector CSS di satu tempat — website berubah, cuma file ini disentuh.

Urutan tiap list = urutan percobaan: class stabil → atribut → teks.
"""

from __future__ import annotations

import re

GITHUB_SIGNUP_URL = "https://github.com/signup"

GITHUB_SIGNUP = {
    "email_input": ["input#email", "input[name='user[email]']", "input[autocomplete='email']"],
    "password_input": ["input#password", "input[name='user[password]']"],
    "username_input": ["input#login", "input[name='user[login]']"],
    # GitHub sering merender ulang label ("Create account" bisa ada di dalam
    # span/svg), jadi teks jadi opsi terakhir.
    "submit_button": [
        "button.js-octocaptcha-form-submit",
        "button.signup-form-fields__button",
        "button[type='submit'][aria-describedby='terms-of-service']",
        "button[type='submit']:has(span.Button-label)",
        "button:has-text('Create account')",
        "span.Button-label:has-text('Create account')",
        "form button[type='submit']",
    ],
    "signup_link": ["a[href='/signup']", "a[href*='/signup']"],
}

GITHUB_LOGIN = {
    "login_input": ["input#login_field", "input[name='login']", "input.js-login-field"],
    "password_input": ["input#password", "input[name='password']"],
    "submit_button": ["input[value='Sign in']", ".js-sign-in-button"],
}

SITE = {
    # Checkbox "I have read and agree to the User Agreement" (SeekAI). Yang
    # clickable adalah span[role=checkbox]; input#legal-consent disembunyikan
    # lewat clip-path jadi tidak bisa di-klik langsung.
    "consent_checkbox": [
        "span[role='checkbox'][aria-labelledby='legal-consent-label']",
        "span[data-slot='checkbox'][role='checkbox']",
        "label[for='legal-consent']",
    ],
    "github_continue": ["button:has-text('Continue with GitHub')", "button:has(svg[role='img'])"],
    # Halaman OAuth GitHub punya 2 button name='authorize': Cancel (value=0,
    # duluan di DOM) dan Authorize (value=1). Tanpa filter value, .first = Cancel.
    "github_authorize": [
        "button[name='authorize'][value='1']",
        "button.js-oauth-authorize-btn",
        "form button[type='submit']:has-text('Authorize')",
    ],
    "create_key": ["button:has-text('Create API Key')", "button:has(svg.lucide-plus)"],
    "key_name": ["input[placeholder='Enter a name']", "input[name='name']"],
    "save": ["button:has-text('Save changes')"],
    "copy_key": [
        "button:has(svg.lucide-copy)",
        "button:has-text('Copy')",
        "button[aria-label*='opy']",
        "button[title*='opy']",
        "[data-base-ui-tooltip-trigger]",
    ],
}

# Bentuk API key yang dikeluarkan situs target: `sk-` + 48 karakter alnum.
# Dipakai untuk membaca key langsung dari DOM, jadi tombol Copy + izin clipboard
# bukan satu-satunya jalan.
# ponytail: dipatok prefix `sk-` karena kedua situs memakainya. Situs baru dengan
# prefix lain → lebarkan pola ini, bukan menurunkan API_KEY_MIN_LENGTH.
API_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{20,}")

# Panjang minimum agar sebuah kandidat dianggap key utuh. Daftar key menampilkan
# versi terpotong (`sk-IEyzjbnS4GP...`) yang juga cocok dengan pola di atas; key
# sungguhan 51 karakter sedangkan potongannya ~10-15, jadi 40 memisahkan keduanya
# dengan jarak aman.
API_KEY_MIN_LENGTH = 40

# Slider captcha GitHub (octocaptcha) — container = track, handle = yang di-drag.
SLIDER = {
    "container": [".sliderContainer", "[class*='sliderContainer']", "#slider-captcha"],
    "handle": [".slider", "[class*='sliderHandle']", "[role='slider']"],
}

# Kotak launch code 8 digit; muncul saat form signup sukses.
OTP_INPUTS = [
    "#launch-code-0",
    "input[id^='launch-code']",
    "input[aria-label*='digit']",
]

# Interstitial Cloudflare. DOM id diperiksa lebih dulu supaya teks halaman biasa
# yang kebetulan memuat kata serupa tidak salah tertangkap.
CLOUDFLARE_CHALLENGE = [
    "iframe[src*='challenges.cloudflare.com']",
    "#challenge-running",
    "#challenge-stage",
    "#cf-challenge-running",
    "[id^='cf-chl-widget']",
]
CLOUDFLARE_TEXTS = [
    "Please enable JS and disable any ad blocker",
    "Verifying you are human",
    "Just a moment",
]

# Halaman blokir anti-bot GitHub; tidak bisa dilewati dengan retry, harus ganti
# IP/fingerprint. Dideteksi supaya tidak terus menabrak selector.
BOT_BLOCK_TEXTS = [
    "We detected unusual activity",
    "unusual activity from your device or network",
]

# GitHub menolak sebagian domain temp-mail. Errornya muncul di validasi field,
# lebih baik berhenti di situ daripada membuang satu captcha yang sudah lolos.
EMAIL_REJECTED_TEXTS = [
    "Email is invalid or already taken",
    "email address is invalid",
    "not allowed to be used",
]

# Toast saat OAuth start ditolak (captcha / rate limit) → butuh bantuan user.
OAUTH_FAILED_TEXT = "Failed to start GitHub login"
