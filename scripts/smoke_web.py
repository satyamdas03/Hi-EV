#!/usr/bin/env python3
"""Smoke test for the Hi-EV WebSocket chat endpoint.

Expects the daemon to be running on ws://127.0.0.1:7345/ws.
Sends a transcript and prints the streamed response.
"""

import asyncio
import json
import sys

import websockets


async def main():
    uri = "ws://127.0.0.1:7345/ws"
    transcript = sys.argv[1] if len(sys.argv) > 1 else "status of Hi-EV"
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as ws:
        await ws.send('{"type": "ping"}')
        pong = await ws.recv()
        print("ping:", pong)

        await ws.send(json.dumps({"type": "transcript", "text": transcript}))
        print(f"sent transcript: {transcript}")
        print("response:")
        while True:
            msg = await ws.recv()
            print(" ", msg)
            data = json.loads(msg)
            if data.get("type") == "done":
                break


if __name__ == "__main__":
    asyncio.run(main())
