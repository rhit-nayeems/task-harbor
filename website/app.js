const button = document.querySelector("#copy");
button.addEventListener("click", async () => {
  const command = document.querySelector("#command");
  const feedback = document.querySelector("#copy-feedback");
  try {
    await navigator.clipboard.writeText(
      command.textContent.replace(/\s+/g, " ").trim(),
    );
    button.textContent = "Copied";
    feedback.textContent = "Installation command copied.";
  } catch {
    const range = document.createRange();
    range.selectNodeContents(command);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    feedback.textContent = "Command selected. Use your device’s copy action.";
  }
});
