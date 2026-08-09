import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import unittest
from core.a2a_bus import get_a2a_bus, A2AMessage
from agent.workers.dev_worker import DevWorkerAgent
from agent.workers.browser_worker import BrowserWorkerAgent
from agent.workers.computer_worker import ComputerWorkerAgent

class TestA2ASystem(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.bus = get_a2a_bus()
        self.dev_worker = DevWorkerAgent()
        self.browser_worker = BrowserWorkerAgent()
        self.computer_worker = ComputerWorkerAgent()
        
        self.dev_worker.start()
        self.browser_worker.start()
        self.computer_worker.start()

    async def asyncTearDown(self):
        self.dev_worker.stop()
        self.browser_worker.stop()
        self.computer_worker.stop()

    async def test_dev_worker_execution(self):
        msg = A2AMessage(
            sender="master",
            recipient="dev_agent",
            action="execute_code",
            payload={"code": "print('Hello from A2A!')"}
        )
        response_msg = await self.bus.request(msg, timeout=10.0)
        self.assertEqual(response_msg.status, "completed")
        self.assertIn("Hello from A2A!", response_msg.response["output"])

    async def test_browser_worker_search(self):
        msg = A2AMessage(
            sender="master",
            recipient="browser_agent",
            action="search_web",
            payload={"query": "Python asyncio"}
        )
        response_msg = await self.bus.request(msg, timeout=15.0)
        self.assertEqual(response_msg.status, "completed")
        self.assertIsNotNone(response_msg.response["results"])

if __name__ == "__main__":
    unittest.main()
