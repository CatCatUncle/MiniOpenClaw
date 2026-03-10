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
