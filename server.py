#!/usr/bin/env python3
# skillhub-mcp-server —— 把 SkillHub 技能目录暴露为 MCP 工具
#
# 零依赖（仅 Python 标准库）。通过 stdio 上的 JSON-RPC 2.0 实现 MCP 协议
# （协议版本 2024-11-05），让任意 MCP 客户端（Claude Desktop / Cursor /
# 自定义 Agent）能够：
#   1. search_skills   按关键词 / 类目 / 标签检索 80+ 个技能
#   2. get_skill       读取某个技能完整的 SKILL.md（五段结构）
#   3. list_categories 查看技能能力版图（类目分布）
#   4. skill_as_tool   把任意技能自动包装成一个可调用的 MCP tool schema
#
# 这是 SkillHub 技能接入 MCP 生态的"标准化接入层"：
# 一份代码同时服务 X-Agent MCP 黑客松（开放创新赛道）与 WAISC 锦标赛
# （官方明确把 MCP Server 代码 + tool schema 列为建议交付物）。
import sys, os, json

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "manifest.json")
# candidates 目录与 x-agent-mcp 同级于 skillhub-publish 根
ROOT = os.path.dirname(os.path.dirname(HERE))
SKILLS_DIR = os.path.join(ROOT, "candidates")
PROTOCOL_VERSION = "2024-11-05"


def log(*a):
    # 日志写 stderr，避免污染 stdout 的 JSON-RPC 流
    print("[skillhub-mcp]", *a, file=sys.stderr)


try:
    with open(MANIFEST, encoding="utf-8") as f:
        SKILLS = json.load(f)
except Exception as e:  # pragma: no cover
    log("manifest load failed:", e)
    SKILLS = []
BY_SLUG = {s["slug"]: s for s in SKILLS}

TOOLS = [
    {
        "name": "search_skills",
        "description": "在 SkillHub 技能目录中按关键词/类目/标签检索可用技能。返回匹配技能的 slug、名称、类目、标签与一句话描述，并标注是否已发布。Agent 在动手前应先用它发现'有没有现成能力可用'。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言或关键词，匹配技能名/描述/标签"},
                "category": {"type": "string", "description": "可选，限定类目，如 dev-programming / content-creation / data-analysis"},
                "tag": {"type": "string", "description": "可选，限定单个标签"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_skill",
        "description": "读取指定 slug 技能的完整信息：frontmatter 元数据 + SKILL.md 全文（适用场景/工作流/示例/边界/技术底座）。用于深入了解某个技能后再决定是否采用。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "技能 slug，如 literature-review-assistant"},
            },
            "required": ["slug"],
        },
    },
    {
        "name": "list_categories",
        "description": "返回技能目录的类目分布统计（类目:数量），帮助快速了解能力版图。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "skill_as_tool",
        "description": "把任意一个技能自动包装成一个可调用的 MCP tool schema（name=slug, description=技能描述, inputSchema 基于技能语义生成）。体现'把 Skill 自动暴露为 Agent 可调用 tool'的核心能力，是 SkillHub 技能接入 MCP 生态的标准化接入层。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "要包装成 tool 的技能 slug"},
            },
            "required": ["slug"],
        },
    },
]


import re


def _tokens(q):
    """把查询拆成匹配单元：英文/数字词整体保留；中文字串整体 + 2-gram 展开，
    使 '镜像瘦身' 也能命中含 '镜像'/'瘦身' 的技能。"""
    q = (q or "").lower()
    raw = re.findall(r"[a-z0-9_]+|[一-鿿]+", q)
    out = []
    for t in raw:
        out.append(t)
        if not re.match(r"[a-z0-9_]+$", t) and len(t) >= 2:
            for i in range(len(t) - 1):
                out.append(t[i:i + 2])
    return [x for x in out if x]


def search_skills(query, category=None, tag=None):
    q = (query or "").strip()
    toks = _tokens(q)
    res = []
    for s in SKILLS:
        if category and s.get("category") != category:
            continue
        if tag and tag not in s.get("tags", []):
            continue
        hay = " ".join([
            s.get("name", ""), s.get("displayName", ""),
            s.get("description", ""), " ".join(s.get("tags", [])),
        ]).lower()
        if toks:
            hit = sum(1 for t in toks if t in hay)
            if hit == 0:
                continue
            s = dict(s)
            s["_score"] = hit
        res.append(s)
    if toks:
        res.sort(key=lambda x: x.get("_score", 0), reverse=True)
    return res


def get_skill(slug):
    s = BY_SLUG.get(slug)
    if not s:
        return None
    md = None
    p = os.path.join(SKILLS_DIR, slug, "SKILL.md")
    if os.path.isfile(p):
        try:
            md = open(p, encoding="utf-8").read()
        except Exception:
            md = None
    return {"meta": s, "skill_md": md}


def skill_as_tool(slug):
    s = BY_SLUG.get(slug)
    if not s:
        return None
    return {
        "name": s["slug"],
        "description": s.get("description", ""),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": f"针对『{s.get('displayName', s['slug'])}』的具体任务描述",
                },
            },
            "required": ["task"],
        },
        "annotations": {"category": s.get("category"), "tags": s.get("tags", [])},
    }


def call_tool(name, args):
    if name == "search_skills":
        r = search_skills(args.get("query", ""), args.get("category"), args.get("tag"))
        out = [f"命中 {len(r)} 个技能（目录共 {len(SKILLS)} 个）："]
        for s in r[:20]:
            flag = "✅已发布" if s.get("published") else "📦候选"
            out.append(
                f"- [{flag}] {s['slug']}  《{s.get('displayName','')}》  [{s.get('category','')}]  {s.get('description','')[:56]}"
            )
        if len(r) > 20:
            out.append(f"... 其余 {len(r)-20} 个省略")
        return "\n".join(out)
    if name == "list_categories":
        cats = {}
        for s in SKILLS:
            cats[s.get("category", "?")] = cats.get(s.get("category", "?"), 0) + 1
        return "类目分布：\n" + "\n".join(
            f"- {k}: {v}" for k, v in sorted(cats.items(), key=lambda i: -i[1])
        )
    if name == "get_skill":
        g = get_skill(args.get("slug", ""))
        if not g:
            return f"未找到 slug={args.get('slug')} 的技能"
        meta = g["meta"]
        body = g["skill_md"] or "（本地未找到 SKILL.md 全文，仅返回元数据）"
        return json.dumps(meta, ensure_ascii=False, indent=2) + "\n\n--- SKILL.md ---\n" + body
    if name == "skill_as_tool":
        t = skill_as_tool(args.get("slug", ""))
        if not t:
            return f"未找到 slug={args.get('slug')} 的技能"
        return json.dumps(t, ensure_ascii=False, indent=2)
    raise ValueError(f"未知工具: {name}")


def handle(req):
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "skillhub-mcp-server", "version": "1.0.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})
        try:
            text = call_tool(name, args)
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"content": [{"type": "text", "text": text}], "isError": False},
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"content": [{"type": "text", "text": f"ERROR: {e}"}], "isError": True},
            }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    # notifications/initialized 等无 id，忽略
    return None


def main():
    log("skillhub-mcp-server started, indexed skills:", len(SKILLS))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        if "id" not in req:  # notification, 不回响应
            continue
        resp = handle(req)
        if resp:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
