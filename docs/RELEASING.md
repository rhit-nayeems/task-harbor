# Publishing a release

The package and primary command stay `task-harbor`. The `harbor` package and
command already belong to another agent framework; do not add a conflicting alias.

## One-time PyPI account setup

Sign in to PyPI, verify your email, and enable two-factor authentication.
At https://pypi.org/manage/account/publishing/ add a pending GitHub publisher:

| Field | Value |
| --- | --- |
| PyPI project name | `task-harbor` |
| Owner | `rhit-nayeems` |
| Repository | `task-harbor` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

No PyPI API token needs to be stored in GitHub. Registering a pending publisher
does not guarantee that a package name is available until publishing succeeds.

## Validate before publishing

Run the **Publish Python package** workflow manually. A manual run builds and
validates distributions and tests the installed wheel; it never uploads to PyPI.
Inspect the `python-distributions` artifact from the successful run.

## Publish

1. Update the version in `pyproject.toml` and `opus_manager/cli.py` together.
2. Update the changelog and ensure tests pass on Windows and Linux.
3. Create a GitHub release with a tag exactly matching `v<package-version>`.
4. Publish the release. The workflow rebuilds, validates, tests, and publishes
   through the `pypi` environment using Trusted Publishing.
5. Confirm installation from PyPI in a fresh environment, then replace the
   GitHub installation instructions and “not on PyPI” statements in the README
   and website. Do not change them before publication succeeds.

Prereleases do not publish through this workflow. Published distribution files
cannot be replaced with new contents under the same filename/version; release
a new version for corrections. Ordinary pushes to main do not publish packages.
