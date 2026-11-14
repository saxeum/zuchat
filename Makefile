.DEFAULT_GOAL := help

# The one bootstrap input: your DeepSeek key, outside the repo.
KEY_FILE ?= $(HOME)/.config/zuchat/deepseek.token
OAUTH_JSON ?= $(HOME)/.config/zuchat/google-oauth.json
SESSION_SECRET ?= $(shell cat $(HOME)/.config/zuchat/session-secret 2>/dev/null)
GOOGLE_CLIENT_ID ?= $(shell python3 scripts/google_client.py id $(OAUTH_JSON) 2>/dev/null)
GOOGLE_CLIENT_SECRET ?= $(shell python3 scripts/google_client.py secret $(OAUTH_JSON) 2>/dev/null)
export GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET SESSION_SECRET ALLOWED_EMAILS APP_BASE_URL
DEEPSEEK_API_KEY ?= $(shell cat $(KEY_FILE) 2>/dev/null)
export DEEPSEEK_API_KEY

MSG ?= hello
LOCAL_URL ?= http://127.0.0.1:8000
DOCKER_URL ?= http://127.0.0.1:8001

.PHONY: help test lint up down image dev oauth-status chat smoke chat-local smoke-local \
        tf-init tf-plan tf-apply tf-fmt github-remote

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up: ## Build and start the app container
	docker compose up -d --build

down: ## Stop the container
	docker compose down

image: ## Build the app image
	docker build -t zuchat .

test: ## Unit tests: local venv, no network, no server
	uv run pytest

lint: ## Lint the source and tests
	uv run ruff check src tests

dev: ## Run the app locally on :8000 with auto-reload
	DEEPSEEK_API_KEY="$(DEEPSEEK_API_KEY)" uv run fastapi dev src/zuchat/main.py

oauth-status: ## Show whether the Google OAuth config is loaded (masked)
	@echo "client_id     $$(printf %s '$(GOOGLE_CLIENT_ID)' | cut -c1-12)... ($(shell printf %s '$(GOOGLE_CLIENT_ID)' | wc -c) chars)"
	@echo "client_secret $$(test -n '$(GOOGLE_CLIENT_SECRET)' && echo set || echo MISSING)"
	@echo "session       $$(test -n '$(SESSION_SECRET)' && echo set || echo 'MISSING (cookies reset each boot)')"

chat: ## Chat with the CONTAINER (default, :8001)
	@APP_URL=$(DOCKER_URL) ./scripts/chat.sh "$(MSG)"

smoke: ## End-to-end check of the CONTAINER (default)
	@APP_URL=$(DOCKER_URL) HINT="start the container: make up" ./scripts/smoke.sh

chat-local: ## Chat with the LOCAL dev server (make dev, :8000)
	@APP_URL=$(LOCAL_URL) ./scripts/chat.sh "$(MSG)"

smoke-local: ## End-to-end check of the LOCAL dev server
	@APP_URL=$(LOCAL_URL) HINT="start the local server: make dev" ./scripts/smoke.sh

TF_DIR ?= terraform/github

tf-init: ## Initialise the GitHub Terraform root
	cd $(TF_DIR) && terraform init

tf-plan: ## Plan GitHub repository changes
	cd $(TF_DIR) && terraform plan

tf-apply: ## Apply GitHub repository changes
	cd $(TF_DIR) && terraform apply

tf-fmt: ## Format Terraform files
	terraform fmt -recursive

github-remote: ## Point origin at the repository Terraform created
	git remote add origin "$$(cd $(TF_DIR) && terraform output -raw ssh_clone_url)" 2>/dev/null \
	  || git remote set-url origin "$$(cd $(TF_DIR) && terraform output -raw ssh_clone_url)"
	@git remote get-url origin
