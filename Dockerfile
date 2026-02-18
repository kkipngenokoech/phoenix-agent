FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY migrations/ migrations/
COPY sample_project/ sample_project/
COPY .env.example .env.example

ENV PYTHONPATH=src
ENV PORT=8000

EXPOSE 8000

CMD ["uvicorn", "phoenix_agent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
