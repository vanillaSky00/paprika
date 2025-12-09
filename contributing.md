# Contributing 

We welcome pull requests that:

- Fix bugs or crashes
- Add small, focused features
- Improve performance or code structure
- Add / improve tests in `tests/`
- Improve docs, examples, or comments


## Ground Rules

- Do **not** push directly to `main`
- One logical change per PR
- All PRs must:
  - Pass GitHub Actions CI
  - Include tests for new or changed behavior
  - Update docs/examples if behavior changes


## Code Style

- Follow **PEP 8**
- Use **type hints** for public functions
- Prefer pure functions (no mutation of input arguments)
- Avoid hidden side effects (no unexpected I/O, globals)
- Tests under `tests/` as `test_*.py`


## Setup (using `uv`)

```bash
git clone git@github.com:vanillaSky00/paprika.git
cd paprika
````

Install dependencies:

```bash
pip install uv   # if not installed
uv sync
```

Run tests:

```bash
uv run pytest
```

Add dependencies:

```bash
uv add <package-name>
```


## Git Workflow

Always start from latest `main`:

```bash
git checkout main
git pull origin main
```

Create a new feature branch:

```bash
git checkout -b feature/my-change
```

Commit and push changes:

```bash
git add .
git commit -m "feat: short description"
git push -u origin feature/my-change
```

Branch Naming:
```
feature/
    chat
    login

bugfix/
    crash-on-start

docs/
    update-readme
```


## Open a Pull Request

On GitHub:

* Compare: `feature/my-change` → `main`
* Fill PR template:

  * What changed?
  * Why changed?
  * How tested?
* Ensure CI is green
* Address review comments

A maintainer will merge once approved 🚀