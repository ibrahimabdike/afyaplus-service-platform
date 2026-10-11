FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY auth.py logistics_mcp.py clinics.json ./
COPY agent/agent_api.py ./
EXPOSE 8001
CMD ["uvicorn", "agent_api:app", "--host", "0.0.0.0", "--port", "8001"]
