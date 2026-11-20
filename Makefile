DEV_DB := job_tracker
TEST_DB := job_tracker_test

.PHONY: setup dev test lint seed eval

# Create the dev and test databases, run migrations, install dependencies.
setup:
	@test -f .env || { cp .env.example .env && echo "Created .env from .env.example"; }
	@for db in $(DEV_DB) $(TEST_DB); do \
		if psql -lqt postgres | cut -d '|' -f 1 | grep -qw $$db; then \
			echo "Database $$db already exists"; \
		else \
			createdb $$db && echo "Created database $$db"; \
		fi; \
	done
	cd backend && uv sync
	cd frontend && npm install
	cd backend && uv run alembic upgrade head

# Start the api and web processes from the Procfile.
dev:
	uv run --project backend honcho start

# Fill an empty dev database with sample data. `make seed ARGS=--reset` wipes it first.
seed:
	cd backend && uv run python -m scripts.seed $(ARGS)

# Run the prompt eval against the real model. Costs money; needs ANTHROPIC_API_KEY and
# ANTHROPIC_MODEL in .env. Writes evals/results/. Never runs in CI.
eval:
	cd backend && uv run python -m evals.run

test:
	cd backend && uv run pytest
	cd frontend && npm test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint
