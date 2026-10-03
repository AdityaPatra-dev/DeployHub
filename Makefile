.PHONY: help venv test test-unit test-e2e demo-python demo-node demo-docker clean

PYTHON := ./backend/.venv/bin/python
PYTEST := ./backend/.venv/bin/pytest

help:
	@echo "DeployHub Management Commands:"
	@echo "  make venv          - Create virtualenv and install dependencies"
	@echo "  make test          - Run all tests (unit & integration)"
	@echo "  make test-unit     - Run unit tests only"
	@echo "  make test-e2e      - Run end-to-end sample app deployment tests"
	@echo "  make demo-python   - Deploy Python sample app via Engine CLI"
	@echo "  make demo-node     - Deploy Node.js sample app via Engine CLI"
	@echo "  make demo-docker   - Deploy Dockerfile sample app via Engine CLI"
	@echo "  make clean         - Stop running DeployHub containers and clean temp files"

venv:
	python3 -m venv backend/.venv
	./backend/.venv/bin/pip install --upgrade pip
	./backend/.venv/bin/pip install -r backend/requirements.txt

test:
	PYTHONPATH=backend $(PYTEST) -v backend/tests/

test-unit:
	PYTHONPATH=backend $(PYTEST) -v backend/tests/test_detector.py backend/tests/test_templates.py

test-e2e:
	PYTHONPATH=backend $(PYTEST) -v backend/tests/test_engine.py

demo-python:
	PYTHONPATH=backend $(PYTHON) -m app.engine.cli deploy ./examples/python-app --name python-demo

demo-node:
	PYTHONPATH=backend $(PYTHON) -m app.engine.cli deploy ./examples/node-app --name node-demo

demo-docker:
	PYTHONPATH=backend $(PYTHON) -m app.engine.cli deploy ./examples/dockerfile-app --name docker-demo

clean:
	-docker rm -f $$(docker ps -aq --filter name="dh-") 2>/dev/null || true
	rm -rf backend/.deployhub-workspaces/
