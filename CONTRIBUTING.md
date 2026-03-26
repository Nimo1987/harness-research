# Contributing to Harness Research

Thank you for your interest in contributing to Harness Research!

## How to Contribute

### Reporting Issues

- Use the [GitHub Issues](https://github.com/Nimo1987/harness-research/issues) to report bugs or suggest features
- Include steps to reproduce, expected behavior, and actual behavior
- Attach relevant log output if available

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Ensure all scripts pass syntax checks: `python3 -m py_compile scripts/*.py`
5. Test with a real research topic if possible
6. Commit with a clear message
7. Push to your fork and open a Pull Request

### Development Guidelines

- **Don't break the state machine** — step IDs and ordering are critical. If you add a step, update `STEPS` in `run_research.py`, `SKILL.md`, and `ARCHITECTURE.md`.
- **Code steps should be deterministic** — no randomness, no LLM calls in CODE steps.
- **LLM steps should have clear I/O** — define exact input variables and output format.
- **Degrade gracefully** — missing API keys should skip the data source, not crash the pipeline.
- **No hardcoded secrets** — all API keys must come from environment variables.

### Areas Where Help is Wanted

- Additional data source integrations (more government APIs, more countries)
- Improved source tier database (`source_tiers.yaml`) — adding more domains
- Better date parsing in `craap_code_score.py`
- Localization of prompt templates
- Test suite development

## Code of Conduct

Be respectful. Be constructive. Focus on the work.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
