# Contributing

Bug reports, documentation fixes, tests, and code contributions are welcome.
For a larger change, open an issue first to discuss the problem and approach.

## Report a bug

Include your operating system, Python version, Task Harbor version, provider,
the command you ran, and steps to reproduce. Remove credentials and private
repository content from logs before sharing them.

## Work on the CLI

Fork and clone the repository, then create a branch for your change.

```sh
python -m pip install -e ".[dev]"
python -m pytest
```

Tests use simulated providers and temporary Git repositories. Live evaluation
consumes provider usage; see [EVALUATION.md](EVALUATION.md) before running it.
Add regression coverage for behavior changes. Describe the problem, the change,
and your validation in the pull request.

## Work on the website

See [website/README.md](website/README.md) for preview and build commands. Keep
product claims tied to implemented behavior and label illustrative output.
Check narrow mobile layouts, keyboard navigation, and installation copying.

Contributions are provided under this repository's [MIT License](LICENSE).
