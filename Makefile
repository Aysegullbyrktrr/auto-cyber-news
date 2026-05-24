.PHONY: setup install validate format lint typecheck test clean init-db migrate db-status run-ingestion run-analysis run-once digest docker-build docker-up docker-down validate-config

PYTHON ?= python3

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -r requirements-dev.txt

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

validate: lint typecheck test

format:
	ruff format src tests

lint:
	ruff check src tests
	ruff format --check src tests

typecheck:
	mypy src

test:
	pytest

init-db:
	PYTHONPATH=src $(PYTHON) -m auto_cyber_news init-db

migrate:
	PYTHONPATH=src $(PYTHON) -m auto_cyber_news migrate

db-status:
	PYTHONPATH=src $(PYTHON) -m auto_cyber_news db-status

run-once:
	PYTHONPATH=src $(PYTHON) -m auto_cyber_news run-once

run-ingestion:
	PYTHONPATH=src $(PYTHON) -m auto_cyber_news run-ingestion

run-analysis:
	PYTHONPATH=src $(PYTHON) -m auto_cyber_news run-analysis

run-scheduler:
	PYTHONPATH=src $(PYTHON) -m auto_cyber_news run-scheduler

send-test-telegram:
	PYTHONPATH=src $(PYTHON) -m auto_cyber_news send-test-telegram

send-test-email:
	PYTHONPATH=src $(PYTHON) -m auto_cyber_news send-test-email

digest:
	PYTHONPATH=src $(PYTHON) -m auto_cyber_news digest

validate-config:
	PYTHONPATH=src $(PYTHON) -m auto_cyber_news validate-config

docker-build:
	docker build -t auto-cyber-news:local .

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage build dist *.egg-info
