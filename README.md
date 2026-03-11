# MiniOpenClaw

MiniOpenClaw is a compact, extensible agent with:
- CLI chat (`agent`)
- Channel gateway (`gateway`)
- Multi-provider LLM support (Gemini/OpenAI/Claude/ARK)
- Local tool execution (file/shell/web search)

## Install

```bash
uv sync
```

## Configuration

Project root has `.env`. Update values there (no manual `source` required; app auto-loads `.env`).

Common fields:
- `MINICLAW_PROVIDER=gemini|openai|claude|ark|openai_compat`
- `MINICLAW_MODEL=...`
- Provider API keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `ARK_API_KEY`)
- Memory:
  - `MINICLAW_MEMORY_ENABLED=true|false`
  - `MINICLAW_MEMORY_PATH=~/.miniopenclaw/memory.json`
  - `MINICLAW_MEMORY_RETRIEVE_K=4`
- Skills:
  - `MINICLAW_SKILL_ENABLED=true|false`
  - `MINICLAW_SKILL_PATHS=.,/absolute/path/to/skills`
  - `MINICLAW_SKILL_SCRIPT_TIMEOUT_SECONDS=10`
- find-skill + MCP flow:
  - `MINICLAW_FIND_SKILL_ENABLED=true|false`
  - `MINICLAW_FIND_SKILL_AUTO_OPEN_LOGIN=true|false`
  - `MINICLAW_FIND_SKILL_SEARCH_CMD='find-skill search "{query}" --json'`
  - `MINICLAW_FIND_SKILL_INSTALL_CMD='find-skill install "{skill_id}"'`
  - `MINICLAW_FIND_SKILL_INVOKE_CMD='find-skill invoke "{skill_id}" --task "{task}" --json'`
  - `MINICLAW_FIND_SKILL_LOGIN_CMD='find-skill login "{skill_id}"'`

## CLI Usage

Interactive mode:

```bash
uv run python -m miniopenclaw agent
```

Interactive mode with logs (tool calls, status):

```bash
uv run python -m miniopenclaw agent --logs
```

One-shot mode:

```bash
uv run python -m miniopenclaw agent -m "hello"
```

### Skill Triggering

Skill files are discovered as `SKILL.md` under `MINICLAW_SKILL_PATHS`.

You can explicitly trigger a skill in conversation:

```text
$frontend-design 帮我做一个登录页
```

or

```text
使用技能 frontend-design 帮我优化页面
```

Use `--logs` to inspect skill/memory traces in `metadata`.

Interactive debug commands:
- `/skills` or `/skills list`
- `/skills refresh`
- `/skills match <text>`
- `/skills show <name>`
- `/skills suggest <purpose>`
- `/skills create <name> [description]`
- `/findskill <query>` or `/findskill <query> || <task>`

`/findskill` workflow:
1. Search skill by query
2. Install matched skill
3. Invoke mapped MCP capability
4. If login URL is detected, auto-open browser for QR/login

If `find-skill` binary is not installed, MiniOpenClaw falls back to local mode:
- search from local `SKILL.md` (using `MINICLAW_SKILL_PATHS`)
- return matched skill guidance and suggested `$skill-name` trigger

If local match also fails, it will try an online GitHub fallback:
- search public repositories by query
- attempt to fetch `SKILL.md` from repo root/`skills/`/`.codex/`
- install to local `./skills/<repo>-remote/`

## Gateway (Multi-Channel)

Run all enabled channels concurrently:

```bash
uv run python -m miniopenclaw gateway
```

If no channel is enabled, gateway exits with an error.

---

## Telegram Integration

### 1) Create bot token

1. Open Telegram and chat with `@BotFather`
2. Run `/newbot`
3. Copy the bot token

### 2) Get your user id (for allowlist)

Use `@userinfobot` (or similar bot) to get your numeric Telegram user id.

### 3) Configure `.env`

```bash
export MINICLAW_TELEGRAM_ENABLED=true
export TELEGRAM_BOT_TOKEN="123456:ABC..."
export TELEGRAM_ALLOW_FROM="123456789"
```

Optional:
- `TELEGRAM_POLL_INTERVAL_SECONDS` (default `1.5`)
- `TELEGRAM_MAX_CHUNK_CHARS` (default `3500`)

### 4) Start gateway

```bash
uv run python -m miniopenclaw gateway
```

### 5) Test

Send a message to your bot from allowed account:
- private chat: message should be replied
- group/thread: message should be routed by `chat_id` + `message_thread_id`

Long replies are automatically split into chunks.

---

## Feishu Integration

### 1) Create app and credentials

In Feishu Open Platform, create app and get:
- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_VERIFY_TOKEN` (if you enable token verification)

### 2) Configure `.env`

```bash
export MINICLAW_FEISHU_ENABLED=true
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="xxx"
export FEISHU_VERIFY_TOKEN="xxx"
export FEISHU_WEBHOOK_HOST="0.0.0.0"
export FEISHU_WEBHOOK_PORT=8765
export FEISHU_WEBHOOK_PATH="/feishu/webhook"
```

Optional allowlist:
- `FEISHU_ALLOW_FROM="ou_xxx,ou_yyy"`
- `FEISHU_ALLOW_CHAT_IDS="oc_xxx,oc_yyy"`

### 3) Expose webhook to public network

Feishu needs a reachable HTTPS callback URL. Example with ngrok:

```bash
ngrok http 8765
```

Set Feishu event callback URL to:

```text
https://<your-ngrok-domain>/feishu/webhook
```

### 4) Start gateway

```bash
uv run python -m miniopenclaw gateway
```

### 5) Test

Send a text message in Feishu chat. Bot should respond in the same chat.

---

## Acceptance Checklist (Week 6-7)

- `gateway` command runs enabled channels concurrently
- Telegram:
  - token works
  - private/group/thread inbound parsing works
  - long message chunking works
  - allowlist works
- Feishu:
  - app credentials/token verification works
  - webhook receives events
  - send API works with auth token
  - user/chat allowlist works
- Same core logic is reused by CLI, Telegram, and Feishu
