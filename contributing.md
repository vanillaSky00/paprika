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

Merge in the local repo:
```
git pull origin <branch> --no-rebase
# And tne edit with text editor, finally then push
git push origin <branch>
```

### Branch Naming Conventions
```
<type>/<short-description>
```

```
feature/   → new features or enhancements
bugfix/    → fixes for issues or regressions
hotfix/    → urgent fixes applied directly to production
refactor/  → code restructuring without behavior changes
test/      → adding or updating tests
docs/      → documentation-only updates
chore/     → CI, scripts, dependency updates
```
Example:
```
feature/agent-mind-langgraph
feature/tools-weather-api
feature/login-endpoint

bugfix/memory-null-location
bugfix/api-timeout-handling

refactor/llm-client-factory
refactor/memory-repo-structure

test/tools-weather-mock
test/llm-openai-client

docs/update-contributing
docs/add-api-reference

chore/bump-deps
chore/cleanup-dockerfile
```
Rules
- Use kebab-case for descriptions (`my-new-feature`)
- Keep names short but meaningful
- Avoid branch names like `fix`, `temp`

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

### PR Naming Conventions
```
<type>(<scope>): <short summary>
```
### Common Scopes
Use directory names to indicate the affected area:
```
agent
memory
tools
llm
api
config
scripts
docker
docs
tests
core
```
Examples
```
feat(tools): add WeatherToolBuilder
feat(config): set default OPENWEATHER_BASE_URL
feat(llm): add Ollama client support
refactor(memory): simplify pgvector repo init
test(tools): mock weather API for unit tests
```
