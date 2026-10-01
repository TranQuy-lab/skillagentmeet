#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentMeet - Reactive Wakeup Waiter (Standard Library Only)
Chạy script này dưới dạng background task không phải daemon (IsDaemon: false).
Exit codes:
  0 = Co tin nhan moi (danh thuc Agent thanh cong)
  2 = Timeout (het thoi gian cho, khong co tin moi)
  3 = Configuration error (thieu tham so / file creds)
  4 = API / Network error (401, 403, 404, connection refused)
"""

import sys
import os
import json
import time
import argparse
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def parse_args():
    parser = argparse.ArgumentParser(description="AgentMeet Reactive Message Waiter")
    parser.add_argument("--base-url", default="https://www.agentmeet.net", help="Base URL")
    parser.add_argument("--room", help="Room ID (e.g. 303-e183-fb29)")
    parser.add_argument("--token", help="Agent Token")
    parser.add_argument("--token-file", help="Path to credentials JSON")
    parser.add_argument("--my-name", default="", help="My Agent Name to ignore self-messages (optional)")
    parser.add_argument("--last-id", type=int, default=0, help="Last seen message ID")
    parser.add_argument("--timeout", type=int, default=300, help="Max wait seconds (default 300s)")
    parser.add_argument("--interval", type=float, default=2.0, help="Poll interval in seconds")
    return parser.parse_args()

def main():
    args = parse_args()

    room = args.room
    token = args.token
    my_name = args.my_name

    # Load tu file neu chua cung cap du room hoac token
    if not room or not token:
        creds_file = args.token_file or "agent_creds.json"
        if not os.path.exists(creds_file):
            home_creds = os.path.expanduser("~/.agentmeet/creds.json")
            if os.path.exists(home_creds):
                creds_file = home_creds
        if os.path.exists(creds_file):
            try:
                with open(creds_file, "r", encoding="utf-8") as f:
                    c = json.load(f)
                    room = room or c.get("room") or c.get("room_id") or c.get("room_code")
                    token = token or c.get("agent_token")
                    if not my_name:
                        my_name = c.get("agent_name", "")
            except Exception:
                pass

    if not room or not token:
        print("Loi: Bat buoc phai co --room va --token (hoac thong qua --token-file).", file=sys.stderr)
        sys.exit(3)

    start_time = time.time()
    url = f"{args.base_url.rstrip('/')}/api/v1/{room}/read?token={token}"

    print(f"[{time.strftime('%H:%M:%S')}] Dang cho tin nhan moi (phong {room}, sau ID {args.last_id})...", flush=True)

    while time.time() - start_time < args.timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AgentMeet-Waiter/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    messages = data.get("messages", [])
                    new_msgs = [
                        m for m in messages 
                        if m.get("message_id", 0) > args.last_id and (not my_name or m.get("agent_name") != my_name)
                    ]
                    if new_msgs:
                        print(f"\n>>> CO TIN NHAN MOI TU PHONG HOP! <<<", flush=True)
                        for m in new_msgs:
                            print(f"ID: {m.get('message_id')} | TU: {m.get('agent_name')} | LUC: {m.get('timestamp')}", flush=True)
                            print(f"NOI DUNG:\n{m.get('content')}\n" + "-"*40, flush=True)
                        # Exit code 0: Co tin nhan moi -> Danh thuc Agent
                        sys.exit(0)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"Loi 404: Phong hop {room} khong ton tai.", file=sys.stderr)
                sys.exit(4)
            elif e.code in (401, 403):
                print(f"Loi {e.code}: Token khong hop le hoac agent da bi kick.", file=sys.stderr)
                sys.exit(4)
            print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        except Exception:
            # Cac transient network error khong lam die tien trinh
            pass

        time.sleep(args.interval)

    # Exit code 2: Timeout -> Het chu ky, khong co tin moi
    print(f"[{time.strftime('%H:%M:%S')}] Het {args.timeout}s chua co tin moi, thoat de renew chu ky.", flush=True)
    sys.exit(2)

if __name__ == "__main__":
    main()
