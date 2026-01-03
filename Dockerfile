FROM python:3.11-slim

WORKDIR /app

COPY src/ src/

RUN pip install --no-cache-dir \
    fastapi>=0.115.0 \
    uvicorn>=0.32.0 \
    pydantic>=2.0.0 \
    pydantic-settings>=2.0.0 \
    httpx>=0.27.0 \
    langchain>=0.3.0 \
    langchain-openai>=0.3.0 \
    langgraph>=0.2.0 \
    python-dotenv>=1.0.0 \
    loguru>=0.7.0 \
    pygithub>=2.0.0 \
    slack-sdk>=3.0.0 \
    jinja2>=3.0.0

ENV PYTHONPATH=/app
EXPOSE 8080

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
