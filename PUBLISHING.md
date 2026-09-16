# Publishing ZotGrep

ZotGrep is released to [PyPI](https://pypi.org/project/zotgrep/) by GitHub Actions. Publishing a GitHub release runs `.github/workflows/python-publish.yml`, which:

1. runs the test suite (`.github/workflows/test.yml`) on Python 3.11–3.14 against `uv.lock`,
2. checks that the release tag matches the version in `pyproject.toml` (tag `v3.2.0` ↔ `version = "3.2.0"`),
3. builds the sdist and wheel and validates them with `twine check --strict`,
4. uploads them to PyPI with [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) through the protected `pypi` environment.

No PyPI API token is stored anywhere. Do not publish from a local machine with `uv publish`.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) and the [GitHub CLI](https://cli.github.com/) (`gh`)
- One-time setup (already done for this repository):
  - PyPI → zotgrep → *Publishing*: trusted publisher for `franciscowilhelm/zotgrep`, workflow `python-publish.yml`, environment `pypi`
  - GitHub → *Settings → Environments*: an environment named `pypi` (optionally with required reviewers)
  - Recommended: a branch ruleset on `main` that requires pull requests and the `Tests` checks to pass

`pyproject.toml` is the single source of truth for version, dependencies, scripts, and license metadata.

## Release procedure

1. **Prepare a release branch** from up-to-date `main`:

   ```bash
   git switch main && git pull
   git switch -c release-X.Y.Z
   ```

2. **Bump the version** (updates `pyproject.toml` and `uv.lock` together):

   ```bash
   uv version X.Y.Z
   ```

   Follow [semantic versioning](https://semver.org/): patch for fixes, minor for new features, major for breaking changes.

3. **Update `CHANGELOG.md`**: rename the `Unreleased` heading to `## X.Y.Z - YYYY-MM-DD`.

4. **Verify locally**:

   ```bash
   uv run --locked --group test pytest -q
   rm -rf dist && uv build
   uvx twine check --strict dist/*
   ```

5. **Open and merge a pull request** into `main` once the `Tests` checks are green:

   ```bash
   git commit -am "Release X.Y.Z"
   git push -u origin release-X.Y.Z
   gh pr create --base main --title "Release X.Y.Z" --fill
   gh pr merge --merge --delete-branch
   ```

6. **Tag the merge commit and publish the GitHub release**. The release notes are the changelog section for this version:

   ```bash
   git switch main && git pull
   git tag -a vX.Y.Z -m "zotgrep X.Y.Z"
   git push origin vX.Y.Z
   gh release create vX.Y.Z --verify-tag --title "vX.Y.Z" --notes-file <notes.md>
   ```

7. **Watch the workflow and confirm the upload**:

   ```bash
   gh run watch "$(gh run list --workflow python-publish.yml -L 1 --json databaseId -q '.[0].databaseId')" --exit-status
   uvx --refresh zotgrep@X.Y.Z --version
   ```

### Pre-releases

Releases marked as *pre-release* on GitHub run the tests and build but are **not** uploaded to PyPI.

### If publishing fails

- **Tag/version mismatch**: delete the release and tag (`gh release delete vX.Y.Z --cleanup-tag`), fix the version on `main`, and tag again.
- **Tests fail**: fix on `main` through a pull request, then recreate the release on the new commit.
- PyPI never accepts the same version twice. If a broken build was already uploaded, yank it on PyPI and release the next patch version.

## Users install and run

```bash
# Option A: one-shot run, no install
uvx zotgrep --web

# Option B: install as a tool
uv tool install zotgrep
zotgrep --web

# Option C: traditional pip
pip install zotgrep
zotgrep --web
```

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
