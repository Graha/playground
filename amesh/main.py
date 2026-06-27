import os
from typing import AsyncGenerator, List, Dict, Any
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Core Modern LangChain Framework & OpenAI
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, trim_messages
from langchain_core.tools import tool

# LangChain Modern Qdrant Integration
from langchain_qdrant import QdrantVectorStore

# LangGraph Orchestration & Checkpointing Engine
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import AsyncMemorySaver

app = FastAPI(
    title="Stateful Multi-Agent platform with Qdrant Long-Term Memory")

# Initialize Shared State Dependencies
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, streaming=True)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
memory_saver = AsyncMemorySaver()

# Standardize localized Qdrant Vector Store connection details
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "enterprise_knowledge_vault"

# Instance pointer initialization wrapper
qdrant_store = QdrantVectorStore.from_existing_collection(
    embedding=embeddings,
    collection_name=COLLECTION_NAME,
    url=QDRANT_URL
)

# =====================================================================
# 1. STRUCTURAL MIDDLEWARE (Execution Logging & Safety Validation)
# =====================================================================


class ProductionExecutionMiddleware(AgentMiddleware):
    """Custom middleware checking model request structures and tracing execution paths."""

    async def __call__(self, state: Any, config: Dict[str, Any], run_next: Any) -> Any:
        thread_id = config.get("configurable", {}).get(
            "thread_id", "anonymous")
        print(
            f"--> [MIDDLEWARE LOG] Executing thinking iteration window for Session Thread: {thread_id}")

        # Pass execution safely down to the next node wrapper component block
        response = await run_next(state, config)

        print(
            f"<-- [MIDDLEWARE LOG] Execution cycle complete for Thread: {thread_id}")
        return response

# =====================================================================
# 2. GLOBAL ROUTER STATE SCHEMA
# =====================================================================


class GlobalPlatformState(dict):
    """Defines the globally shared multi-agent state data dict layout."""
    messages: list
    target_agent: str        # 'billing' or 'tech'
    user_id: str
    retrieved_context: str   # Long-Term background knowledge injected via Qdrant

# =====================================================================
# 3. GRAPH RUNNER PROCESSING NODES
# =====================================================================


async def short_term_memory_node(state: GlobalPlatformState):
    """
    Short-Term Memory Manager Node.
    Slices history down to a fixed message window size to stabilize processing costs.
    """
    current_history = state["messages"]

    trimmed_history = trim_messages(
        current_history,
        strategy="last",
        token_counter=len,
        max_tokens=8,          # Rolling window constraint
        start_on="human",
        allow_partial=False
    )
    print(
        f"[SHM NODE] Managed message sequence length from {len(current_history)} down to {len(trimmed_history)}")
    return {"messages": trimmed_history}


async def long_term_memory_retrieval_node(state: GlobalPlatformState):
    """
    Long-Term Memory Search Node (RAG).
    Extracts the core user question and references the Qdrant instance.
    """
    if not state["messages"]:
        return {"retrieved_context": ""}

    latest_user_query = state["messages"][-1].content
    print(
        f"[LTM NODE] Querying Qdrant Vector Engine with text chunk: '{latest_user_query}'")

    # Asynchronous similarity scan across the semantic space indexes
    # Filter constraints matching individual users can be layered into this filter dict
    search_results = await qdrant_store.asimilarity_search(
        query=latest_user_query,
        k=2
    )

    # Format and pack retrieved knowledge context frames
    context_chunks = [doc.page_content for doc in search_results]
    aggregated_context = "\n---\n".join(
        context_chunks) if context_chunks else "No historical records found."

    return {"retrieved_context": aggregated_context}


async def polymorphic_agent_node(state: GlobalPlatformState, config):
    """
    Polymorphic Agent Execution Worker.
    Dynamically loads the agent configuration based on input parameters,
    combines long-term context with short-term history, and invokes the agent.
    """
    agent_mode = state.get("target_agent", "tech")

    # Define agent boundaries dynamically
    if agent_mode == "billing":
        system_base = "You are a professional Account Billing Specialist. Focus on payment issues."
    else:
        system_base = "You are an Elite Systems Infrastructure Engineer. Focus on tech troubleshooting."

    # Inject retrieved Long-Term memory assets inside the primary configuration prompt window
    full_prompt_instructions = (
        f"{system_base}\n\n"
        f"### LONG-TERM KNOWLEDGE BASE CONTEXT (QDRANT):\n"
        f"{state.get('retrieved_context', 'No data available.')}\n\n"
        f"Analyze the context blocks above to accurately address the user request."
    )

    # Build a fresh, clean instance conforming to modern LangChain v1 guidelines
    dynamic_worker_agent = create_agent(
        llm,
        tools=[],  # Add operational business tools arrays if required
        prompt=full_prompt_instructions,
        middleware=[ProductionExecutionMiddleware()],
        checkpointer=memory_saver
    )

    # Trigger execution layer passing along context structures down the sub-network graph
    agent_result = await dynamic_worker_agent.ainvoke({"messages": state["messages"]}, config)
    return {"messages": agent_result["messages"]}

# =====================================================================
# 4. TOPOLOGY GRAPH ASSEMBLY
# =====================================================================
workflow = StateGraph(GlobalPlatformState)

# Append execution processing step nodes
workflow.add_node("short_term_trimmer", short_term_memory_node)
workflow.add_node("long_term_retriever", long_term_memory_retrieval_node)
workflow.add_node("agent_core_worker", polymorphic_agent_node)

# Map edge connections layout path lines
workflow.add_edge(START, "short_term_trimmer")
workflow.add_edge("short_term_trimmer", "long_term_retriever")
workflow.add_edge("long_term_retriever", "agent_core_worker")
workflow.add_edge("agent_core_worker", END)

# Compile global interface controller
production_platform_agent = workflow.compile(checkpointer=memory_saver)

# =====================================================================
# 5. FASTAPI REST INTERFACE PIPELINE ENDPOINTS
# =====================================================================


class ChatPayload(BaseModel):
    user_id: str = Field(..., example="usr_corporate_88")
    session_id: str = Field(..., example="sess_parallel_9")
    # Options: 'billing' or 'tech'
    target_agent: str = Field(..., example="tech")
    message: str = Field(...,
                         example="My server configuration throws connection reset errors.")


class DocumentIngestPayload(BaseModel):
    text_content: str = Field(
        ..., example="Server policy docs: Connection reset errors are fixed by updating the API endpoint URL.")


@app.post("/knowledge-base/ingest")
async def ingest_to_knowledge_base(payload: DocumentIngestPayload):
    """Utility endpoint to programmatically populate long-term knowledge data models inside Qdrant."""
    await qdrant_store.aadd_texts(texts=[payload.text_content])
    return {"status": "success", "message": "Text data chunk upserted to Qdrant storage array successful."}


@app.post("/chat/stream")
async def process_chat_stream(payload: ChatPayload):
    # Compound multi-tenant tracking isolation boundary line key string configuration
    compound_thread_key = f"{payload.user_id}:{payload.session_id}"
    config = {"configurable": {"thread_id": compound_thread_key}}

    initial_input = {
        "messages": [HumanMessage(content=payload.message)],
        "target_agent": payload.target_agent,
        "user_id": payload.user_id
    }

    async def sse_event_streamer() -> AsyncGenerator[str, None]:
        # Track and capture internal LLM generation sequences smoothly
        async for event in production_platform_agent.astream_events(initial_input, config, version="v2"):
            if event.get("event") == "on_chat_model_stream":
                token = event["data"]["chunk"].content
                if token:
                    yield f"data: {token}\n\n"

    return StreamingResponse(sse_event_streamer(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
