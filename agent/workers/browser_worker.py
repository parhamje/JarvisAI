import asyncio
from typing import Dict, Any
from agent.base_agent import BaseWorkerAgent
from actions.web_search import web_search

class BrowserWorkerAgent(BaseWorkerAgent):
    """
    Worker Agent responsible for background web research, site scraping,
    and automated browser interaction.
    """
    def __init__(self):
        super().__init__(agent_id="browser_agent", name="Browser Worker Agent")

    async def process_action(self, action: str, payload: Dict[str, Any]) -> Any:
        loop = asyncio.get_running_loop()

        if action == "search_web":
            query = payload.get("query", "")
            domain = payload.get("domain", None)
            params = {"query": query}
            if domain:
                params["domain"] = domain
            result = await loop.run_in_executor(
                None,
                web_search,
                params
            )
            return {"results": result}

        elif action == "browse":
            from actions.browser_control import browser_control
            nav_action = payload.get("nav_action", "open")
            url = payload.get("url", "")
            query = payload.get("query", "")
            result = await loop.run_in_executor(
                None,
                browser_control,
                nav_action,
                url,
                query
            )
            return {"output": result}

        else:
            raise ValueError(f"Unknown action '{action}' for BrowserWorkerAgent.")
