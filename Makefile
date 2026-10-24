.PHONY: install dev seed test build

install:
	npm install

dev: install
	npm run dev

seed:
	npm run seed

test:
	npm test

build:
	npm run build
