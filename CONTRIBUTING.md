# Contributing

Contributions are welcome, and they are greatly appreciated!
Every little bit helps, and credit will always be given.

If you have a suggestion for improvements, please fork the repo and create a pull request. You can also simply open an issue. Don't forget to rate the project! Thanks again!

1. Fork the Project
1. Create your Feature Branch (git checkout -b feature/AmazingFeature)
1. Commit your Changes (git commit -m 'Add some AmazingFeature')
1. Push to the Branch (git push origin feature/AmazingFeature)
1. Open a Pull Request

## Dev environment setup

### Initial setup
You only need two tools, [Poetry](https://github.com/python-poetry/poetry)
and [Copier](https://github.com/copier-org/copier).

Poetry is used as a package manager. Copier is used for the project structure (scaffolding).

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

A conda [environment.yaml](./environment.yaml) is provided inside this repo.

### Dev setup

Install the projects code and all dependencies with:

```bash
poetry install
```

## Running tests

## Serving docs


Install the optional docs depdendencies with:

```bash
poetry install --only=docs
```

Run the build process with:

```bash
make build-docs
```

To view the docs copy the content of the [docs/_build](./docs/_build) folder to a webserver or use VSCode and the [Live server extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode.live-server).
