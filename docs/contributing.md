# Contributing Guide

Thanks for helping improve shouldigetgas.

## ⚠️ Important disclaimer

This project was entirely **vibe-coded with Claude**, uses **Claude Haiku** internally for parts of data processing, and the output may not be **100% accurate**.

## Ways to contribute

- Report bugs with clear repro steps
- Suggest product or UX improvements
- Improve docs and data quality
- Submit code fixes and features via pull requests

## Development workflow

1. Open or claim an issue.
2. Create a branch (recommended format: `type/short-description`, e.g. `docs/readme-refresh`).
3. Make focused changes.
4. Run relevant local checks.
5. Open a PR with context and screenshots/logs when helpful.

## Code style and standards

- Keep changes small and scoped.
- Preserve zero-build frontend architecture.
- Keep region/unit handling correct (`gal` for US, `L` for Canada).
- Use environment variables; never hardcode secrets.

## Pull request checklist

- [ ] Scope is clear and limited
- [ ] Docs updated when behavior changes
- [ ] Relevant commands run successfully
- [ ] Lint/test output attached when available
- [ ] Region/unit formatting remains correct
- [ ] No secrets or hardcoded credentials

## Commit conventions

Use Conventional Commits where possible:

- `feat: ...`
- `fix: ...`
- `docs: ...`
- `refactor: ...`
- `chore: ...`

## Good first issues

Good first issues are tasks that are:
- Small and isolated
- Well-described with expected outcome
- Low-risk to core data flow
- Mostly docs, UI polish, or non-breaking improvements

## Anti-patterns to avoid

- Mixing sync and async DB patterns in backend DB access
- Hardcoding live gas prices instead of fetching from sources/fallback flow
- Breaking the cached-data contract (`frontend/data/data.json`)
- Hardcoding region lists outside `backend/config.py`
- Blocking or crashing when optional services fail (NewsAPI, Anthropic, Redis)

## Code of conduct

By participating, you agree to follow a Contributor Covenant-style code of conduct:
- Be respectful and inclusive
- Assume good intent
- Give constructive feedback
- Avoid harassment, discrimination, and abusive behavior

If you encounter harmful behavior, open a private maintainer contact issue in the repository.
