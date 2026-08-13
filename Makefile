.PHONY: validate render check

validate:
	python tools/spec.py validate

render:
	python tools/spec.py render

check:
	python tools/spec.py check
