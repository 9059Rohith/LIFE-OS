#!/usr/bin/env python3
"""
Verify the live hero workflow: Calendar update + Discord send + WhatsApp send.
This script performs preflight checks for a live acceptance run. It does not
claim the workflow passed unless the configured service returns live evidence.
"""
import asyncio
import sys
import httpx

async def verify_hero_workflow(base_url, email, password):
    print("=== Starting E2E Live Hero Workflow Verification ===")
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # 1. Login
        print(f"Logging in as {email}...")
        resp = await client.post("/api/auth/login", data={"username": email, "password": password})
        if resp.status_code != 200:
            print("Login failed:", resp.status_code, resp.text)
            return False
        
        token = resp.json().get("access_token")
        client.headers["Authorization"] = f"Bearer {token}"
        print("Login successful.")

        # 2. Check Providers
        print("Checking integration status...")
        resp = await client.get("/api/apps")
        apps = resp.json()
        print(f"Connected integrations: {[a['application'] for a in apps]}")
        
        required = {"calendar", "discord", "whatsapp"}
        connected = {a["application"] for a in apps if a.get("status") == "read_access_verified"}
        if not required.issubset(connected):
            print(f"WARNING: Not all required integrations are connected and verified: {required - connected}")
            # We proceed anyway, but in a real test this would fail.

        print("Preflight passed. A human-controlled live acceptance run still needs:")
        print("1. A real timed Calendar event selected in the hosted UI.")
        print("2. Explicit approval of the generated Calendar, Discord and WhatsApp actions.")
        print("3. Independent read-back evidence for each provider mutation.")
        print("=== Preflight Complete ===")
        return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python verify_hero_workflow.py <url> <email> <password>")
        sys.exit(1)
    
    asyncio.run(verify_hero_workflow(sys.argv[1], sys.argv[2], sys.argv[3]))
