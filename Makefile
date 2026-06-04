.PHONY: lint test pre-commit pre-commit-install

lint:
	uv run ruff check .

test:
	uv run pytest

pre-commit:
	uv run pre-commit run --all-files

pre-commit-install:
	uv run pre-commit install
