#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentMeet - Leader Election CLI & Protocol Engine (Standard Library Only)
Hỗ trợ quy trình bầu chọn Trưởng nhóm (Team Lead / Coordinator) cho nhóm >= 3-4 agents:
  - nominate: Đề cử ứng viên kèm lý do kỹ thuật
  - vote: Bỏ phiếu cho ứng viên (chuẩn hóa candidate_id)
  - tally: Đọc transcript phòng họp, kiểm phiếu và xử lý Tie-break
  - declare: Tuyên bố chính thức Trưởng nhóm đắc cử
  - status: Kiểm tra Trưởng nhóm hiện tại của phòng họp
Tương thích 100% với agentmeet.protocol envelope.
"""

from __future__ import annotations

import sys
import os
import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# Đưa thư mục gốc của package vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet import load_credentials, DEFAULT_BASE_URL
from agentmeet.protocol import (
    KIND_LEAD,
    decode,
    encode,
    tally_lead,
)

EXIT_OK = 0
EXIT_CONFIG = 3
EXIT_API = 4

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def parse_args(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base-url", default=None, help="Base URL")
    common.add_argument("--room", default=None, help="Room ID (e.g. 303-e183-fb29)")
    common.add_argument("--token", default=None, help="Agent Token")
    common.add_argument("--token-file", default=None, help="Path to credentials JSON")

    sub_common = argparse.ArgumentParser(add_help=False)
    sub_common.add_argument("--base-url", default=argparse.SUPPRESS)
    sub_common.add_argument("--room", default=argparse.SUPPRESS)
    sub_common.add_argument("--token", default=argparse.SUPPRESS)
    sub_common.add_argument("--token-file", default=argparse.SUPPRESS)

    parser = argparse.ArgumentParser(description="AgentMeet Leader Election Engine", parents=[common])
    subparsers = parser.add_subparsers(dest="command", help="Election subcommands")

    # nominate
    p_nom = subparsers.add_parser("nominate", parents=[sub_common], help="Nominate a candidate")
    p_nom.add_argument("--candidate-id", required=True, help="Candidate agent ID (e.g. ag_5613f172)")
    p_nom.add_argument("--candidate-name", default="", help="Candidate agent display name")
    p_nom.add_argument("--reason", default="Kinh nghiệm kỹ thuật và truy cập workspace", help="Nomination rationale")

    # vote
    p_vote = subparsers.add_parser("vote", parents=[sub_common], help="Cast a ballot for a candidate")
    p_vote.add_argument("--candidate-id", required=True, help="Candidate agent ID to vote for")
    p_vote.add_argument("--candidate-name", default="", help="Candidate agent display name (optional)")

    # tally
    p_tally = subparsers.add_parser("tally", parents=[sub_common], help="Count votes from room transcript and determine winner")

    # declare
    p_dec = subparsers.add_parser("declare", parents=[sub_common], help="Officially declare elected leader")
    p_dec.add_argument("--leader-id", required=True, help="Elected leader agent ID")
    p_dec.add_argument("--leader-name", default="", help="Elected leader name")
    p_dec.add_argument("--votes", type=int, default=1, help="Votes received")
    p_dec.add_argument("--total", type=int, default=1, help="Total voting agents")

    # status
    p_status = subparsers.add_parser("status", parents=[sub_common], help="Show current room leadership status")

    return parser.parse_args(argv)

def load_creds(args):
    room = getattr(args, "room", None)
    token = getattr(args, "token", None)
    agent_name = ""
    agent_id = ""
    base_url = getattr(args, "base_url", None) or DEFAULT_BASE_URL

    creds_file = getattr(args, "token_file", None) or "agent_creds.json"
    if not (room and token) and not os.path.exists(creds_file):
        home_creds = os.path.expanduser("~/.agentmeet/creds.json")
        if os.path.exists(home_creds):
            creds_file = home_creds

    if os.path.exists(creds_file):
        try:
            c = load_credentials(creds_file)
            room = room or c.get("room") or c.get("room_id") or c.get("room_code")
            token = token or c.get("agent_token")
            agent_name = c.get("agent_name", "")
            agent_id = c.get("agent_id", "")
            if base_url == DEFAULT_BASE_URL and c.get("base_url"):
                base_url = c.get("base_url")
        except Exception:
            pass

    return base_url, room, token, agent_id, agent_name

def send_message(base_url, room, token, my_name, content):
    if not token:
        print("Lỗi: Thiếu agent_token để gửi tin nhắn (dùng --token hoặc --token-file).", file=sys.stderr)
        sys.exit(EXIT_CONFIG)

    url = f"{base_url.rstrip('/')}/api/v1/{room}/message"
    payload = {
        "agent_token": token,
        "agent_name": my_name or "Agent",
        "content": content
    }
    try:
        req_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "AgentMeet-Election/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Lỗi API HTTP {e.code}: {e.reason}", file=sys.stderr)
        sys.exit(EXIT_API)
    except urllib.error.URLError as e:
        print(f"Lỗi mạng / kết nối: {e.reason}", file=sys.stderr)
        sys.exit(EXIT_API)

def fetch_transcript(base_url, room):
    url = f"{base_url.rstrip('/')}/api/v1/{room}/transcript?limit=100"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AgentMeet-Election/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Lỗi API HTTP {e.code}: {e.reason}", file=sys.stderr)
        sys.exit(EXIT_API)
    except urllib.error.URLError as e:
        print(f"Lỗi mạng / kết nối: {e.reason}", file=sys.stderr)
        sys.exit(EXIT_API)

def cmd_nominate(args, base_url, room, token, my_id, my_name):
    cid = args.candidate_id.strip()
    cname = args.candidate_name.strip() or cid
    data = {
        "action": "nominate",
        "candidate": cid,
        "candidate_id": cid,
        "candidate_name": cname,
        "reason": args.reason,
        "by": my_name or my_id,
        "nominator_id": my_id,
        "nominator_name": my_name
    }
    content = encode(KIND_LEAD, data)
    res = send_message(base_url, room, token, my_name, content)
    print(f"[room: {room}] [OK] Đã phát đề cử ứng viên {cname} ({cid}) vào phòng! Msg ID: {res.get('message_id')}")

def cmd_vote(args, base_url, room, token, my_id, my_name):
    cid = args.candidate_id.strip()
    cname = args.candidate_name.strip() or cid
    data = {
        "action": "vote",
        "candidate": cid,
        "candidate_id": cid,
        "candidate_name": cname,
        "by": my_name or my_id,
        "voter_id": my_id,
        "voter_name": my_name
    }
    content = encode(KIND_LEAD, data)
    res = send_message(base_url, room, token, my_name, content)
    print(f"[room: {room}] [OK] Đã bỏ phiếu cho {cname} ({cid})! Msg ID: {res.get('message_id')}")

def cmd_tally(args, base_url, room):
    tdata = fetch_transcript(base_url, room)
    messages = tdata.get("messages", [])
    agents = tdata.get("agents", [])
    active_agents = [a for a in agents if a.get("status") == "active" and a.get("agent_name") != "Admin"]
    total_voting = len(active_agents)

    name_map = {}
    for a in agents:
        name_map[a.get("agent_id")] = a.get("agent_name")

    for msg in messages:
        env = decode(msg.get("content", ""))
        if env and env.kind == KIND_LEAD:
            d = env.data
            cid = d.get("candidate_id") or d.get("candidate")
            cname = d.get("candidate_name") or d.get("lead")
            if cid and cname and cid not in name_map:
                name_map[cid] = cname

    result = tally_lead(messages)
    
    print(f"[room: {room}] === KẾT QUẢ KIỂM PHIẾU BẦU TRƯỞNG NHÓM ===")
    print(f"Tổng số Agents có quyền bầu ({total_voting}): {', '.join([name_map.get(a['agent_id'], a['agent_id']) for a in active_agents])}\n")

    if result.get("declared"):
        dec_id = result["declared"]
        dec_name = name_map.get(dec_id, dec_id)
        print(f"🏆 TRƯỞNG NHÓM ĐÃ TUYÊN BỐ (DECLARED): **{dec_name}** (`{dec_id}`)")
        return

    votes = result.get("votes", {})
    if not votes:
        print("Chưa có phiếu bầu nào được ghi nhận.")
        return

    sorted_results = sorted(votes.items(), key=lambda x: len(x[1]), reverse=True)
    print("| Ứng viên (Candidate) | ID | Số phiếu | Người bầu | Tỷ lệ (%) |")
    print("|---|---|---|---|---|")
    for cid, voter_list in sorted_results:
        pct = (len(voter_list) / total_voting * 100) if total_voting > 0 else 0
        voters_str = ", ".join(voter_list)
        cname = name_map.get(cid, cid)
        print(f"| **{cname}** | `{cid}` | **{len(voter_list)}** | {voters_str} | {pct:.1f}% |")

    if result.get("tie"):
        tied_names = [f"{name_map.get(t, t)} (`{t}`)" for t in result["tie"]]
        print(f"\n⚠️ HÒA PHIẾU giữa các ứng viên: {', '.join(tied_names)}! Cần áp dụng luật Tie-break (xem docs/LEADERSHIP.md).")
    elif result.get("lead"):
        winner_id = result["lead"]
        winner_name = name_map.get(winner_id, winner_id)
        w_votes = len(votes.get(winner_id, []))
        if w_votes > total_voting / 2:
            print(f"\n🏆 ĐẮC CỬ: **{winner_name}** (`{winner_id}`) với {w_votes}/{total_voting} phiếu (đạt đa số quá bán).")
        else:
            print(f"\n[CHƯA ĐẠT QUÁ BÁN] **{winner_name}** dẫn đầu với {w_votes}/{total_voting} phiếu. Cần tiếp tục bỏ phiếu.")

def cmd_declare(args, base_url, room, token, my_id, my_name):
    lid = args.leader_id.strip()
    lname = args.leader_name.strip() or lid
    data = {
        "action": "declare",
        "candidate": lid,
        "lead": lid,
        "leader_id": lid,
        "leader_name": lname,
        "by": my_name or my_id,
        "votes": args.votes,
        "total_agents": args.total
    }
    content = encode(KIND_LEAD, data)
    res = send_message(base_url, room, token, my_name, content)
    print(f"[room: {room}] [OK] Đã tuyên bố Trưởng nhóm: {lname} ({lid})! Msg ID: {res.get('message_id')}")

def cmd_status(args, base_url, room):
    tdata = fetch_transcript(base_url, room)
    messages = tdata.get("messages", [])
    agents = tdata.get("agents", [])
    name_map = {a.get("agent_id"): a.get("agent_name") for a in agents}
    for msg in messages:
        env = decode(msg.get("content", ""))
        if env and env.kind == KIND_LEAD:
            d = env.data
            cid = d.get("candidate_id") or d.get("candidate")
            cname = d.get("candidate_name") or d.get("lead")
            if cid and cname and cid not in name_map:
                name_map[cid] = cname

    result = tally_lead(messages)
    print(f"[room: {room}] === TRẠNG THÁI LÃNH ĐẠO PHÒNG HỌP ===")
    if result.get("declared"):
        lid = result["declared"]
        print(f"Trưởng nhóm đương nhiệm: **{name_map.get(lid, lid)}** (`{lid}`) — Đã tuyên bố chính thức.")
    elif result.get("lead"):
        lid = result["lead"]
        print(f"Ứng viên dẫn đầu phiếu: **{name_map.get(lid, lid)}** (`{lid}`) — Chưa tuyên bố.")
    else:
        print("Chưa có Trưởng nhóm được tuyên bố trong phiên làm việc hiện tại.")

def main():
    args = parse_args()
    if not args.command:
        print("Vui lòng chỉ định lệnh: nominate, vote, tally, declare, status. Dùng --help để xem chi tiết.", file=sys.stderr)
        sys.exit(1)

    base_url, room, token, my_id, my_name = load_creds(args)
    if not room:
        print("Lỗi: Không tìm thấy room. Cung cấp --room hoặc --token-file.", file=sys.stderr)
        sys.exit(EXIT_CONFIG)

    if args.command in ("nominate", "vote", "declare") and not token:
        print(f"Lỗi: Lệnh '{args.command}' yêu cầu agent_token hợp lệ (--token hoặc --token-file).", file=sys.stderr)
        sys.exit(EXIT_CONFIG)

    if args.command == "nominate":
        cmd_nominate(args, base_url, room, token, my_id, my_name)
    elif args.command == "vote":
        cmd_vote(args, base_url, room, token, my_id, my_name)
    elif args.command == "tally":
        cmd_tally(args, base_url, room)
    elif args.command == "declare":
        cmd_declare(args, base_url, room, token, my_id, my_name)
    elif args.command == "status":
        cmd_status(args, base_url, room)

if __name__ == "__main__":
    main()
