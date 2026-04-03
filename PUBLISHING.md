# Publishing ZotGrep with uv / PyPI

## Prerequisites

- Install [uv](https://docs.astral.sh/uv/getting-started/installation/) (one command: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Create a [PyPI account](https://pypi.org/account/register/)
- Generate a PyPI API token at https://pypi.org/manage/account/token/

## 1. Prepare the package

### Add a LICENSE file

You declare MIT in `setup.py` and `pyproject.toml`, but there is **no LICENSE file in the repo**. PyPI and most license scanners expect one. Create `LICENSE` in the repo root with the full MIT text and your name/year.

### Sync setup.py and pyproject.toml

`setup.py` is only needed for legacy `pip install -e .` support. The authoritative config is `pyproject.toml`. Make sure both declare the same version, deps, and entry points. Consider dropping `setup.py` entirely -- modern `pip` and `uv` only need `pyproject.toml`.

### Add flask to setup.py install_requires

If keeping `setup.py`, add `"flask>=3.0"` to `install_requires` to match `pyproject.toml`.

### Check the package name

Search [PyPI](https://pypi.org/search/?q=zotgrep) to confirm `zotgrep` is not already taken. If it is, consider `zotgreper` or `zot-search`.

## 2. Build

```bash
uv build
```

This creates `dist/zotgrep-2.1.0.tar.gz` and `dist/zotgrep-2.1.0-py3-none-any.whl`.

## 3. Test on TestPyPI first

```bash
uv publish --publish-url https://test.pypi.org/legacy/ --token pypi-YOUR_TEST_TOKEN
```

Then verify:
```bash
uvx --index-url https://test.pypi.org/simple/ zotgrep --version
```

## 4. Publish to PyPI

```bash
uv publish --token pypi-YOUR_TOKEN
```

## 5. Users install and run

```bash
# Option A: one-shot run, no install
uvx zotgrep --web

# Option B: install into a project
uv add zotgrep
zotgrep --web

# Option C: traditional pip
pip install zotgrep
zotgrep --web
```

## 6. Updating

1. Bump version in `pyproject.toml` (and `setup.py` / `__init__.py` if present)
2. `uv build`
3. `uv publish --token pypi-YOUR_TOKEN`

## 7. Optional: GitHub Actions release workflow

Add `.github/workflows/publish.yml` to auto-publish on tag push:

```yaml
name: Publish to PyPI
on:
  push:
    tags: ["v*"]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv build
      - run: uv publish --token ${{ secrets.PYPI_TOKEN }}
```

Store your PyPI token as a GitHub Actions secret named `PYPI_TOKEN`.

---

# License compliance

## Your license

ZotGrep declares **MIT** in `setup.py` classifiers and `pyproject.toml`, but **no `LICENSE` file exists in the repository**. You must add one before publishing -- PyPI will accept the upload without it, but:

- The MIT license requires the full text to be included with the software
- Users and license scanners (FOSSA, Snyk, GitHub's license detection) won't recognize your project as MIT without the file
- Some package managers and enterprise policies reject packages with no detectable license

Create a `LICENSE` file in the repo root with the standard MIT text, your name, and the year.

## Dependency licenses

All direct dependencies use permissive licenses. No GPL/copyleft concerns.

| Package | License | Attribution required? |
|---|---|---|
| Flask | BSD-3-Clause | Yes -- include copyright notice |
| pyzotero | Blue Oak Model 1.0.0 | Yes -- recipients must get license text or link to https://blueoakcouncil.org/license/1.0.0 |
| pypdfium2 | BSD-3-Clause / Apache-2.0 (dual, user's choice) | Yes -- include copyright notice |
| PDFium (bundled in pypdfium2) | Apache-2.0 | Yes -- include license text |
| NLTK | Apache-2.0 | Yes -- include license text |
| PyYAML | MIT | Yes -- include copyright notice |

## What you need to do

### Minimum (required for MIT compliance)

1. **Add a `LICENSE` file** with the MIT license text to the repo root.

### Recommended (good practice for PyPI packages)

2. **Add a `THIRD_PARTY_LICENSES` or `NOTICE` file** listing each dependency, its license, and a link. This satisfies the attribution clauses of BSD-3, Apache-2.0, and Blue Oak. Example format:

```
This project uses the following third-party packages:

Flask - BSD-3-Clause
  Copyright Pallets
  https://github.com/pallets/flask/blob/main/LICENSE.txt

pyzotero - Blue Oak Model License 1.0.0
  Copyright Contributors
  https://blueoakcouncil.org/license/1.0.0

pypdfium2 - BSD-3-Clause / Apache-2.0
  Copyright pypdfium2-team
  https://github.com/pypdfium2-team/pypdfium2/blob/main/LICENSES/

NLTK - Apache License 2.0
  Copyright NLTK Project
  https://github.com/nltk/nltk/blob/develop/LICENSE.txt

PyYAML - MIT
  Copyright Kirill Simonov
  https://github.com/yaml/pyyaml/blob/main/LICENSE
```

### Not required but nice

3. **Add `license = {file = "LICENSE"}` to `pyproject.toml`** under `[project]` so PyPI displays the license text on the package page.

## How to audit going forward

When adding a new dependency, check its license before shipping:

```bash
# Quick check via pip
uv pip show <package> | grep License

# Or use pip-licenses for a full audit
uvx pip-licenses --from=mixed --format=table
```

Watch out for:
- **GPL / AGPL** -- copyleft, would require you to release under GPL too
- **LGPL** -- copyleft for modifications to the library itself, usually fine for Python imports but worth understanding
- **No license / custom license** -- avoid or get legal advice
- **Apache-2.0 patent clause** -- grants patent rights, generally favorable to you as a user
