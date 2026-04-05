FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY paperless_rag_sync/ paperless_rag_sync/

CMD ["python", "-m", "paperless_rag_sync.main"]
