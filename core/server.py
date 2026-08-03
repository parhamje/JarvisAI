import asyncio
import json
import websockets
from typing import Set, Callable, Awaitable

class JarvisServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.on_message_callback: Callable[[str, dict], Awaitable[None]] = None
        
    def set_callback(self, callback: Callable[[str, dict], Awaitable[None]]):
        self.on_message_callback = callback

    async def register(self, websocket):
        self.clients.add(websocket)
        print(f"[Server] Client connected. Total: {len(self.clients)}")

    async def unregister(self, websocket):
        self.clients.remove(websocket)
        print(f"[Server] Client disconnected. Total: {len(self.clients)}")

    async def handler(self, websocket, path):
        await self.register(websocket)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "unknown")
                    payload = data.get("payload", {})
                    
                    if self.on_message_callback:
                        await self.on_message_callback(msg_type, payload)
                        
                except json.JSONDecodeError:
                    print(f"[Server] Invalid JSON received: {message}")
        finally:
            await self.unregister(websocket)

    async def broadcast(self, msg_type: str, payload: dict):
        if not self.clients:
            return
            
        message = json.dumps({"type": msg_type, "payload": payload})
        
        # Broadcast to all connected clients
        tasks = [asyncio.create_task(client.send(message)) for client in self.clients]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def start(self):
        print(f"[Server] Starting WebSocket server on ws://{self.host}:{self.port}")
        async with websockets.serve(self.handler, self.host, self.port):
            await asyncio.Future()  # run forever

# Singleton instance
_server = None

def get_server() -> JarvisServer:
    global _server
    if _server is None:
        _server = JarvisServer()
    return _server
