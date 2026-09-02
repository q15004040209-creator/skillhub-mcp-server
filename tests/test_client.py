#!/usr/bin/env python3
# 最小 MCP 客户端：验证 skillhub-mcp-server 可走通 initialize → tools/list → tools/call。
# 运行：python tests/test_client.py
import subprocess, json, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SERVER = os.path.join(ROOT, "server.py")


def main():
    p = subprocess.Popen(
        [sys.executable, SERVER],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
    )

    def send(obj):
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()

    def recv():
        line = p.stdout.readline()
        return json.loads(line) if line.strip() else None

    # 1) initialize
    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                     "clientInfo": {"name": "test-client", "version": "1.0"}}})
    r = recv()
    print("[initialize] serverInfo =", r["result"]["serverInfo"],
          "| protocol =", r["result"]["protocolVersion"])

    # 2) initialized notification (无响应)
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    # 3) tools/list
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    r = recv()
    print("[tools/list] tools =", [t["name"] for t in r["result"]["tools"]])

    # 4) tools/call: search_skills
    send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
          "params": {"name": "search_skills", "arguments": {"query": "docker 镜像 瘦身"}}})
    r = recv()
    print("\n[search_skills] 返回前 600 字：\n" + r["result"]["content"][0]["text"][:600])

    # 5) tools/call: list_categories
    send({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
          "params": {"name": "list_categories", "arguments": {}}})
    r = recv()
    print("\n[list_categories]：\n" + r["result"]["content"][0]["text"])

    # 6) tools/call: skill_as_tool
    send({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
          "params": {"name": "skill_as_tool", "arguments": {"slug": "docker-image-optimizer"}}})
    r = recv()
    print("\n[skill_as_tool] 自动生成的 tool schema 前 400 字：\n" + r["result"]["content"][0]["text"][:400])

    # 7) tools/call: get_skill
    send({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
          "params": {"name": "get_skill", "arguments": {"slug": "secret-leak-scanner"}}})
    r = recv()
    print("\n[get_skill] 返回长度 =", len(r["result"]["content"][0]["text"]), "字符")

    p.stdin.close()
    p.wait()
    print("\n[DONE] server exit code =", p.returncode)


if __name__ == "__main__":
    main()
