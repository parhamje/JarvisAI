import asyncio
from typing import Dict, Any
from agent.base_agent import BaseWorkerAgent
from actions.dev_agent import dev_agent

class DevWorkerAgent(BaseWorkerAgent):
    """
    Worker Agent responsible for software development, coding tasks,
    script creation, and iterative bug fixing in the background.
    """
    def __init__(self):
        super().__init__(agent_id="dev_agent", name="Dev Worker Agent")

    async def process_action(self, action: str, payload: Dict[str, Any]) -> Any:
        if action == "build_feature":
            task_description = payload.get("task", "")
            target_file = payload.get("file", None)
            
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, 
                self._run_dev_task, 
                task_description, 
                target_file
            )
            return result
        elif action == "execute_code":
            code = payload.get("code", "")
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, 
                dev_agent,
                {"description": f"Execute the following python code snippet:\n```python\n{code}\n```"}
            )
            return {"output": result}
        else:
            raise ValueError(f"Unknown action '{action}' for DevWorkerAgent.")

    def _run_dev_task(self, task: str, target_file: str = None) -> Dict[str, Any]:
        print(f"[{self.name}] Starting background dev task: '{task}'")
        res = dev_agent({"description": task})
        return {
            "success": True,
            "summary": res
        }
