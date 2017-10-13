PATH := node_modules/.bin:$(PATH)

deploy-apex: project.json deps/tiler-deps.tgz
	apex deploy -l debug -E environment.json

.PHONY: project.json
project.json: project.json.hbs node_modules/.bin/interp
	interp < $< > $@

deploy-up: up.json deps/tiler-deps.tgz
	up

# always build this in case the *environment* changes
.PHONY: up.json
up.json: up.json.hbs node_modules/.bin/interp
	interp < $< > $@

node_modules/.bin/interp:
	npm install interp

deps/tiler-deps.tgz: deps/Dockerfile.tiler deps/tiler-required.txt
	docker run --rm --entrypoint tar $$(docker build --build-arg http_proxy=$(http_proxy) -t marblecutter-tilezen-tiler-deps -q -f $< .) zc -C /var/task . > $@

clean:
	rm -f deps/tiler-deps.tgz

server:
	docker build --build-arg http_proxy=$(http_proxy) -t quay.io/mojodna/marblecutter-tilezen .
