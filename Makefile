.PHONY: run migrate bot api worker test lint fmt build up down logs

run: up

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	. .venv/bin/activate && alembic upgrade head

bot:
	. .venv/bin/activate && python scripts/run_bot.py

api:
	. .venv/bin/activate && uvicorn app.api.main:app --reload --port 8000

worker:
	. .venv/bin/activate && python scripts/run_worker.py

test:
	. .venv/bin/activate && pytest -q

lint:
	. .venv/bin/activate && ruff check app tests

fmt:
	. .venv/bin/activate && ruff check --fix app tests

build:
	docker compose build

venv:
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
