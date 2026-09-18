VENV=.venv
PY=${VENV}/bin/python
PIP=${VENV}/bin/pip

.PHONY: venv install migrate revision seed seedjobs test runserver runconsumer runconsumerminimal falkor-run falkor-verify scrape process ingest clean

venv:
	python -m venv ${VENV}

install: venv
	. ${VENV}/bin/activate && ${PIP} install -r requirements.txt

migrate: install
	. ${VENV}/bin/activate && DATABASE_URL=${DATABASE_URL:-sqlite:///career_graph.db} alembic upgrade head

revision:
	@echo "Usage: make revision m=\"message\""
	. ${VENV}/bin/activate && DATABASE_URL=${DATABASE_URL:-sqlite:///career_graph.db} alembic revision --autogenerate -m "${m}"

seed: install
	. ${VENV}/bin/activate && python scripts/seed_data.py

seedjobs: install
	. ${VENV}/bin/activate && python scripts/seed_jobs.py

test: install
	. ${VENV}/bin/activate && pytest -q

runserver: install
	. ${VENV}/bin/activate && uvicorn career_graph.api.app:app --reload --host 0.0.0.0 --port 8000

runconsumer: install
	SQS_QUEUE_URL=${SQS_QUEUE_URL} . ${VENV}/bin/activate && python scripts/run_sqs_consumer.py

runconsumerminimal: install
	SQS_QUEUE_URL=${SQS_QUEUE_URL} . ${VENV}/bin/activate && python scripts/run_sqs_consumer_minimal.py

falkor-run:
	bash scripts/run_falkordb.sh

falkor-verify: install
	. ${VENV}/bin/activate && python scripts/falkor_verification.py

# --- Scraper + Ingestion (PRD Layer 2) ---
SCRAPE_SOURCES ?= greenhouse lever remoteok arbeitnow
SCRAPE_LIMIT ?= 10

scrape: install
	GREENHOUSE_BOARD_TOKEN=$(GREENHOUSE_BOARD_TOKEN) LEVER_COMPANY=$(LEVER_COMPANY) \
		. ${VENV}/bin/activate && python scripts/run_scraper.py \
		--sources $(SCRAPE_SOURCES) --limit $(SCRAPE_LIMIT)

process: install
	. ${VENV}/bin/activate && python scripts/process_jobs.py --file fixtures/scraped/jobs.json

process-sqs: install
	. ${VENV}/bin/activate && python scripts/process_jobs.py --queue

ingest: install
	ARGS=""; \
	[ -n "$(RESUME)" ] && ARGS="$$ARGS --resume $(RESUME)"; \
	[ -n "$(GITHUB_USERNAME)" ] && ARGS="$$ARGS --github $(GITHUB_USERNAME)"; \
	. ${VENV}/bin/activate && python scripts/ingest_candidate.py $$ARGS

clean:
	rm -f career_graph.db