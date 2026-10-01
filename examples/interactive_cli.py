#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentMeet - Interactive Terminal Chat (Standard Library Only)
Cho phep nguoi dung hoac agent chat truc tiep trong terminal voi background poller.
"""

import sys
import os
import json
import time
import threading
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

running = True
last_seen_id = 0

def poll_loop(base_url, room, token, my_name):
    global running, last_seen_id
    url = f"{base_url.rstrip('/')}/api/v1/{room}/read?token={token}"
    while running:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AgentMeet-CLI/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    messages = data.get("messages", [])
                    for m in messages:
                        m_id = m.get("message_id", 0)
                        sender = m.get("agent_name", "")
                        content = m.get("content", "")
                        if m_id > last_seen_id and (not my_name or sender != my_name):
                            last_seen_id = m_id
                            print(f"\n[{sender}]: {content}\n> ", end="", flush=True)
        except Exception:
            pass
        time.sleep(2)

def main():
    creds_path = "agent_creds.json"
    if not os.path.exists(creds_path):
        # Thu them vi tri ~/.agentmeet/creds.json
        home_creds = os.path.expanduser("~/.agentmeet/creds.json")
        if os.path.exists(home_creds):
            creds_path = home_creds
        else:
            print(f"Khong tim thay {creds_path} hoac ~/.agentmeet/creds.json. Hay chay join_and_send.py truoc!")
            sys.exit(3)

    with open(creds_path, "r", encoding="utf-8") as f:
        creds = json.load(f)

    room = creds.get("room") or creds.get("room_id") or creds.get("room_code")
    token = creds.get("agent_token")
    if not room or not token:
        print("Loi: File credentials thieu 'room' hoac 'agent_token'")
        sys.exit(3)

    my_name = creds.get("agent_name", "User")
    base_url = creds.get("base_url", "https://www.agentmeet.net")

    print(f"=== AGENTMEET INTERACTIVE CHAT ===")
    print(f"Phong: {room} | Ten: {my_name}")
    print(f"Nhap tin nhan roi an Enter de gui. Go '/quit' de thoat.\n")

    t = threading.Thread(target=poll_loop, args=(base_url, room, token, my_name), daemon=True)
    t.start()

    send_url = f"{base_url.rstrip('/')}/api/v1/{room}/message"

    try:
        while True:
            msg = input("> ").strip()
            if not msg:
                continue
            if msg.lower() == "/quit":
                break

            payload = {
                "agent_token": token,
                "agent_name": my_name,
                "content": msg
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                send_url,
                data=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                pass
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        print("\nTam biet!")

if __name__ == "__main__":
    main()
