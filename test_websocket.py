#!/usr/bin/env python3
"""
WebSocket test client to check if the upgrade to 101 status works
"""
import asyncio
import websockets
import json
import sys

async def test_websocket(url: str, ticket_id: int, user_id: int):
    """Test WebSocket connection and 101 upgrade"""
    try:
        print(f"Connecting to: {url}")
        
        async with websockets.connect(url) as websocket:
            print(f"✓ WebSocket connected!")
            print(f"✓ Connection established (101 Switching Protocols)")
            
            # Send subscribe message
            subscribe_msg = {
                "type": "subscribe",
                "ticket_id": ticket_id,
                "user_id": user_id
            }
            print(f"\nSending subscribe message: {json.dumps(subscribe_msg)}")
            await websocket.send(json.dumps(subscribe_msg))
            
            # Receive confirmation
            response = await websocket.recv()
            print(f"Received: {response}")
            
            # Keep connection alive for 10 seconds to receive any messages
            print("\nWaiting for messages (10 seconds)...")
            try:
                while True:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10)
                    print(f"Message received: {message}")
            except asyncio.TimeoutError:
                print("No messages received (timeout)")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Use local or remote URL
    # For local testing: ws://localhost:8000/ws/ticket/1
    # For remote testing: ws://155.212.218.54/ws/ticket/1
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        # Try local first, then remote
        url = "ws://localhost:8000/ws/ticket/1"
    
    ticket_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    user_id = int(sys.argv[3]) if len(sys.argv) > 3 else 123
    
    print(f"WebSocket Test Client")
    print(f"URL: {url}")
    print(f"Ticket ID: {ticket_id}")
    print(f"User ID: {user_id}")
    print("-" * 50)
    
    asyncio.run(test_websocket(url, ticket_id, user_id))
