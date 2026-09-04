@echo off
setlocal

rem Launcher Windows: cari Python, siapkan .env, jalankan.
rem Bootstrap di dalam bansos.py yang memasang dependency dan mengunduh browser,
rem jadi di sini cukup memastikan interpreternya ada dan .env sudah dibuat.

cd /d "%~dp0"

set "PY="
for %%C in (py python python3) do (
    if not defined PY (
        where %%C >nul 2>nul && set "PY=%%C"
    )
)

if not defined PY (
    echo [X] Python tidak ditemukan di PATH.
    echo     Pasang Python 3.10+ dari https://www.python.org/downloads/
    echo     dan centang "Add Python to PATH" saat install.
    pause
    exit /b 1
)

rem 'py' butuh -3 supaya tidak memilih Python 2 kalau keduanya terpasang.
if /i "%PY%"=="py" set "PY=py -3"

if not exist ".env" (
    if exist ".env.example" (
        echo [!] .env belum ada - dibuat dari .env.example
        copy /y ".env.example" ".env" >nul
        echo     Isi dulu GITHUB_PASSWORD dan NINEROUTER_PASSWORD, lalu jalankan lagi.
        notepad ".env"
        pause
        exit /b 1
    )
    echo [X] .env dan .env.example tidak ada.
    pause
    exit /b 1
)

%PY% bansos.py %*
set "CODE=%ERRORLEVEL%"

rem Jendela dibiarkan terbuka: dobel-klik dari Explorer akan menutupnya seketika
rem dan pesan errornya tidak terbaca.
echo.
echo Selesai dengan exit code %CODE%.
pause
exit /b %CODE%
