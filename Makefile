.PHONY: verify browser demo
verify:
	uv lock --check
	uv sync --frozen
	uv run python manage.py check
	uv run python manage.py makemigrations --check --dry-run
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy config reconciliation
	uv run pytest
	uv run python manage.py evaluate
browser:
	uv run pytest tests/test_browser.py -m browser
demo:
	uv run python manage.py demo
