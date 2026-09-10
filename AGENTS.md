# AGENTS.md — Kervansaray

Bu repo **iki ajan tarafından paralel** geliştiriliyor (Claude Code + Antigravity).
Kod yazmadan önce **mutlaka** oku:

1. `docs/PARALLEL_WORKFLOW.md` — iş bölümü, kulvar haritası, çakışma kuralları
2. `docs/PARALLEL_STATUS.md` — diğer ajan şu an neye dokunuyor (önce buna yaz)
3. `docs/PROJECT_BRIEF.md` — ne inşa ediliyor, neyin reddedildiği

## Oturum başı ritüeli
```
git fetch && git status && git log --oneline origin/main -5
```
Sonra `docs/PARALLEL_STATUS.md` oku, işini oraya yaz, **önce onu commit et**.

## Commit
- Küçük, sık, hemen push. Yerelde biriktirme.
- Önek: `feat(scope):` / `fix(scope):` / `docs:` (scope: ui/api/llm/db/tools/infra)
- `main`'e force-push yok, paylaşılan geçmişe rebase yok.
- Commit mesajı sonu: `Co-Authored-By: <model> <noreply@anthropic.com>`

## Bilinen tuzaklar
- `~/portfolio/Caddyfile` düzenleme → `docker compose up -d --force-recreate caddy` (reload yetmez, inode).
- `.env` gitignore'da, gerçek API anahtarları var — asla echo'lama, commit'leme.
- `api/static/index.html`, `prompts.py`, `schemas.py` paylaşımlı — dokunmadan STATUS'a yaz.
