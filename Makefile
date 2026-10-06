.DEFAULT_GOAL := help


# ============================================================
# Configuration
# ============================================================

IMAGE     := greth-offensive:latest
CONTAINER := greth-offensive
COMPOSE   := docker compose -f docker-compose.yml


# ============================================================
# Colors
# ============================================================

BOLD  := \033[1m
DIM   := \033[2m
GREEN := \033[32m
RED   := \033[31m
RESET := \033[0m


# ============================================================
# Helpers
# ============================================================

define RUN
	@printf "$(DIM)  ▸  $(1)$(RESET)\n"
	@$(1) && \
		printf "$(GREEN)$(BOLD)  ✓  $(2)$(RESET)\n" || \
		{ printf "$(RED)$(BOLD)  ✗  $(3)$(RESET)\n"; exit 1; }
endef


# ============================================================
# Help
# ============================================================

.PHONY: help

help:
	@printf "\n"
	@printf "$(BOLD)  GRETH$(RESET)  $(DIM)— AI hacking adversary$(RESET)\n"
	@printf "\n"

	@printf "$(BOLD)  Python$(RESET)\n"
	@printf "    $(GREEN)install$(RESET)        Install dependencies via uv\n"
	@printf "    $(GREEN)run$(RESET)            Run the application\n"
	@printf "    $(GREEN)test$(RESET)           Run the test suite\n"
	@printf "    $(GREEN)lint$(RESET)           Check linting\n"
	@printf "    $(GREEN)lint-fix$(RESET)       Auto-fix linting issues\n"
	@printf "    $(GREEN)format$(RESET)         Format source code\n"
	@printf "    $(GREEN)format-check$(RESET)   Check formatting\n"
	@printf "    $(GREEN)pyclean$(RESET)        Remove Python caches\n"
	@printf "\n"

	@printf "$(BOLD)  Build$(RESET)\n"
	@printf "    $(GREEN)build$(RESET)          Build container image\n"
	@printf "    $(GREEN)rebuild$(RESET)        Force full rebuild (no cache)\n"
	@printf "\n"

	@printf "$(BOLD)  Cleanup$(RESET)\n"
	@printf "    $(GREEN)purge$(RESET)          $(RED)⚠$(RESET)  Remove everything including workspace volume\n"
	@printf "\n"


# ============================================================
# Python
# ============================================================

.PHONY: install run test lint lint-fix format format-check pyclean

install:
	$(call RUN,\
		uv sync,\
		dependencies ready,\
		sync failed — check pyproject.toml)


run:
	$(call RUN,\
		uv run python main.py,\
		exited cleanly,\
		application exited with error)


test:
	$(call RUN,\
		uv run pytest,\
		all tests passed,\
		one or more tests failed)


lint:
	$(call RUN,\
		uv run ruff check .,\
		no issues found,\
		linting issues detected)


lint-fix:
	$(call RUN,\
		uv run ruff check . --fix,\
		issues fixed,\
		could not fix all issues)


format:
	$(call RUN,\
		uv run ruff format .,\
		source formatted,\
		formatting failed)


format-check:
	$(call RUN,\
		uv run ruff format --check .,\
		formatting clean,\
		formatting issues found — run: make format)


pyclean:
	$(call RUN,\
		find . -type d -name "__pycache__" -prune -exec rm -rf {} + ; \
		find . -type d -name ".pytest_cache" -prune -exec rm -rf {} + ; \
		find . -type d -name ".ruff_cache" -prune -exec rm -rf {} + ; \
		find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete,\
		caches removed,\
		clean failed)


# ============================================================
# Docker
# ============================================================

.PHONY: build rebuild purge

build:
	$(call RUN,\
		$(COMPOSE) build --progress=plain,\
		image ready,\
		build failed — check Dockerfile or network)


rebuild:
	$(call RUN,\
		$(COMPOSE) build --progress=plain --no-cache,\
		clean image ready,\
		rebuild failed — check Dockerfile or network)


purge:
	@printf "$(RED)$(BOLD)  ⚠   WARNING: workspace volume and all data will be deleted.$(RESET)\n"
	@printf "$(DIM)  Type YES to confirm: $(RESET)" && read confirm && \
		[ "$$confirm" = "YES" ] || exit 1
	$(call RUN,\
		$(COMPOSE) down --volumes --rmi local,\
		everything removed,\
		purge failed)
