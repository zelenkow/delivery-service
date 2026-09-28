PY_SRCS = .
RADON_MIN_MI = 65

.PHONY: help install lint fmt typecheck security cc mi test check

help:
	@echo "Доступные цели:"
	@echo " install   - установить зависимости"
	@echo " lint      - ruff check (с автофиксом)"
	@echo " fmt       - ruff format (проверка)"
	@echo " typecheck - mypy"
	@echo " security  - bandit"
	@echo " cc        - radon cc + quality gate (E/F)"
	@echo " mi        - radon mi + quality gate (< 65)"
	@echo " test      - pytest"
	@echo " check     - полный прогон"

install:
	uv sync

lint:
	uv run ruff check $(PY_SRCS) --fix

fmt:
	uv run ruff format $(PY_SRCS) --check

typecheck:
	uv run mypy $(PY_SRCS)

security:
	uv run bandit -r $(PY_SRCS) -lll -x .venv,venv,build,dist,migrations

cc:
	uv run radon cc -s -a $(PY_SRCS)
	@if uv run radon cc -s $(PY_SRCS) | grep -E '\((E|F)\)'; then \
		echo "❌ Radon CC: обнаружены функции со сложностью E/F"; \
		exit 1; \
	else \
		echo "✅ Radon CC: нет функций с E/F"; \
	fi

mi:
	@uv run radon mi -s $(PY_SRCS)
	@MI_BAD=$$(uv run radon mi -s $(PY_SRCS) | awk '{print $$NF}' | awk -F'[()]' '{print $$2}' | awk '$$1+0<$(RADON_MIN_MI){print}'); \
	if [ -n "$$MI_BAD" ]; then \
		echo "❌ Radon MI: найден MI < $(RADON_MIN_MI)"; \
		exit 1; \
	else \
		echo "✅ Radon MI: все файлы с MI >= $(RADON_MIN_MI)"; \
	fi

test:
	uv run pytest -v

check: lint fmt typecheck security cc mi test
	@echo "✅ Все проверки пройдены"