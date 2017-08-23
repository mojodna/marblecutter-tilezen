PATH := node_modules/.bin:$(PATH)

.NOTPARALLEL:
.ONESHELL:

tmp := $(shell mktemp -u)

deploy-apex: project.json
	apex deploy -l debug -E environment.json

project.json: project.json.hbs .env node_modules/.bin/interp
	interp < $< > $@

deploy-up: up.json
	up

up.json: up.json.hbs .env node_modules/.bin/interp
	interp < $< > $@

node_modules/.bin/interp:
	npm install interp

deps/deps.tgz: deps/Dockerfile deps/required.txt
	docker run --rm --entrypoint tar $$(docker build --build-arg http_proxy=$(http_proxy) -q -f $< .) zc -C /var/task . > $@

clean:
	rm -f deps/deps.tgz

server:
	docker build --build-arg http_proxy=$(http_proxy) -t quay.io/mojodna/marblecutter-tilezen .
