# aws-cli-manager — Agent Instructions

## Versioning

Before committing any changes, bump the version in `pyproject.toml`:

| Tipo de cambio | Formato | Rango | Ejemplo |
|---|---|---|---|
| Ajuste pequeño (bug fix, tweak) | `0.2.x` | x: 0–9 | `0.2.0` → `0.2.1` |
| Ajuste significativo | `0.x.0` | x: 0–9 | `0.2.0` → `0.3.0` |
| Nueva funcionalidad mayor | `x.0.0` | x: 0–∞ | `0.2.0` → `1.0.0` |

## Principles

- **Modular** — cada dominio en su propio módulo (`aws/`, `db/`, `ssm/`, `kafka/`, `workflow/`)
- **Retrocompatible** — no romper comandos existentes. Si un cambio altera comportamiento, version mayor
- **Versionable** — todo cambio se versiona, se commitea y se pushea

## Workflow

When a user requests an adjustment:

1. Make the code change
2. Update `version` in `pyproject.toml`
3. `git add -A && git commit -m "tipo: descripción concisa"`
4. `git push`

## Commit message format

Use conventional commits:
- `feat:` — new feature
- `fix:` — bug fix
- `refactor:` — code restructuring
- `docs:` — documentation only
- `chore:` — tooling, config, dependencies

## Config files

Files under `config/env.*` (without `.example`) are gitignored.
Never commit real credentials or environment-specific values.
Always update the `.example` templates when the config shape changes.
