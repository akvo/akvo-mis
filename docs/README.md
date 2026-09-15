# Akvo MIS documentation

User-facing documentation, written in reStructuredText under `source/` and
built with [Sphinx](https://www.sphinx-doc.org/). The live site is published to
[ReadTheDocs](https://akvo-mis.readthedocs.io/).

## Building locally

### With uv (recommended)

No manual Python, pip, or Sphinx install needed —
[uv](https://docs.astral.sh/uv/) reads `pyproject.toml`/`uv.lock` and
provisions the pinned interpreter and dependencies on first run:

```bash
cd docs
uv run make html      # output in build/html/
```

The toolchain is pinned to Python 3.10 and `sphinx-rtd-theme==1.0.0`, matching
the theme deployed on ReadTheDocs.

For a live-reload preview while editing — rebuilds and refreshes the browser on
every save (`sphinx-autobuild` ships as a dev dependency):

```bash
cd docs
# port 8899 to avoid the dev stack, which uses 3000/5050/5432/8000/8888
uv run sphinx-autobuild --port 8899 source build/html   # http://127.0.0.1:8899
```

### With Docker

Uses a prebuilt Sphinx image; needs only Docker:

```bash
cd docs
./generate.sh
```

### With a manual pip install

If you already manage your own environment:

```bash
cd docs
pip install -r requirements.txt
make html
```
