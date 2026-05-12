# Code Style & Linting

This project uses modern Python tooling for code quality, entirely orchestrated by `hatch`.

## Formatting and Linting
We use [Ruff](https://docs.astral.sh/ruff/) to handle both code formatting and linting. Ruff replaces Black, isort, and Flake8, executing in milliseconds.

To format your code and fix auto-fixable lint errors, run:
```bash
hatch run fmt
```

To check for issues without modifying files (used in CI):
```bash
hatch run fmt-check
```

## Type Checking

We strictly enforce static typing using mypy.

```bash
hatch run type-check
```