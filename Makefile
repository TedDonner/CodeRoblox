PYTHON ?= python3
PYTHONPATH := src
MISE ?= mise
ROJO_BUILD_OUTPUT := build/CodeRobloxPlugin.rbxm

.PHONY: setup format lint python-test luau-test test build-plugin ci clean

setup:
	@echo "No local bootstrap needed. Ensure python3 and mise are installed."

format:
	$(MISE) trust --yes . >/dev/null && $(MISE) x -- stylua plugin/src plugin/tests

lint:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m compileall src tests scripts
	$(MISE) trust --yes . >/dev/null && $(MISE) x -- stylua --check plugin/src plugin/tests
	$(MISE) trust --yes . >/dev/null && $(MISE) x -- selene plugin/src

python-test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests -v

luau-test:
	$(MISE) trust --yes . >/dev/null && $(MISE) x -- lune run plugin/tests/run_tests.luau

test: python-test luau-test

build-plugin:
	mkdir -p build
	$(MISE) trust --yes . >/dev/null && $(MISE) x -- rojo build plugin.project.json --output $(ROJO_BUILD_OUTPUT)

ci: lint test build-plugin

clean:
	rm -rf build __pycache__ .pytest_cache
