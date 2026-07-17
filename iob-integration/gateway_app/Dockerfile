FROM python:3.11-slim

WORKDIR /app

# Install deps
COPY gateway_app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway_app/ ./gateway_app/
COPY __init__.py ./__init__.py 2>/dev/null || true

EXPOSE 8000 8001

# Default command runs gateway on 8000; ws server is separate service in compose
CMD ["uvicorn", "gateway_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
