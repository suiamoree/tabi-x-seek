# Graph Report - tabi-x-seek  (2026-10-14)

## Corpus Check
- 26 files · ~27,609 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .example 1, .bat 1)

## Summary
- 508 nodes · 1317 edges · 22 communities (18 shown, 4 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 113 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `72447998`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Settings
- page.py
- github.py
- _StubbornLocator
- resolve_locator
- WorkerMail
- cli.py
- sites.py
- base.py
- selfcheck.py
- README.md
- bootstrap.py
- runner.py
- MailProvider
- storage.py
- _FakePage
- check_router_client
- retry_after_refresh
- warmup
- check_retry_escalation
- find_visible
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
- `Deep-link /signup diblokir` --references--> `open_signup()`  [INFERRED]
  README.md → bansos/github.py
- `🔍 Cara kerjanya di dalam` --references--> `GithubAccount`  [INFERRED]
  README.md → bansos/config.py
- `✅ Self-check` --references--> `RunOptions`  [INFERRED]
  README.md → bansos/config.py

## Import Cycles
- None detected.

## Communities (22 total, 4 thin omitted)

### Community 0 - "Settings"
Cohesion: 0.05
Nodes (24): build_proxy(), close(), launch(), available_modes(), build_proxy(), launch(), _launch_kwargs(), mode_label() (+16 more)

### Community 1 - "page.py"
Cohesion: 0.16
Nodes (9): guard(), bot_blocked(), _frames(), has_any_text(), has_selector(), has_text(), on_cloudflare_challenge(), pass_cloudflare() (+1 more)

### Community 2 - "github.py"
Cohesion: 0.13
Nodes (12): EmailRejected, _fill_and_submit(), _fill_form(), _nudge_all(), _on_signup_page(), register(), _submit_form(), _submitted() (+4 more)

### Community 3 - "_StubbornLocator"
Cohesion: 0.13
Nodes (4): _answer(), check_click_retries(), _ClickPage, _StubbornLocator

### Community 5 - "WorkerMail"
Cohesion: 0.17
Nodes (7): WorkerMail, list_messages(), read_code(), list_messages(), read_link(), check_worker_auth_errors(), check_worker_client()

### Community 6 - "cli.py"
Cohesion: 0.09
Nodes (16): _account_count(), _ask_options(), _browser_mode(), _concurrency(), main(), _pick(), _pick_proxy(), _pick_sites() (+8 more)

### Community 7 - "sites.py"
Cohesion: 0.08
Nodes (35): _login_google(), _oauth_once(), human_delay(), click_first_visible(), fill_input(), goto(), _try_click(), wait_for_url_contains() (+27 more)

### Community 8 - "base.py"
Cohesion: 0.10
Nodes (14): _as_text(), extract_code(), plain_text(), poll_for_code(), random_local_part(), random_password(), _epoch(), MailTmMail (+6 more)

### Community 9 - "selfcheck.py"
Cohesion: 0.11
Nodes (17): available_modes(), _launch_kwargs(), mode_label(), new_session_id(), proxy_username(), check_browser_geometry(), check_browser_modes(), check_github_account() (+9 more)

### Community 10 - "README.md"
Cohesion: 0.06
Nodes (31): GithubAccount, Akun GitHub tetap bisa kena flag walau semuanya benar, Akun mail.tm langsung kena ban GitHub, 🧭 Alur kerja, 🚨 Batasan & known issues, Belum ada, 🔐 Catatan keamanan, Deep-link /signup diblokir (+23 more)

### Community 11 - "bootstrap.py"
Cohesion: 0.27
Nodes (7): _browser_ready(), _fetch_browser(), _install_missing(), _missing_packages(), run(), _run(), use_utf8_stdout()

### Community 12 - "runner.py"
Cohesion: 0.14
Nodes (9): Site, BotBlocked, RateLimited, StepSkipped, _flush(), _push_keys(), _register_key(), _save() (+1 more)

### Community 13 - "MailProvider"
Cohesion: 0.13
Nodes (5): _fill_otp(), submit_otp(), MailProvider, new_fresh_address(), process_account()

### Community 14 - "storage.py"
Cohesion: 0.19
Nodes (5): check_storage(), append_account(), begin_run(), _clean(), _write()

### Community 16 - "check_router_client"
Cohesion: 0.46
Nodes (4): check_router_client(), _mailtm_handler(), _router_handler(), _worker_handler()

### Community 17 - "retry_after_refresh"
Cohesion: 0.15
Nodes (12): _do_login(), login(), on_login_page(), open_signup(), _attempt(), reload(), _reload_once(), retry_after_refresh() (+4 more)

### Community 19 - "check_retry_escalation"
Cohesion: 0.29
Nodes (3): check_retry_escalation(), _fails(), _run_escalation_cases()

### Community 20 - "find_visible"
Cohesion: 0.17
Nodes (8): _gone(), handle_slider(), _slide_until_gone(), _wait_for_container(), drag_slider(), find_visible(), hard_reload(), _current_input_value()

## Knowledge Gaps
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Settings` to `selfcheck.py`, `runner.py`, `MailProvider`, `cli.py`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `Settings` (e.g. with `build_proxy()` and `launch()`) actually correct?**
  _`Settings` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Should `Settings` be split into smaller, more focused modules?**
  _Cohesion score 0.05251141552511415 - nodes in this community are weakly interconnected._
- **Why does `🔍 Cara kerjanya di dalam` connect `retry_after_refresh` to `page.py`, `README.md`, `runner.py`, `sites.py`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `NineRouter` (e.g. with `add_codebuddy()` and `_wait_new_account()`) actually correct?**
  _`NineRouter` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `github.py` be split into smaller, more focused modules?**
  _Cohesion score 0.13405797101449277 - nodes in this community are weakly interconnected._
- **Why does `NineRouter` connect `Settings` to `check_router_client`, `selfcheck.py`, `runner.py`, `MailProvider`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._