# Publishing ZotGrep with uv / PyPI

## Prerequisites

- Install [uv](https://docs.astral.sh/uv/getting-started/installation/) (one command: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Create a [PyPI account](https://pypi.org/account/register/)
- Generate a PyPI API token at https://pypi.org/manage/account/token/

## 1. Prepare the package

### Add a LICENSE file

The repo now uses **GPLv3**. Keep the `LICENSE` file and `pyproject.toml` aligned so PyPI and license scanners detect the same license metadata everywhere.

### Use `pyproject.toml` as the single source of truth

Modern `pip` and `uv` use `pyproject.toml`. Keep version, dependencies, scripts, and license metadata there and avoid reintroducing duplicate packaging metadata elsewhere.

### Check the package name

Search [PyPI](https://pypi.org/search/?q=zotgrep) to confirm `zotgrep` is not already taken. If it is, consider `zotgreper` or `zot-search`.

## 2. Build

```bash
uv build
```

This creates `dist/zotgrep-3.0.0.tar.gz` and `dist/zotgrep-3.0.0-py3-none-any.whl`.

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

1. Bump version in `pyproject.toml`
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

ZotGrep is licensed under **GPLv3**. Keep the `LICENSE` file in the repository and publish with matching metadata in `pyproject.toml`.

- The GPL requires the license text to be provided with the software
- Users and license scanners (FOSSA, Snyk, GitHub's license detection) rely on the `LICENSE` file and package metadata being consistent
- Some package managers and enterprise policies reject packages with missing or conflicting license metadata

If you change the license in the future, update the file and the package metadata together.

## Dependency licenses

There is no obvious blocker to shipping ZotGrep itself under **GPLv3**. The main caution is that Apache-2.0 dependencies are compatible with GPLv3, but not GPLv2-only, so avoid downgrading this project to GPLv2-only without a fresh review.

| Package | License | Attribution required? |
|---|---|---|
| Flask | BSD-3-Clause | Yes -- include copyright notice |
| pyzotero | Blue Oak Model 1.0.0 | Yes -- recipients must get license text or link to https://blueoakcouncil.org/license/1.0.0 |
| pypdfium2 | BSD-3-Clause / Apache-2.0 (dual, user's choice) | Yes -- include copyright notice |
| PDFium (bundled in pypdfium2) | Apache-2.0 | Yes -- include license text |
| pySBD | MIT | Yes -- include copyright notice |
| PyYAML | MIT | Yes -- include copyright notice |

## What you need to do

### Minimum (required for GPLv3 compliance)

1. **Keep the `LICENSE` file** with the full GPLv3 text in the repo root.

### Recommended (good practice for PyPI packages)

2. **Keep the `NOTICE` file** listing each dependency, its license, and a link. This satisfies the attribution clauses of BSD-3, Apache-2.0, and Blue Oak.

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

pySBD - MIT
  Copyright Nipun Sadvilkar
  https://github.com/nipunsadvilkar/pySBD/blob/master/LICENSE

PyYAML - MIT
  Copyright Kirill Simonov
  https://github.com/yaml/pyyaml/blob/main/LICENSE
```

### Not required but nice

3. **Keep the SPDX license expression and `license-files` in `pyproject.toml`** so PyPI displays the license cleanly and ships the GPL text with the package.

## How to audit going forward

When adding a new dependency, check its license before shipping:

```bash
# Quick check via pip
uv pip show <package> | grep License

# Or use pip-licenses for a full audit
uvx pip-licenses --from=mixed --format=table
```

Watch out for:
- **Apache-2.0 plus GPLv2-only** -- incompatible; GPLv3 is the safer choice here
- **GPL / AGPL** -- copyleft, would require you to release compatible derivative work under GPL/AGPL terms
- **LGPL** -- copyleft for modifications to the library itself, usually fine for Python imports but worth understanding
- **No license / custom license** -- avoid or get legal advice
- **Apache-2.0 patent clause** -- grants patent rights, generally favorable to you as a user
