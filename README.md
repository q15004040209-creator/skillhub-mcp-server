# skillhub-mcp-server

> 把 SkillHub 上 **80+ 个实战技能** 通过 MCP（Model Context Protocol）协议，自动暴露为任意 AI Agent 可一键调用的工具。
> 一份代码，同时服务 **X-Agent AI MCP Hackathon 2026（开放创新赛道）** 与 **世界 AI 技能锦标赛 WAISC（自成长主题，补官方明确要求的 MCP 接入文件缺口）**。

## 一、定位（Positioning）

SkillHub 已沉淀 80+ 个覆盖编程 / 办公 / 内容创作 / 数据分析 / 安全运维的技能（每个都是一份结构化的 `SKILL.md`：适用场景 / 工作流 / 示例 / 边界 / 技术底座）。但这些技能原本"只能被人读、不能被 Agent 调"。

`skillhub-mcp-server` 是它们的**标准化 MCP 接入层**：用零依赖的纯 Python 实现 MCP over stdio（JSON-RPC 2.0），让 Claude Desktop / Cursor / 任意自研 Agent 能通过标准 MCP 协议，检索、读取、并把任意技能自动包装成可调用的 tool。

## 二、场景（When to use）

- **Agent 在动手前先"查能力"**：与其让 LLM 凭空写一段可能出错的正则/ Dockerfile / 文献综述，不如先 `search_skills("docker 镜像瘦身")`，发现已有成熟技能，直接采纳。
- **多 Agent 协作**：一个"调度 Agent"通过 `list_categories` 了解能力版图，把子任务分派给对应技能 tool。
- **技能即服务（Skill-as-a-Tool）**：`skill_as_tool(slug)` 把任一个技能自动生成 MCP tool schema，是 SkillHub 技能接入 MCP 生态的标准姿势。
- **WAISC 自成长主题契合点**：server 暴露的技能目录可被上层 Agent 持续检索与复用，越用越懂"有哪些现成能力可用"，本身就是一种"越用越懂你"的能力沉淀机制。

## 三、能力（Capabilities）

MCP 工具清单（4 个，tool schema 由 `server.py` 的 `TOOLS` 定义，自动随技能目录更新）：

| 工具 | 作用 |
|---|---|
| `search_skills(query, category?, tag?)` | 按关键词 / 类目 / 标签检索技能，返回 slug、名称、类目、标签、一句话描述，并标注是否已发布 |
| `get_skill(slug)` | 读取某技能完整信息：frontmatter 元数据 + `SKILL.md` 全文（五段结构） |
| `list_categories()` | 返回技能能力版图（类目:数量分布） |
| `skill_as_tool(slug)` | 把任一技能自动包装成可调用的 MCP tool schema（name=slug, description=技能描述, inputSchema 基于语义生成） |

- **零依赖**：仅用 Python 标准库，Python 3.8+ 可直接运行，无 `pip install`。
- **数据驱动**：技能目录来自 `manifest.json`（由 `candidates/` 下全部 `SKILL.md` frontmatter 自动生成），新增技能无需改代码。
- **协议合规**：实现 MCP 2024-11-05 的 `initialize` / `tools/list` / `tools/call`，含 `notifications/initialized`、`ping` 处理。

## 四、技术底座（Tech Stack）

- **传输**：stdio（标准输入/输出），每行一个 JSON-RPC 2.0 消息，符合 MCP 标准传输约定；日志走 stderr 不污染协议流。
- **协议**：`initialize` 协商 `protocolVersion=2024-11-05`，声明 `capabilities.tools`；`tools/list` 返回工具定义；`tools/call` 执行并返回 `content[].text`。
- **检索**：`search_skills` 采用"英文/数字词整体 + 中文字串 2-gram 展开 + 命中数排序"的轻量相关度算法，对中文混合查询鲁棒（如 "docker 镜像 瘦身" 能正确命中 `docker-image-optimizer`）。
- **接入层**：`skill_as_tool` 体现"Skill → MCP tool"的标准化映射，是 SkillHub 技能接入 MCP 生态的关键一环。

## 五、运行说明（Run）

```bash
# 1. 准备：确保 manifest.json 存在（已随仓库提供，含 80+ 技能元数据）
cd compete/x-agent-mcp

# 2. 直接运行（stdio 模式，等待 MCP 客户端连接）
python server.py

# 3. 自检：用内置最小客户端走通 initialize → tools/list → tools/call
python tests/test_client.py
```

接入 Claude Desktop（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "skillhub": {
      "command": "python",
      "args": ["/绝对路径/compete/x-agent-mcp/server.py"]
    }
  }
}
```

## 六、测试样例（Examples）

**示例 1 — 检索技能（输入 → 输出）**

```
→ tools/call: search_skills({"query": "docker 镜像 瘦身"})
← 命中 2 个技能（目录共 88 个）：
  - [✅已发布] docker-image-optimizer  《Docker 镜像瘦身专家》  [dev-programming]  把动辄 1GB+ 的镜像压到最小…
  - [✅已发布] cicd-pipeline-builder  《CI/CD 流水线搭建与红灯排错》  [dev-programming]  …
```

**示例 2 — 把技能包装成 tool（输入 → 输出）**

```
→ tools/call: skill_as_tool({"slug": "docker-image-optimizer"})
← {
     "name": "docker-image-optimizer",
     "description": "把动辄 1GB+ 的镜像压到最小…",
     "inputSchema": {"type":"object","properties":{"task":{"type":"string"}},"required":["task"]},
     "annotations": {"category":"dev-programming","tags":["Docker","镜像优化",…]}
   }
```

**示例 3 — 读取完整技能（输入 → 输出）**

```
→ tools/call: get_skill({"slug": "secret-leak-scanner"})
← {"meta":{…frontmatter…}, "skill_md":"---\nname: secret-leak-scanner\n…全文…"}
```

> 仓库根 `tests/test_client.py` 可一键复现上述三个示例，作为"可运行、可验证"的提交证据。
