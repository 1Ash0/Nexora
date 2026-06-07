"""
Entry point for Nexora backend.

CRITICAL (Windows): psycopg3 requires SelectorEventLoop. We must:
  1. Set WindowsSelectorEventLoopPolicy before anything else
  2. Call asyncio.run() ourselves so the loop type is guaranteed
     (uvicorn.run() internally calls asyncio.run() which on Windows
      still picks ProactorEventLoop despite the policy in some versions)
"""
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn


async def serve():
    config = uvicorn.Config(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
        loop="none",   # tell uvicorn NOT to touch the event loop
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(serve())
