up:
	docker compose -f infra/docker-compose.yml up -d --wait

down:
	docker compose -f infra/docker-compose.yml down -v

test:
	ruff check . && pytest -q

schemas:
	python -m contracts.export_schemas

.PHONY: up down test schemas
