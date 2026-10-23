-include .env
export

DC  := docker compose
RUN := $(DC) run --rm runner

.PHONY: setup docker-ok build infra up down reset seed index-init sync reconcile explain pull-model wait-api \
        ask trace set-acl eval agreement test policy logs upgrade-build upgrade-swap check-00 check-09 check-15

setup:        ## first run only: create .env from the template
	@if [ -f .env ]; then echo ".env already exists, left unchanged"; else cp .env.example .env && echo "created .env from .env.example"; fi
	@grep -q '^MINIO_ACCESS_KEY=' .env || echo "WARNING: .env is missing settings. Run: cp .env.example .env"

docker-ok:    ## fail fast when Docker is not running
	@docker info >/dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop, wait for it to finish starting, then retry."; exit 1; }

build: docker-ok  ## build the shared Python image
	$(DC) build runner

infra: docker-ok  ## Postgres, Redpanda, MinIO, OpenSearch
	$(DC) up -d postgres redpanda redpanda-init minio minio-init opensearch

up: docker-ok     ## everything enabled in COMPOSE_PROFILES
	$(DC) up -d --build

down:
	$(DC) down

reset:        ## delete all containers AND data volumes
	$(DC) down -v --remove-orphans

seed:
	$(RUN) python -m brimmora.seed

index-init:
	$(RUN) python -m brimmora.ingest init

sync:
	$(RUN) python -m brimmora.ingest sync

reconcile:
	$(RUN) python -m brimmora.ingest reconcile

explain:      ## make explain AS=bob Q="What caused error E-4472?"
	$(RUN) python -m brimmora.explain $(AS) "$(Q)"

pull-model:
	@if echo "$(COMPOSE_PROFILES)" | grep -q ollama; then $(DC) exec ollama ollama pull $(LLM_MODEL); else ollama pull $(LLM_MODEL); fi

wait-api:
	@for i in $$(seq 1 60); do curl -sf localhost:8000/healthz >/dev/null && echo "api ready" && exit 0; sleep 5; done; echo "api not ready after 5 minutes"; exit 1

ask:          ## make ask AS=bob Q="What caused error E-4472?"
	$(RUN) python -m brimmora.cli ask $(AS) "$(Q)"

trace:        ## make trace ID=<request_id>
	$(RUN) python -m brimmora.cli trace $(ID)

set-acl:      ## make set-acl KEY=manuals/lockout-tagout.md TAGS=group:procurement
	$(RUN) python -m brimmora.cli set-acl $(KEY) $(TAGS)

eval:
	$(RUN) python -m brimmora.evaluate run

agreement:
	$(RUN) python -m brimmora.evaluate agreement

test:
	$(RUN) pytest -q /srv/tests

policy:
	docker run --rm -v "$(CURDIR)":/project -w /project openpolicyagent/conftest:v0.56.0 test docker-compose.yml app/brimmora/tools.json -p policy

logs:         ## make logs S=consumer
	$(DC) logs -f --tail=100 $(S)

upgrade-build:
	$(RUN) python -m brimmora.upgrade build $(VERSION)

upgrade-swap:
	$(RUN) python -m brimmora.upgrade swap $(VERSION)

check-00:
	$(DC) run --rm --no-deps runner python -m brimmora.checks 00

check-09:
	$(DC) exec airflow airflow dags test brimmora_ingest
	$(RUN) python -m brimmora.checks 09

check-15: test policy

check-%:
	$(RUN) python -m brimmora.checks $*
