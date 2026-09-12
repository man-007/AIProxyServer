PYTHON ?= .venv/bin/python
UVICORN ?= $(PYTHON) -m uvicorn
APP ?= proxy_gateway.main:app
HOST ?= 127.0.0.1
PORT ?= 8080
export PYTHONPATH := src

.PHONY: install test run docker-build docker-up docker-down

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

run:
	NVIDIA_API_KEY=$${NVIDIA_API_KEY:-dummy} $(UVICORN) $(APP) --host $(HOST) --port $(PORT)

docker-build:
	docker build -t claude-nvidia-proxy .

docker-up:
	docker compose up --build

docker-down:
	docker compose down
