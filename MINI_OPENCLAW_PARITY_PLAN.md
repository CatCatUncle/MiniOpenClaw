# MiniOpenClaw 能力建设任务拆解（执行版）

目标：实现一个“迷你版但能力完整”的 Agent，支持 CLI + 多渠道（Telegram、飞书等）、多 Provider、工具调用、记忆、调度、可发布。

## 0. 范围定义（先定边界）

### 对标能力清单
- [ ] CLI 交互（稳定输入、流式输出、slash 命令）
- [ ] 会话与记忆（多轮上下文、持久化、压缩）
- [ ] Provider 抽象（至少 Gemini + OpenAI 兼容）
- [ ] 工具调用（文件、shell、安全边界）
- [ ] 多渠道网关（Telegram、飞书）
- [ ] 定时任务（Cron）
- [ ] 技能系统（SKILL.md + 动态加载）
- [ ] 配置系统（config.json + env 覆盖）
- [ ] 测试、日志、发布

验收：以上 9 项全部具备最小可用实现。

---

## 1. 架构阶段（Week 1）

### 1.1 目录与模块骨架
- [x] 新建 `miniopenclaw/` 包结构：
  - [x] `core/`（agent loop, router, events）
  - [x] `providers/`
  - [x] `channels/`
  - [x] `session/`
  - [x] `memory/`
  - [x] `tools/`
  - [x] `skills/`
  - [x] `cron/`
  - [x] `config/`
  - [x] `cli/`
- [x] `__main__.py` + Typer 命令入口

验收：`uv run python -m miniopenclaw --help` 能工作。

### 1.2 统一消息协议（关键）
- [x] 定义 `MessageEvent`（channel/user/thread/content/media/ts）
- [x] 定义 `AgentResponse`（text/chunks/tool_calls/status）
- [x] 统一“渠道入站 -> 核心 -> 渠道出站”数据结构

验收：CLI、Telegram、飞书都可复用同一 core 接口。

---

## 2. CLI 与会话阶段（Week 2）

### 2.1 CLI 稳定化
- [x] `prompt_toolkit` + `FileHistory`
- [x] `patch_stdout` 处理流式输出
- [x] 终端状态恢复（防退格异常）
- [x] 统一输出样式（`🦞 miniOpenClaw`）

### 2.2 会话管理
- [x] `SessionManager`（按 `channel:user:thread` 隔离）
- [x] 会话持久化（JSON/SQLite）
- [x] 上下文裁剪（轮数 + 字符上限）
- [x] `/clear /history /session` 命令

验收：同一用户上下文连续可用，重启后可恢复。

---

## 3. Provider 阶段（Week 3）

### 3.1 Provider 抽象
- [x] `BaseProvider`：`generate()` / `stream_generate()`
- [x] `GeminiProvider`（AICodeMirror base_url）
- [x] `OpenAICompatProvider`（兼容 OpenRouter/vLLM）
- [x] Provider 工厂（按 config 选择）

### 3.2 鲁棒性
- [x] 超时、重试（指数退避）
- [x] 错误分级（认证/限流/网络/服务）
- [x] 统一错误提示与日志字段

验收：切换 provider 不改 core 代码。

---

## 4. 工具与 Agent Loop 阶段（Week 4-5）

### 4.1 工具系统
- [x] Tool schema（name/description/json schema）
- [x] 执行器（validate -> run -> summarize）
- [x] 首批工具：
  - [x] 读文件
  - [x] 写文件
  - [x] shell（白名单）
  - [x] web fetch（可选）

### 4.2 安全边界
- [x] 工作目录沙箱限制
- [x] 命令白名单 + 危险命令阻断
- [x] 高风险操作确认机制

### 4.3 Agent 循环
- [x] `plan -> act -> observe` 最大步数
- [x] 工具失败恢复策略
- [x] 用户中断处理

验收：可完成“读文件->修改->保存->反馈”的闭环任务。

---

## 5. 多渠道阶段（Week 6-7）

### 5.1 渠道抽象
- [x] `BaseChannel`：`start/stop/send_message`
- [x] `ChannelManager`：注册、启停、健康检查
- [x] `Gateway` 命令：并发运行所有启用渠道

### 5.2 Telegram 接入
- [x] Bot token 配置
- [x] 入站消息解析（私聊/群聊/thread）
- [x] 出站文本与长消息分片
- [x] 用户白名单 `allowFrom`

### 5.3 飞书接入
- [x] App credentials 配置
- [x] webhook/event 处理
- [x] 消息发送与鉴权
- [x] 用户/群权限策略

验收：同一个 core 对话逻辑，CLI/Telegram/飞书均可回复。

---

## 6. 记忆与技能阶段（Week 8-9）

### 6.1 记忆系统
- [ ] 短期记忆（当前会话）
- [ ] 长期记忆（摘要 + 标签 + 检索）
- [ ] 记忆压缩与污染防护

### 6.2 技能系统
- [ ] `SKILL.md` 发现与加载
- [ ] 技能触发规则（显式/意图匹配）
- [ ] 技能脚本执行隔离

验收：能够在对话中调用指定技能并产出可追踪日志。

---

## 7. 调度与后台任务阶段（Week 10）

### 7.1 Cron 服务
- [ ] 任务定义（自然语言 -> cron 表达式）
- [ ] 任务持久化
- [ ] 执行与重试策略

### 7.2 通知回投
- [ ] 在原渠道线程回投结果
- [ ] 失败告警

验收：可创建一个“每日提醒”并按时发送。

---

## 8. 工程化阶段（Week 11-12）

### 8.1 配置与命令
- [ ] `onboard` 初始化配置
- [ ] `agent`、`gateway`、`channels login` 等命令
- [ ] 环境变量覆盖机制

### 8.2 测试
- [ ] 单元测试：session/router/provider/tool
- [ ] 集成测试：mock provider + mock channel
- [ ] 回归测试：CLI 快照

### 8.3 观测与发布
- [ ] 结构化日志（request_id/session_id/channel）
- [ ] 打包发布（entry point）
- [ ] CHANGELOG + 版本语义化

验收：新机器按 README 可 10 分钟跑通 CLI + Telegram。

---

## 9. 优先级与依赖（执行顺序）

P0（必须）：架构、CLI、会话、provider 抽象  
P1（高）：工具系统、agent loop、安全边界  
P2（高）：Telegram、飞书网关  
P3（中）：记忆、技能、cron  
P4（中）：测试、发布、可观测性

依赖关系：
- 渠道接入依赖 `MessageEvent` 协议稳定
- 工具调用依赖 provider 支持工具指令格式
- 记忆系统依赖 session 管理
- cron 回投依赖 channel manager

---

## 10. 你可以马上开工的前三个任务

1. `Task-001`：创建 `miniopenclaw` 包结构 + CLI 入口（半天）
2. `Task-002`：实现 `SessionManager` 与本地持久化（1 天）
3. `Task-003`：抽象 `BaseProvider` 并迁移当前 Gemini 代码（1 天）

完成这 3 个后，再做 Telegram/飞书不会返工。
