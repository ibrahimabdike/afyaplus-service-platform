import logging
import os
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from auth import current_user

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("afyaplus.agent")
app = FastAPI(title="AfyaPlus Logistics Agent API", version="1.0.0")
_agent = None

class AskRequest(BaseModel):
    model_config = {"extra": "forbid"}
    question: str = Field(min_length=5, max_length=500)

async def get_agent():
    global _agent
    if _agent is not None:
        return _agent
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise HTTPException(503, "Agent model is not configured.")
    client = MultiServerMCPClient({
        "logistics": {"transport": "stdio", "command": "python",
                      "args": [os.path.join(os.path.dirname(__file__), "logistics_mcp.py")]}
    })
    tools = await client.get_tools()
    model = ChatOpenAI(
        model=os.getenv("AGENT_MODEL", "openai/gpt-4o-mini"),
        api_key=key, base_url="https://openrouter.ai/api/v1",
        temperature=0.2, max_tokens=400,
    )
    _agent = create_agent(model, tools, system_prompt=(
        "You are the AfyaPlus logistics assistant. Use tools for stock and routes; "
        "never invent stock values. Reorder is flagged below 10 units. "
        "If tools cannot answer, say so clearly. Route distances are approximate "
        "straight-line estimates, not live road directions. Never confirm or execute orders."
    ))
    return _agent

@app.get("/health")
def health():
    return {"service": "logistics-agent-api", "version": "1.0.0", "status": "ok"}

@app.post("/ask-logistics")
async def ask_logistics(body: AskRequest, user: dict = Depends(current_user)):
    trace_id = uuid4().hex[:8]
    log.info("event=agent_request trace=%s user=%s question_chars=%s",
             trace_id, user["sub"], len(body.question))
    try:
        agent = await get_agent()
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": body.question}]},
            {"recursion_limit": 8},
        )
        answer = result["messages"][-1].content
        log.info("event=agent_complete trace=%s user=%s", trace_id, user["sub"])
        return {"answer": answer, "trace_id": trace_id}
    except HTTPException:
        raise
    except Exception:
        log.exception("event=agent_failed trace=%s", trace_id)
        raise HTTPException(503, detail=f"Agent unavailable; reference trace {trace_id}.")
