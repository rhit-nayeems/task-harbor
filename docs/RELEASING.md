# Publishing a release

The package and primary command stay `task-harbor`. The `harbor` package and
command already belong to another agent framework; do not add a conflicting alias.

## Publisher configuration

Task Harbor is published on [PyPI](https://pypi.org/project/task-harbor/).
Trusted Publishing is already configured with the following GitHub identity;
normal releases do not need a new publisher or an API token.

| Field | Value |
| --- | --- |
| PyPI project name | `task-harbor` |
| Owner | `rhit-nayeems` |
| Repository | `task-harbor` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

Manage this configuration in the project's PyPI publishing settings. Maintainers
must keep their PyPI account email verified and two-factor authentication enabled.

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
5. Confirm the new version appears on PyPI, then install it in a fresh virtual
   environment from outside the source checkout. Replace `VERSION` below with
   the released version:

   ```sh
   python -m pip install --index-url https://pypi.org/simple "task-harbor==VERSION"
   task-harbor --version
   task-harbor --help
   python -m task_harbor runs --json
   ```

6. Check upgrading an existing installation with `python -m pip install --upgrade
   task-harbor`. Keep the README and website installation instructions aligned
   with the published package. These smoke checks do not call a model provider.

Prereleases do not publish through this workflow. Published distribution files
cannot be replaced with new contents under the same filename/version; release
a new version for corrections. Ordinary pushes to main do not publish packages.
