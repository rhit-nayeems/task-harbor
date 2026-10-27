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

const stages = [
  {file:'BACKLOG.md', content:'## SEARCH-01 — Handle empty queries\n\nAcceptance criteria:\n  Empty searches show a helpful message.\n  Existing search tests still pass.', title:'Define what done means.', description:'Write a task and its acceptance criteria. Harbor reads the backlog and plans the work.'},
  {file:'GIT WORKTREE', content:'original branch\n  │\n  └── task worktree\n      ├── implementation changes\n      └── checkpoint commit', title:'Give the task its own workspace.', description:'The agent implements the plan in a separate Git worktree. A checkpoint records the changes before verification.'},
  {file:'VERIFICATION RESULTS', content:'$ python -m pytest tests/test_search.py\n\n3 passed\nexit code: 0\n\nNext: model QA against acceptance criteria', title:'Check the changes.', description:'Your configured commands run first, followed by model QA. A failed required check prevents approval. These results are an example, not a live run.'},
  {file:'TASK EVIDENCE', content:'Task: SEARCH-01\nChecks: passed\nDestination: local integration branch\nHuman review: pending\n\n$ task-harbor review --run-id YOUR_RUN_ID', title:'You decide what to accept.', description:'Inspect the diff and check results. Harbor does not push changes or merge into your original branch. Find your run ID with task-harbor runs.'}
];
const stageControls = document.querySelector('.stage-controls');
stageControls.hidden = false;
stageControls.addEventListener('click', (event) => {
  const selected = event.target.closest('button[data-stage]');
  if (!selected) return;
  const stage = stages[Number(selected.dataset.stage)];
  stageControls.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button === selected)));
  document.querySelector('#artifact-name').textContent = stage.file;
  document.querySelector('#artifact-content').textContent = stage.content;
  document.querySelector('#stage-title').textContent = stage.title;
  document.querySelector('#stage-description').textContent = stage.description;
});

const branchMap = document.querySelector('.branch-map');
const trace = branchMap.querySelector('.trace');
const pulse = branchMap.querySelector('.task-pulse');
const motionToggle = document.querySelector('#motion-toggle');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const pathLength = trace.getTotalLength();
let elapsed = 0;
let lastFrame = null;
let frameId = null;
let paused = false;
function drawProgress(time) {
  if (lastFrame !== null) elapsed += Math.min(time - lastFrame, 100);
  lastFrame = time;
  // Travel for five seconds, then hold the result for one second.
  const progress = Math.min((elapsed % 6000) / 5000, 1);
  const point = trace.getPointAtLength(pathLength * progress);
  pulse.setAttribute('cx', point.x);
  pulse.setAttribute('cy', point.y);
  trace.style.strokeDashoffset = String(1 - progress);
  frameId = requestAnimationFrame(drawProgress);
}
function syncMotion() {
  cancelAnimationFrame(frameId);
  lastFrame = null;
  motionToggle.hidden = reducedMotion.matches;
  if (reducedMotion.matches) {
    branchMap.dataset.motion = 'static';
    trace.style.strokeDashoffset = '0';
  } else {
    branchMap.dataset.motion = paused ? 'paused' : 'running';
    motionToggle.textContent = paused ? 'Play animation' : 'Pause animation';
    if (!paused && !document.hidden) frameId = requestAnimationFrame(drawProgress);
  }
}
motionToggle.addEventListener('click', () => { paused = !paused; syncMotion(); });
reducedMotion.addEventListener('change', syncMotion);
document.addEventListener('visibilitychange', syncMotion);
syncMotion();
