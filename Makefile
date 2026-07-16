up:
	docker compose -f infra/docker-compose.yml up -d --wait

down:
	docker compose -f infra/docker-compose.yml down -v

test:
	ruff check . && pytest -q

.PHONY: up down test
