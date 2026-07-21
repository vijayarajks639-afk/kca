up:
	docker compose -f infra/docker-compose.yml up -d --wait

down:
	docker compose -f infra/docker-compose.yml down -v

migrate:
	alembic -c infra/alembic.ini upgrade head

downgrade:
	alembic -c infra/alembic.ini downgrade -1

test:
	ruff check . && pytest -q

schemas:
	python -m kca.contracts.export_schemas

dashboard:
	streamlit run kca/apps/demo_dashboard/app.py

.PHONY: up down migrate downgrade test schemas dashboard
.PHONY: up down migrate downgrade test
schemas:
	python -m contracts.export_schemas

.PHONY: up down test schemas
