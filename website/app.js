const stages = {
  plan: {
    status: "SCOPE DEFINED",
    description:
      "Acceptance criteria and scope are captured before the agent starts.",
    command: "cat BACKLOG.md",
    lines: [
      ["SEARCH-01 · Handle an empty search query", ""],
      ["AC-1  Empty query returns an empty list", "defined"],
      ["Scope src/search.py + tests/test_search.py", ""],
      ["Open questions", "none"],
    ],
    note: "Operator-defined agreement · saved with the run",
    count: "01 / 04",
  },
  implement: {
    status: "CHANGES ISOLATED",
    description:
      "The implementer works on a task branch in its own Git worktree.",
    command: "git diff --stat",
    lines: [
      ["src/search.py", "2 insertions(+)"],
      ["tests/test_search.py", "8 insertions(+)"],
      ["Original branch", "unchanged"],
      ["Task checkpoint", "a41c9e2"],
    ],
    note: "Separate worktree · recoverable task state",
    count: "02 / 04",
  },
  verify: {
    status: "CHECKS PASSED",
    description:
      "Checks run at the exact checkpoint. Results stay attached to the task.",
    command: "python -m pytest tests/test_search.py",
    lines: [
      ["test_empty_query_returns_empty_list", "PASS"],
      ["test_whitespace_query_returns_empty_list", "PASS"],
      ["test_existing_search_results", "PASS"],
      ["3 passed · exit code 0", ""],
    ],
    note: "Checkpoint a41c9e2 · isolated worktree",
    count: "03 / 04",
  },
  review: {
    status: "AWAITING YOUR REVIEW",
    description:
      "Inspect the full diff and check evidence before accepting the result.",
    command: "task-harbor review --run-id example-001",
    lines: [
      ["Acceptance checks", "3 passed"],
      ["Changed files", "2"],
      ["Human acceptance", "not recorded"],
      ["Auto-push to remote", "disabled"],
    ],
    note: "Local integration branch · you decide what ships",
    count: "04 / 04",
  },
};
function setStage(key) {
  const stage = stages[key];
  if (!stage) return;
  document
    .querySelectorAll("[data-stage]")
    .forEach((button) =>
      button.setAttribute(
        "aria-selected",
        String(button.dataset.stage === key),
      ),
    );
  document
    .querySelector("#demo-panel")
    .setAttribute("aria-labelledby", "step-" + key);
  document.querySelector("#demo-status").textContent = stage.status;
  document.querySelector("#demo-description").textContent = stage.description;
  document.querySelector("#demo-footnote").textContent = stage.note;
  document.querySelector("#demo-counter").textContent = stage.count;
  const terminal = document.querySelector("#demo-console");
  terminal.replaceChildren();
  const command = document.createElement("div");
  command.className = "prompt";
  command.textContent = stage.command;
  terminal.append(command);
  stage.lines.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "console-line";
    const left = document.createElement("span");
    left.textContent = label;
    const right = document.createElement("span");
    right.className = value === "PASS" ? "success" : "dim";
    right.textContent = value;
    row.append(left, right);
    terminal.append(row);
  });
}
document
  .querySelectorAll("[data-stage]")
  .forEach((button) =>
    button.addEventListener("click", () => setStage(button.dataset.stage)),
  );
const commands = {
  pip: 'python -m pip install "git+https://github.com/rhit-nayeems/task-harbor.git"',
  pipx: 'pipx install "git+https://github.com/rhit-nayeems/task-harbor.git"',
};
document.querySelectorAll("[data-install]").forEach((button) =>
  button.addEventListener("click", () => {
    document
      .querySelectorAll("[data-install]")
      .forEach((b) => b.setAttribute("aria-selected", String(b === button)));
    document.querySelector("#install-text").textContent =
      commands[button.dataset.install];
    document
      .querySelector("#install-command")
      .setAttribute("aria-labelledby", button.id);
    document.querySelector("#copy-status").textContent =
      button.dataset.install === "pipx"
        ? "Requires pipx. After installing, run pipx ensurepath and restart your terminal."
        : "Installs directly from GitHub. Not published to PyPI yet.";
    document.querySelector("#copy-command").textContent = "Copy ⧉";
  }),
);
document.querySelector("#copy-command").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(
      document.querySelector("#install-text").textContent,
    );
    document.querySelector("#copy-command").textContent = "Copied ✓";
    document.querySelector("#copy-status").textContent =
      "Command copied. Paste it into your terminal.";
  } catch {
    const range = document.createRange();
    range.selectNodeContents(document.querySelector("#install-text"));
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    document.querySelector("#copy-status").textContent =
      "Clipboard unavailable. The command is selected; use your device’s copy action.";
  }
});
document.querySelectorAll('[role="tablist"]').forEach((list) =>
  list.addEventListener("keydown", (event) => {
    if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
    const tabs = [...list.querySelectorAll('[role="tab"]')];
    let index = tabs.indexOf(document.activeElement);
    if (index < 0) return;
    event.preventDefault();
    index =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? tabs.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
            tabs.length;
    tabs[index].focus();
    tabs[index].click();
  }),
);
setStage("verify");
