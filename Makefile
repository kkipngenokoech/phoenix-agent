.PHONY: install dev backend frontend infra test clean

# Install all dependencies
install:
	pip install -e ".[openai]"
	cd frontend && npm install

# Start both backend and frontend (dev mode)
dev:
	@echo "Starting infrastructure, backend on :8000, frontend on :3000..."
	@docker-compose up -d 2>/dev/null || echo "Warning: Docker not available — running without Redis/Postgres/Neo4j"
	@make backend & make frontend

# Backend API server
backend:
	PYTHONPATH=src uvicorn phoenix_agent.api.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend dev server
frontend:
	cd frontend && npm run dev

# Start infrastructure (Redis, PostgreSQL, Neo4j)
infra:
	docker-compose up -d

# Stop infrastructure
infra-down:
	docker-compose down

# Run sample project tests
test:
	cd sample_project && pytest tests/ -v

# Clean build artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/
