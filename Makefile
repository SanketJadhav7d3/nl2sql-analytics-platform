# Convenience targets. On Windows without `make`, run the underlying commands
# shown in the README directly.

.PHONY: db-up db-down db-logs load reload psql

db-up:        ## start Postgres
	docker compose up -d

db-down:      ## stop Postgres (keeps volume)
	docker compose down

db-logs:
	docker compose logs -f db

load:         ## create schemas + load CSVs + build analytics
	python -m src.warehouse.load

psql:         ## open a psql shell in the container
	docker compose exec db psql -U analytics -d analytics
