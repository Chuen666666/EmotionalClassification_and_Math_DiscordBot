# Repository Guide for AI Agents

## Runtime and dependencies

- Use Python 3.14, as declared in `.python-version`.
- Edit direct runtime dependencies in `requirements.in` and development tools in `requirements-dev.in`.
- Keep the official PyTorch CPU index and `+cpu` build; the application explicitly runs inference on CPU and must not pull multi-gigabyte CUDA dependencies into Render or CI.
- `requirements.txt` and `requirements-dev.txt` are generated, hash-locked files. Do not edit them by hand.
- Regenerate both locks with `uv pip compile`, `--generate-hashes`, `--universal`, `--python-version 3.14`, `--upgrade`, `--index-strategy unsafe-best-match`, and `--emit-index-url`; exact pins and hashes constrain resolution across PyPI and the official PyTorch index.
- Install production dependencies with `python -m pip install --require-hashes -r requirements.txt`.
- Install the development environment with `python -m pip install --require-hashes -r requirements-dev.txt`.

## Application entry points

- `python math_bot.py` starts the Discord bot and its Render health endpoint.
- `python emo_cla.py` trains and saves the BERT emotion model. It needs the local training workbook and downloads the base model.
- Never commit bot tokens, channel configuration, trained models, training data, or downloaded archives.

## Required checks

Run these before opening a pull request:

```text
python -m compileall -q math_bot.py emo_cla.py
ruff check .
ruff format --check .
pre-commit run --all-files
```

Changes must go through a pull request. Do not push directly to `main`; CI must pass before merging.
