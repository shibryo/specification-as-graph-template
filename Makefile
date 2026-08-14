.PHONY: validate render check

# Set DIR to apply the tools to another specification graph directory,
# e.g. `make render DIR=examples/symphony/spec`.
DIRFLAG := $(if $(DIR),--dir $(DIR),)

validate:
	python tools/spec.py validate $(DIRFLAG)

render:
	python tools/spec.py render $(DIRFLAG)

check:
	python tools/spec.py check $(DIRFLAG)
