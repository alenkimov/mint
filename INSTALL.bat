@echo off
poetry install
poetry run playwright install
poetry run alembic upgrade head
pause
