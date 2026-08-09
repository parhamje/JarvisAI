import asyncio
import traceback
from typing import Dict, Any, Optional
from core.a2a_bus import get_a2a_bus, A2AMessage

class BaseWorkerAgent:
    """
    Base class for asynchronous worker agents in the Jarvis Multi-Agent ecosystem.
    Each worker agent listens on the A2A bus for messages directed to its agent_id.
    """
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.bus = get_a2a_bus()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        """Starts the worker agent's message processing loop."""
        if self._running:
            return
        self._running = True
        self.bus.register_agent(self.agent_id)
        self._task = asyncio.create_task(self._run_loop())
        print(f"[{self.name}] Agent started and listening on A2A bus.")

    def stop(self):
        """Stops the worker agent."""
        self._running = False
        if self._task:
            self._task.cancel()
        self.bus.unregister_agent(self.agent_id)
        print(f"[{self.name}] Agent stopped.")

    async def _run_loop(self):
        """Internal processing loop receiving messages from the bus."""
        while self._running:
            try:
                msg = await self.bus.receive(self.agent_id)
                msg.status = "in_progress"
                await self.bus.broadcast_event(msg)
                
                try:
                    response_payload = await self.process_action(msg.action, msg.payload)
                    msg.status = "completed"
                    msg.response = response_payload
                except Exception as e:
                    msg.status = "failed"
                    msg.error = str(e)
                    print(f"[{self.name}] Error processing action '{msg.action}': {e}")
                    traceback.print_exc()

                # Send reply back through the bus
                await self.bus.reply(msg)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.name}] Unexpected loop error: {e}")
                await asyncio.sleep(1)

    async def process_action(self, action: str, payload: Dict[str, Any]) -> Any:
        """
        Subclasses override this method to perform their specific actions.
        Should return a result (dict, string, etc.) or raise an Exception on failure.
        """
        raise NotImplementedError("Subclasses must implement process_action()")
