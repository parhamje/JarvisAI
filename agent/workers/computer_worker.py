import asyncio
from typing import Dict, Any
from agent.base_agent import BaseWorkerAgent
from actions.autonomous_computer import autonomous_computer

class ComputerWorkerAgent(BaseWorkerAgent):
    """
    Worker Agent responsible for autonomous computer vision analysis,
    screen spatial reasoning, and mouse/keyboard GUI execution.
    """
    def __init__(self):
        super().__init__(agent_id="computer_agent", name="Computer Vision & GUI Worker Agent")

    async def process_action(self, action: str, payload: Dict[str, Any]) -> Any:
        loop = asyncio.get_running_loop()

        if action == "execute_gui_task":
            task_description = payload.get("task", "")
            result = await loop.run_in_executor(
                None,
                autonomous_computer,
                task_description
            )
            return {"result": result}
        else:
            raise ValueError(f"Unknown action '{action}' for ComputerWorkerAgent.")
