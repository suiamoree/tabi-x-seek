# Graph Report - tabi-x-seek  (2026-10-14)

## Corpus Check
- 26 files · ~27,779 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .example 1, .bat 1)

## Summary
- 512 nodes · 1330 edges · 16 communities (15 shown, 1 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 113 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `72447998`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- browser.py
- MailTmMail
- page.py
- _FakePage
- launch
- WorkerMail
- Settings
- sites.py
- base.py
- selfcheck.py
- README.md
- bootstrap.py
- runner.py
- storage.py
- check_router_client
- run.sh

## God Nodes (most connected - your core abstractions)
1. `human_delay()` - 35 edges
2. `Settings` - 34 edges
3. `click_first_visible()` - 28 edges
4. `NineRouter` - 26 edges
5. `find_visible()` - 24 edges
6. `Site` - 22 edges
7. `main()` - 22 edges
8. `collect_key()` - 21 edges
9. `goto()` - 20 edges
10. `MailProvider` - 18 edges

## Surprising Connections (you probably didn't know these)
- `➕ Menambah situs baru` --references--> `_sites()`  [INFERRED]
  README.md → bansos/config.py
- `Akun mail.tm langsung kena ban GitHub` --references--> `EmailRejected`  [INFERRED]
  README.md → bansos/errors.py
- `🩹 Kalau sebuah langkah gagal` --references--> `StepSkipped`  [INFERRED]
  README.md → bansos/errors.py
- `Deep-link /signup diblokir` --references--> `open_signup()`  [INFERRED]
  README.md → bansos/github.py
- `🔍 Cara kerjanya di dalam` --references--> `GithubAccount`  [INFERRED]
  README.md → bansos/config.py

## Import Cycles
- None detected.

## Communities (16 total, 1 thin omitted)

### Community 0 - "browser.py"
Cohesion: 0.12
Nodes (9): close(), new_session_id(), available_modes(), build_proxy(), launch(), _launch_kwargs(), mode_label(), new_session_id() (+1 more)

### Community 1 - "MailTmMail"
Cohesion: 0.18
Nodes (5): MailTmMail, list_messages(), read_code(), list_messages(), read_link()

### Community 2 - "page.py"
Cohesion: 0.06
Nodes (39): _gone(), handle_slider(), _slide_until_gone(), _wait_for_container(), EmailRejected, _fill_and_submit(), _fill_form(), _nudge_all() (+31 more)

### Community 3 - "_FakePage"
Cohesion: 0.06
Nodes (9): set_auto(), _answer(), check_auto_mode_skips(), check_click_retries(), _ClickPage, _fails(), _FakeLocator, _FakePage (+1 more)

### Community 4 - "launch"
Cohesion: 0.22
Nodes (6): available_modes(), launch(), _launch_kwargs(), mode_label(), check_browser_geometry(), check_browser_modes()

### Community 5 - "WorkerMail"
Cohesion: 0.16
Nodes (7): poll_for_code(), WorkerMail, list_messages(), list_messages(), read_link(), check_worker_auth_errors(), check_worker_client()

### Community 6 - "Settings"
Cohesion: 0.07
Nodes (21): _account_count(), _ask_options(), _browser_mode(), _concurrency(), main(), _pick(), _pick_proxy(), _pick_sites() (+13 more)

### Community 7 - "sites.py"
Cohesion: 0.06
Nodes (44): add_codebuddy(), _login_google(), _oauth_once(), _wait_new_account(), _do_login(), login(), on_login_page(), human_delay() (+36 more)

### Community 8 - "base.py"
Cohesion: 0.16
Nodes (8): _as_text(), extract_code(), plain_text(), random_local_part(), random_password(), _epoch(), read_code(), check_mail_parsing()

### Community 9 - "selfcheck.py"
Cohesion: 0.13
Nodes (14): build_proxy(), proxy_username(), check_github_account(), check_key_extraction(), check_key_uniqueness(), check_masked_key_rejected(), check_proxy(), check_proxy_override() (+6 more)

### Community 10 - "README.md"
Cohesion: 0.06
Nodes (30): Akun GitHub tetap bisa kena flag walau semuanya benar, Akun mail.tm langsung kena ban GitHub, 🧭 Alur kerja, 🚨 Batasan & known issues, Belum ada, 🔐 Catatan keamanan, Deep-link /signup diblokir, 📤 Hasil (+22 more)

### Community 11 - "bootstrap.py"
Cohesion: 0.18
Nodes (7): _browser_ready(), _fetch_browser(), _install_missing(), _missing_packages(), run(), _run(), use_utf8_stdout()

### Community 12 - "runner.py"
Cohesion: 0.05
Nodes (20): GithubAccount, RunOptions, Site, BotBlocked, RateLimited, StepSkipped, _fill_otp(), submit_otp() (+12 more)

### Community 14 - "storage.py"
Cohesion: 0.19
Nodes (5): check_storage(), append_account(), begin_run(), _clean(), _write()

### Community 16 - "check_router_client"
Cohesion: 0.24
Nodes (6): check_mailtm_client(), check_router_client(), check_router_login_without_cookie(), _mailtm_handler(), _router_handler(), _worker_handler()

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Settings` to `browser.py`, `launch`, `sites.py`, `selfcheck.py`, `runner.py`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `Settings` (e.g. with `build_proxy()` and `launch()`) actually correct?**
  _`Settings` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Should `browser.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11956521739130435 - nodes in this community are weakly interconnected._
- **Why does `🔍 Cara kerjanya di dalam` connect `page.py` to `README.md`, `runner.py`, `sites.py`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `NineRouter` (e.g. with `add_codebuddy()` and `_wait_new_account()`) actually correct?**
  _`NineRouter` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `page.py` be split into smaller, more focused modules?**
  _Cohesion score 0.056962025316455694 - nodes in this community are weakly interconnected._
- **Why does `NineRouter` connect `runner.py` to `check_router_client`, `selfcheck.py`, `Settings`, `sites.py`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._