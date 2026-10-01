#!/usr/bin/env python3
"""test_concurrent_claim.py - Stress test atomic claim race prevention.

Tests that the prototype server correctly prevents concurrent task claims
using multiple threads. Verifies exactly one agent gets 200 and all others
get 409 Conflict.

Usage:
    python test_concurrent_claim.py                    # Default: 4 threads
    python test_concurrent_claim.py --threads 8        # 8 parallel threads
    python test_concurrent_claim.py --rounds 5         # Run 5 rounds
    python test_concurrent_claim.py --url http://...   # Custom server URL
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.stdout.reconfigure(encoding="utf-8")


def create_room(base_url):
    """Create a test room and return room_code + agent tokens."""
    data = json.dumps({"max_messages": 100, "agent_name": "Lead"}).encode()
    req = Request(f"{base_url}/api/v1/rooms", data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    resp = urlopen(req, timeout=10)
    result = json.loads(resp.read().decode())
    
    room = result["room_code"]
    lead_token = result["agent_token"]
    
    # Create N agents
    tokens = [lead_token]
    for i in range(20):  # Pre-create enough agents
        req = Request(f"{base_url}/api/v1/{room}/agent-join?name=Worker{i}")
        resp = urlopen(req, timeout=10)
        tokens.append(json.loads(resp.read().decode())["agent_token"])
    
    return room, tokens


def create_task(base_url, room, lead_token):
    """Create a task and return task_id."""
    data = json.dumps({
        "agent_token": lead_token,
        "title": f"Race Test Task {time.time()}",
        "description": "Concurrent claim stress test"
    }).encode()
    req = Request(f"{base_url}/api/v1/{room}/tasks", data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    resp = urlopen(req, timeout=10)
    return json.loads(resp.read().decode())["id"]


def claim_task(base_url, room, task_id, agent_token):
    """Attempt to claim a task. Returns (status_code, agent_token_suffix)."""
    data = json.dumps({"agent_token": agent_token}).encode()
    req = Request(f"{base_url}/api/v1/{room}/tasks/{task_id}/claim", data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        resp = urlopen(req, timeout=10)
        return resp.status
    except HTTPError as e:
        return e.code


def run_race_test(base_url, room, tokens, num_threads, round_num):
    """Run one round of concurrent claim test."""
    task_id = create_task(base_url, room, tokens[0])
    
    # Select N different agent tokens for this round
    test_tokens = tokens[1:num_threads + 1]
    
    results = []
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {
            executor.submit(claim_task, base_url, room, task_id, tok): i
            for i, tok in enumerate(test_tokens)
        }
        for future in as_completed(futures):
            status = future.result()
            results.append(status)
    
    results.sort()
    success_count = results.count(200)
    conflict_count = results.count(409)
    
    passed = (success_count == 1 and conflict_count == num_threads - 1)
    
    return {
        "round": round_num,
        "threads": num_threads,
        "results": results,
        "success": success_count,
        "conflict": conflict_count,
        "passed": passed,
    }


def main():
    parser = argparse.ArgumentParser(description="Stress test atomic claim")
    parser.add_argument("--url", default="http://127.0.0.1:8080", help="Server URL")
    parser.add_argument("--threads", type=int, default=4, help="Parallel threads (default: 4)")
    parser.add_argument("--rounds", type=int, default=3, help="Number of test rounds (default: 3)")
    args = parser.parse_args()

    print(f"🧪 CONCURRENT CLAIM STRESS TEST")
    print(f"   Server: {args.url}")
    print(f"   Threads: {args.threads}")
    print(f"   Rounds: {args.rounds}")
    print("=" * 55)

    try:
        room, tokens = create_room(args.url)
        print(f"✅ Room created: {room} ({len(tokens)} agents)\n")
    except Exception as e:
        print(f"❌ Failed to connect to server: {e}")
        print("   Make sure prototype server is running:")
        print("   cd O:\\agent-meet-server\\prototype && python app.py")
        sys.exit(1)

    all_passed = True
    for r in range(1, args.rounds + 1):
        result = run_race_test(args.url, room, tokens, args.threads, r)
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"  Round {r}: {result['results']} → {status}")
        if not result["passed"]:
            all_passed = False
            print(f"    Expected: 1×200 + {args.threads-1}×409")
            print(f"    Got:      {result['success']}×200 + {result['conflict']}×409")

    print("\n" + "=" * 55)
    if all_passed:
        print(f"🎉 ALL {args.rounds} ROUNDS PASSED! Atomic claim is working correctly.")
    else:
        print(f"⚠️ SOME ROUNDS FAILED! Race condition may still exist.")
    print("=" * 55)


if __name__ == "__main__":
    main()
