
# You can set these variables from the command line, and also
# from the environment for the first two.
PROJECT := $(shell basename "$$(readlink -f .)")
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = doc
BUILDDIR      = doc_build
POETRY        = poetry

SHELL := /bin/bash

shPRJ2WHEEL = function prj2wheel () { PROJECT=$1; PVER=$$(${POETRY} version -s);echo "dist/$${PROJECT@L}-$${PVER}-py3-none-any.whl"; }
fnPRJ2WHEEL = $(shell ${shPRJ2WHEEL}; prj2wheel "$1")

.PHONY: sphinx-help all help Makefile pyproject.toml doc dist clean doc-clean
.PHONY: install

help:
	@echo "Make targets:"
	@echo "  help        - This help (the default target)"
	@echo "  sphinx-help - Help with document bulder"
	@echo "  all         - Make documentation and distribution targets"
	@echo "  dist        - Python package wheel and source dist using Poetry"
	@echo "  dist        - Distribution Python wheel"
	@echo "  doc-clean   - Destroy built documentation"
	@echo "  clean       - Destroy all built output"
	@echo "  install     - Remove (if installed), then install using pip"


all: doc dist

sphinx-help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# $(O) is meant as a shortcut for $(SPHINXOPTS).
doc: Makefile
	$(SPHINXBUILD) "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

dist: $(call fnPRJ2WHEEL,${PROJECT})

doc-clean:
	rm -rf doc_build

clean: doc-clean
	rm -rf dist

$(call fnPRJ2WHEEL,${PROJECT}): pyproject.toml
	${POETRY} build

install: $(call fnPRJ2WHEEL,${PROJECT})
	pip uninstall -y ${PROJECT}
	pip install $(call fnPRJ2WHEEL,${PROJECT})
