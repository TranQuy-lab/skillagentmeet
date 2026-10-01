#!/usr/bin/env python3
"""benchmark_tokens.py - Measure actual token savings of server-side filtering.

Compares token consumption between:
  A) Full transcript fetch (old approach)
  B) Server-side filtered fetch (new approach with since_id/mention/kind)

Uses a simple whitespace tokenizer as baseline (no external deps).
Optionally uses tiktoken if available for GPT-family accurate counts.

Usage:
    python benchmark_tokens.py                              # Run with default fixture
    python benchmark_tokens.py --room <room> --token-file f # Use live room data
    python benchmark_tokens.py --tiktoken                   # Use tiktoken if available
    python benchmark_tokens.py --json                       # JSON output
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from agentmeet import AgentMeet


def simple_tokenize(text: str) -> int:
    """Simple whitespace + punctuation tokenizer (language-agnostic baseline)."""
    # Split on whitespace and common delimiters, count non-empty tokens
    tokens = re.findall(r'[\w]+|[^\s\w]', text, re.UNICODE)
    return len(tokens)


def get_tokenizer(use_tiktoken=False):
    """Return a token counting function."""
    if use_tiktoken:
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")  # GPT-4 / Claude compatible
            def count(text):
                return len(enc.encode(text))
            return count, "tiktoken (cl100k_base)"
        except ImportError:
            print("WARNING: tiktoken not installed, falling back to simple tokenizer", file=sys.stderr)
    return simple_tokenize, "simple (whitespace+punct)"


def create_fixture_messages():
    """Create a realistic fixture of 50 messages simulating a CTF team room."""
    msgs = []
    agents = ["Antigravity", "opencode", "GLM (ZhipuAI)", "muse spark 1.3", "Admin"]
    
    # Simulate typical team chatter
    templates = [
        "💓 [heartbeat] {{\"v\": 1, \"kind\": \"heartbeat\", \"by\": \"{agent}\", \"note\": \"Standby\"}}",
        "📊 [STATUS UPDATE] {agent} → @team: Đã hoàn thành task X, chuyển sang Y.",
        "🔍 [ANALYSIS] {agent}: Phân tích file Z cho kết quả: flag format number{{...}}, cần verify.",
        "✅ [ACK] {agent} → @Lead: Đã nhận task, bắt đầu làm ngay!",
        "⚠️ [BLOCKER] {agent}: Server timeout, không SSH được vào node0447. Cần hỗ trợ.",
        "🎉 [SOLVED] {agent} → @all: Flag number{{abc123}} submitted successfully! +100pts",
        "🤝 [REVIEW] {agent}: Verified pass. Test suite 17/17 green. Good job @dev!",
        "Random chatter about weather and setup configuration that nobody needs to read.",
        "@{target} please check the latest findings in challenges/forensics/dead_drop/",
        "📋 [task] {{\"v\": 1, \"kind\": \"task\", \"title\": \"Fix atomic claim race\", \"owner\": \"{agent}\"}}",
    ]
    
    for i in range(50):
        agent = agents[i % len(agents)]
        template = templates[i % len(templates)]
        target = agents[(i + 1) % len(agents)]
        content = template.format(agent=agent, target=target)
        msgs.append({
            "message_id": i + 1,
            "agent_name": agent,
            "content": content,
            "timestamp": f"2026-09-20T09:{i:02d}:00Z"
        })
    return msgs


def benchmark(messages, tokenizer_fn, filter_agent=None, filter_keyword=None):
    """Run benchmark comparing full vs filtered token counts."""
    # Scenario A: Full transcript
    full_text = json.dumps(messages, ensure_ascii=False)
    full_tokens = tokenizer_fn(full_text)
    
    # Scenario B: Filtered (simulate server-side filtering)
    filtered = messages
    if filter_agent:
        filtered = [m for m in filtered if filter_agent.lower() in m.get("agent_name", "").lower()]
    if filter_keyword:
        filtered = [m for m in filtered if filter_keyword.lower() in m.get("content", "").lower()]
    
    filtered_text = json.dumps(filtered, ensure_ascii=False)
    filtered_tokens = tokenizer_fn(filtered_text)
    
    # Scenario C: Cursor-based (only last 5 messages)
    cursor_msgs = messages[-5:]
    cursor_text = json.dumps(cursor_msgs, ensure_ascii=False)
    cursor_tokens = tokenizer_fn(cursor_text)
    
    savings_ab = (1 - filtered_tokens / full_tokens) * 100 if full_tokens > 0 else 0
    savings_ac = (1 - cursor_tokens / full_tokens) * 100 if full_tokens > 0 else 0
    
    return {
        "full_transcript": {"messages": len(messages), "tokens": full_tokens},
        "filtered": {"messages": len(filtered), "tokens": filtered_tokens, "savings_pct": round(savings_ab, 1)},
        "cursor_last5": {"messages": len(cursor_msgs), "tokens": cursor_tokens, "savings_pct": round(savings_ac, 1)},
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark token savings of server-side filtering")
    parser.add_argument("--room", help="Live room code (default: use fixture)")
    parser.add_argument("--token-file", default=None, help="Credentials file path")
    parser.add_argument("--tiktoken", action="store_true", help="Use tiktoken for accurate GPT token counts")
    parser.add_argument("--filter-agent", help="Filter by agent name")
    parser.add_argument("--filter-keyword", help="Filter by keyword")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    tokenizer_fn, tokenizer_name = get_tokenizer(args.tiktoken)
    
    # Get messages
    if args.room:
        creds_path = args.token_file or os.environ.get("AGENTMEET_CREDS", r"/home/noble-tran/agent-meet_skill\agent_creds.json")
        with open(creds_path, "r", encoding="utf-8") as f:
            creds = json.load(f)
        m = AgentMeet(room=args.room)
        result = m.transcript(limit=100)
        messages = result.get("messages", [])
        source = f"live room {args.room}"
    else:
        messages = create_fixture_messages()
        source = "synthetic fixture (50 msgs)"

    # Run benchmarks
    results = {}
    
    # Baseline: no filter
    results["baseline"] = benchmark(messages, tokenizer_fn)
    
    # With agent filter
    if args.filter_agent:
        results[f"filter_agent={args.filter_agent}"] = benchmark(
            messages, tokenizer_fn, filter_agent=args.filter_agent
        )
    
    # With keyword filter
    if args.filter_keyword:
        results[f"filter_keyword={args.filter_keyword}"] = benchmark(
            messages, tokenizer_fn, filter_keyword=args.filter_keyword
        )
    
    # Standard filters
    for agent in ["Admin", "GLM"]:
        key = f"mentions_{agent}"
        results[key] = benchmark(messages, tokenizer_fn, filter_keyword=f"@{agent}")

    if args.json:
        output = {"tokenizer": tokenizer_name, "source": source, "benchmarks": results}
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print("=" * 65)
        print(f"  TOKEN SAVINGS BENCHMARK")
        print(f"  Tokenizer: {tokenizer_name}")
        print(f"  Source: {source}")
        print("=" * 65)
        
        for name, data in results.items():
            print(f"\n📊 {name}:")
            ft = data["full_transcript"]
            fl = data["filtered"]
            cr = data["cursor_last5"]
            print(f"  Full transcript:  {ft['messages']:>3} msgs → {ft['tokens']:>5} tokens")
            print(f"  Filtered:         {fl['messages']:>3} msgs → {fl['tokens']:>5} tokens (−{fl['savings_pct']}%)")
            print(f"  Cursor (last 5):  {cr['messages']:>3} msgs → {cr['tokens']:>5} tokens (−{cr['savings_pct']}%)")
        
        print("\n" + "=" * 65)


if __name__ == "__main__":
    main()
