.PHONY: run bot api worker migrate test lint build clean

run:
	docker compose up --build

build:
	docker compose build

migrate:
	docker compose run --rm migrate

bot:
	python scripts/run_bot.py

api:
	uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	python run_worker.py

test:
	pytest -q

lint:
	ruff check app tests

clean:
	docker compose down -v
	find . -type d -name __pycache__ | xargs rm -rf

shell-db:
	docker compose exec db psql -U livematch -d livematch

shell-redis:
	docker compose exec redis redis-cli
