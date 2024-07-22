# Contributing

Contributions are welcome, and they are greatly appreciated!
Every little bit helps, and credit will always be given.

## Initial dev environment setup

### Initial setup
You only need two tools, [Poetry](https://github.com/python-poetry/poetry)
and [Copier](https://github.com/copier-org/copier).

Poetry is unsed an a package manager. Copier is used for the project structure (scaffolding).

Install with pip:
```bash
python3 -m pip install --user pipx
pipx install poetry
pipx install copier copier-templates-extensions
```

Or create a new environment with conda/mamba:

```bash
conda install -f environment.yaml -p ./.venv
```

A conda environment.yaml is provided inside this repo.

### Dev setup

Install the projects code and all dependencies with:

```bash
poetry install
```



## Running tests

To run the tests, use:

```
make test
```

## Serving docs

You can create a new virtualenv
and install `mkdocs` and `mkdocs-material`:

```bash
python3 -m venv venv
. venv/bin/activate
pip install mkdocs mkdocs-material
mkdocs serve
```

You can also install `mkdocs` with `pipx` and
inject `mkdocs-material` in its venv,
this way you don't need to create one yourself:

```bash
python3 -m pip install --user pipx
pipx install mkdocs
pipx inject mkdocs mkdocs-material
mkdocs serve
```