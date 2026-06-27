# Spin up Qdrant Vector Engine locally
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant

# Install standard packages 
pip install fastapi uvicorn langgraph langchain langchain-core langchain-openai langchain-qdrant pydantic
