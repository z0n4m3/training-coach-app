.PHONY: test api-up migrate

test:
	cd apps/api && pytest

api-up:
	docker compose up --build db api

migrate:
	docker compose exec api alembic upgrade head
