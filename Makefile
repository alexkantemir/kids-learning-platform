.PHONY: up down restart logs ps build deploy

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

ps:
	docker compose ps

build:
	docker compose build --no-cache

deploy:
	rsync -avz --exclude='.git' --exclude='node_modules' --exclude='__pycache__' \
		--exclude='.next' --exclude='postgres_data' \
		./ kids-server:/opt/kids-platform/
	ssh kids-server 'cd /opt/kids-platform && docker compose pull && docker compose up -d --build'
