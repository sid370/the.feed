.PHONY: help db install migrate reset seed tick ticks loop status api web test live

help:
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

db:        ## start local postgres
	docker compose up -d db
	@until docker compose exec -T db pg_isready -U charsocial >/dev/null 2>&1; do sleep 1; done
	@echo "postgres ready on :5433"

install:   ## create venv and install
	python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"
	@echo "installed. activate with: source .venv/bin/activate"

migrate:   ## apply schema
	.venv/bin/python -m charsocial.worker.main migrate

reset:     ## drop and recreate schema
	.venv/bin/python -m charsocial.worker.main reset

seed:      ## seed the starting cast
	.venv/bin/python -m charsocial.worker.main seed

tick:      ## run one tick
	.venv/bin/python -m charsocial.worker.main tick

ticks:     ## run 20 ticks (phase 1 verification)
	.venv/bin/python -m charsocial.worker.main tick --times 20 --seed 1

loop:      ## run the worker on its interval
	.venv/bin/python -m charsocial.worker.main loop

status:    ## world state summary
	.venv/bin/python -m charsocial.worker.main status

api:       ## run the read API on :8000
	.venv/bin/uvicorn charsocial.api.main:app --reload --port 8000

web:       ## run the frontend on :3000
	cd web && npm install && npm run dev

test:      ## run tests
	.venv/bin/pytest -q

live:      ## switch to the real provider for this shell
	@echo 'export LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-...'

kimi:      ## switch to kimi for this shell
	@echo 'export LLM_PROVIDER=kimi  # KIMI_API_KEY is already in your zshrc'
