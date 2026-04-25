PYTHON ?= python
UVICORN ?= uvicorn
HOST ?= 127.0.0.1
PORT ?= 8000
API_KEY ?= lablink-dev-key

.PHONY: test run smoke

test:
	pytest -q

run:
	LABLINK_API_KEY=$(API_KEY) $(UVICORN) app.main:app --host $(HOST) --port $(PORT)

smoke:
	LABLINK_API_KEY=$(API_KEY) $(UVICORN) app.main:app --host $(HOST) --port $(PORT) >/tmp/lablink-core.log 2>&1 & \
	PID=$$!; \
	sleep 2; \
	echo "Health check:"; \
	curl -fsS http://$(HOST):$(PORT)/health; \
	echo "\nMode check:"; \
	curl -fsS -H "x-api-key: $(API_KEY)" http://$(HOST):$(PORT)/mode; \
	kill $$PID; \
	wait $$PID 2>/dev/null || true
