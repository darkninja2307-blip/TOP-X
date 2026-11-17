# make install  -> install python packages
# make db       -> create database + tables (asks for MySQL root password)
# make start    -> run the website on http://localhost:5000
# make admin ID=123456789  -> make a Discord user an admin
PY ?= python3

.PHONY: start install db admin env
env:
	@test -f .env || (cp .env.example .env && echo "Created .env - open it and fill in your Discord + DB details, then run: make start" && exit 1)

install:
	$(PY) -m pip install -r requirements.txt

db:
	mysql -u root -p < schema.sql

start: env
	@$(PY) -c "import flask, mysql.connector, requests" 2>/dev/null || $(PY) -m pip install -r requirements.txt
	@echo "TOP-X running at http://localhost:5000"
	$(PY) app.py

admin: env
	$(PY) -m flask --app app make-admin $(ID)
