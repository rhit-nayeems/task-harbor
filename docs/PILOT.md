# Run a small pilot

Start with a few teams maintaining Python repositories with established tests.
This is an initial customer hypothesis, not a claim that Task Harbor works best
for these teams. Watch where users struggle and revise it.

## Pilot materials

Use the [recruitment plan](PILOT_RECRUITMENT.md) to find and qualify participants.
It includes sourced research candidates, channel restrictions, and an invitation
draft. No outreach has been sent and no pilot results are claimed.

Copy the [worksheets](../evaluations/pilot-templates) into a private folder:

- `interviews.md`: prompts about recent work and an observed first session.
- `teams.csv`: onboarding, voluntary repeat usage, and actual payment responses.
- `attempts.csv`: equivalent records for direct-agent and Harbor attempts.

Start with five teams over four weeks as a learning target, not a qualification
for funding. Keep the customer hypothesis explicit: teams with 2–10 engineers,
Python repositories, established tests, and recurring maintenance work.
Revise this hypothesis if observed behavior points elsewhere.

Use anonymous IDs. Leave unmeasured fields blank rather than entering zero.
Use `direct` or `harbor` for arm and `accepted`, `needs_changes`, `rejected`, or
`abandoned` for human_outcome. Record every attempt, including failed ones.
No customer results have been collected in these templates.

## First session

Ask a developer to show their last maintenance task and how they used their
coding agent. Record where they spent time: writing requirements, guiding the
agent, recovering failures, reviewing changes, and fixing mistakes.

Have them try `task-harbor demo`, then `task-harbor setup` in their own repository.
Observe whether they can configure checks, finish a small task, and review its
evidence without assistance. Record assistance and setup time separately.

## Compare real work

Use the [comparison runner](../EVALUATION.md) with the same starting commit,
task, provider, model, effort, and environment in each arm. Both live arms use
provider usage. Use repeated trials and independent grading; the three smoke
fixtures do not establish product value. Avoid having the same reviewer solve
the same task in both arms where prior knowledge would distort the comparison.

For each attempt, record:

- Whether a human accepted the change, requested changes, rejected it, or abandoned it.
- Active preparation/supervision, review, and repair minutes, without overlap.
- Agent elapsed time and reported provider usage; retain unknown usage as unknown.
- Regressions found during review and later use.

Record a Harbor review against its exact checkpoint:

```sh
task-harbor feedback --run-id RUN_ID --task TASK_ID --outcome accepted --minutes 4 --supervision-minutes 3 --repair-minutes 0
```

`--minutes` is review time. Omitted supervision or repair values mean unknown,
not zero. Supply explicit zero when no time was spent. Feedback entries append;
do not log the same time twice. Task completion and model PASS are not human
acceptance. Keep equivalent records for direct-agent attempts.

Measure human minutes per accepted task, including time spent on unsuccessful
attempts. Report acceptance and regressions alongside this number so rejecting
hard tasks cannot make the result look better. Show raw counts, sample size,
and usage as well; do not claim savings from a few favorable examples.

## Follow up

After several weeks, check whether teams started more work without reminders,
which tasks they stopped using Harbor for, and whether they will pay to continue.
Keep interview and payment records outside public run reports. Share repository
content or customer evidence only with the team's permission. Task Harbor does
not collect or transmit pilot analytics automatically.
