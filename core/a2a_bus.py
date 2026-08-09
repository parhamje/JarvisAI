import asyncio
import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Callable, Awaitable, List, Optional

@dataclass
class A2AMessage:
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = "master"
    recipient: str = "broadcast"
    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, in_progress, completed, failed
    response: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "action": self.action,
            "payload": self.payload,
            "status": self.status,
            "response": self.response,
            "error": self.error,
            "created_at": self.created_at,
        }

class A2ABus:
    """
    Central Agent-to-Agent (A2A) Event & Message Bus.
    Handles asynchronous message dispatching, subscriptions, and response routing.
    """
    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._subscribers: Dict[str, List[Callable[[A2AMessage], Awaitable[None]]]] = {}
        self._results: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    def register_agent(self, agent_id: str):
        """Registers a worker agent with its own dedicated message queue."""
        if agent_id not in self._queues:
            self._queues[agent_id] = asyncio.Queue()
            print(f"[A2A Bus] Registered agent: '{agent_id}'")

    def unregister_agent(self, agent_id: str):
        if agent_id in self._queues:
            del self._queues[agent_id]
            print(f"[A2A Bus] Unregistered agent: '{agent_id}'")

    async def send(self, msg: A2AMessage) -> A2AMessage:
        """Sends a message to a specific recipient agent."""
        recipient = msg.recipient
        if recipient in self._queues:
            await self._queues[recipient].put(msg)
            print(f"[A2A Bus] Message [{msg.action}] routed from '{msg.sender}' to '{recipient}'")
        else:
            msg.status = "failed"
            msg.error = f"Recipient agent '{recipient}' not registered."
            print(f"[A2A Bus] Failed to route message: Agent '{recipient}' not found.")
        return msg

    async def request(self, msg: A2AMessage, timeout: float = 60.0) -> A2AMessage:
        """Sends a message and waits for the worker agent to complete and return a result."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._results[msg.message_id] = future

        await self.send(msg)

        try:
            result_msg = await asyncio.wait_for(future, timeout=timeout)
            return result_msg
        except asyncio.TimeoutError:
            msg.status = "failed"
            msg.error = f"Request timed out after {timeout}s"
            return msg
        finally:
            self._results.pop(msg.message_id, None)

    async def reply(self, msg: A2AMessage):
        """Called by worker agents to return results for a request."""
        if msg.message_id in self._results:
            future = self._results[msg.message_id]
            if not future.done():
                future.set_result(msg)
        
        # Also broadcast result event to subscribers
        await self.broadcast_event(msg)

    async def subscribe(self, event_type: str, callback: Callable[[A2AMessage], Awaitable[None]]):
        """Allows agents to subscribe to specific event types."""
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

    async def broadcast_event(self, msg: A2AMessage):
        """Notifies all subscribers of an event (e.g. status updates)."""
        action_subs = self._subscribers.get(msg.action, [])
        all_subs = self._subscribers.get("*", [])
        callbacks = action_subs + all_subs

        for cb in callbacks:
            try:
                asyncio.create_task(cb(msg))
            except Exception as e:
                print(f"[A2A Bus] Error in subscriber callback: {e}")

    async def receive(self, agent_id: str) -> A2AMessage:
        """Called by worker agents to await their next assigned message."""
        if agent_id not in self._queues:
            self.register_agent(agent_id)
        return await self._queues[agent_id].get()

# Global Singleton Instance
_bus_instance = None

def get_a2a_bus() -> A2ABus:
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = A2ABus()
    return _bus_instance
