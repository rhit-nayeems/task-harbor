# Find the first five pilot teams

Research checked October 30, 2026. This is a recruitment plan, not a list of
customers. Nobody listed here has been contacted or agreed to participate.
Repository size, team size, agent usage, and buying authority must be qualified
in conversation; an open-source repository does not establish those facts.

## Who to recruit first

Start with developers you can reach through an existing relationship who
maintain Python software at work. Prefer a team with 2–10 engineers, existing
tests, a recurring maintenance backlog, and someone already using Claude Code
or Codex. This is a hypothesis to test, not a proven customer profile.

Ask about a recent task before offering the product. A team that cannot name
recurring supervision or review work may not need Harbor.

An open-source maintainer can teach us about review, but is not automatically a
potential paying customer. Keep those interviews separate from commercial pilots.

## Public projects worth investigating

These are research candidates. They are not invitations to advertise in issue
trackers, submit automated PRs, or contact every contributor.

| Candidate | Public evidence | Possible conversation | What remains unknown |
| --- | --- | --- | --- |
| Datasette and sqlite-utils plugin maintainers | Both projects document pytest-based development. Datasette has a documented plugin ecosystem and community. | How smaller plugins are maintained; which changes need repeated human checking. | Whether individual maintainers use agents, have recurring work, or want a pilot. Treat the shared ecosystem as one recruitment channel. |
| Rich / Textual ecosystem maintainers | Rich documents development and an AI contribution policy requiring disclosure and an approved solution. | How maintainers establish confidence in CLI changes and terminal behavior. | Willingness to participate, commercial buying authority, and which changes can be tested adequately. |
| Meilisearch Python SDK maintainers | The contribution guide permits AI assistance with disclosure, scope explanation, and human review. | SDK maintenance, regressions, and time spent verifying changes. | Environment complexity, team size, agent usage, and procurement. Qualify the test environment before offering a first run. |
| MCP Python SDK maintainers | The contribution guide explicitly describes limited review capacity and increased agent-generated PR volume. | What evidence actually reduces review work, and what evidence merely adds noise. | Whether Harbor helps their internal workflow. Treat this as a later research interview, not an invitation to generate contributions. |

Sources:

- [Datasette contribution and test instructions](https://docs.datasette.io/en/latest/contributing.html)
- [Datasette community link](https://docs.datasette.io/en/latest/)
- [sqlite-utils contribution and test instructions](https://sqlite-utils.datasette.io/en/stable/contributing.html)
- [Rich contribution guide](https://github.com/Textualize/rich/blob/main/CONTRIBUTING.md)
- [Rich AI policy](https://github.com/Textualize/rich/blob/main/AI_POLICY.md)
- [Meilisearch Python contribution guide](https://github.com/meilisearch/meilisearch-python/blob/main/CONTRIBUTING.md)
- [MCP Python SDK contribution guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/CONTRIBUTING.md)

My inference from these sources: review effort is worth investigating. They do
not demonstrate that these teams need Harbor or that Harbor reduces that effort.

## Channels and exclusions

- Warm introductions: start here. Ask people you already know whether they
  maintain a suitable repository; do not assume an introduction exists.
- Datasette community: the official docs link to Discord. Read current channel
  rules and ask whether a research invitation is appropriate before posting.
- Show HN: a runnable CLI and provider-free demo are more suitable than a signup
  page. The founder must write the submission and replies personally; HN bars
  generated text. Do not frame a minor version announcement as a new launch or
  solicit votes. Check whether the project has already been submitted.
- Python Discord: unapproved advertising is prohibited. This is not an open
  recruitment channel. Obtain the community's approval before any promotion.
- Pallets / Click: exclude from initial agent pilots. Its AI policy discourages
  AI-generated contributions and applies across community interactions.

Sources: [Show HN](https://news.ycombinator.com/showhn.html),
[HN guidelines](https://news.ycombinator.com/newsguidelines.html),
[Python Discord rules](https://www.pythondiscord.com/pages/rules/),
[Pallets AI policy](https://palletsprojects.com/contributing/llm-ai).

## Invitation draft for a personal conversation

Edit this for someone you actually know or a channel that permits invitations.
It is not copy for HN, Pallets, or any community that prohibits generated text.

> I'm building Task Harbor, an open-source CLI that runs a coding backlog with
> Claude Code or Codex and collects checks and diffs for review. I'm trying to
> understand where developers still spend time supervising agents and checking
> their changes. Would you be open to a 20-minute conversation about a recent
> maintenance task? No installation needed. If there's a fit, we could try one
> small task together later.

Share the demo only after interest:

```sh
python -m pip install --upgrade task-harbor
task-harbor demo
```

Explain that the demo uses a scripted fix and local tests. It does not demonstrate
agent quality. The CLI is MIT-licensed; real agent tasks use the participant's
provider account. Do not promise lower cost, time savings, or correctness.

## Qualify before scheduling a pilot

Ask these questions, record the answers privately, and include negative responses:

1. What repository do you maintain, and can you authorize local agent work on it?
2. Which coding agent did you use on your last task?
3. What work did you personally do before, during, and after its execution?
4. Which checks already run locally? Can one bounded change be reviewed in one session?
5. What task would you otherwise handle this week? What would make Harbor worth keeping?
6. Who decides whether to pay for developer tools, and what relevant tools does the team buy now?

Do not ask for credentials or private source uploads. Run locally with the
participant controlling their account. For now, keep all internal preparation
provider-free; schedule live task work only after the participant agrees.

## Four-week sequence

1. Interview about ten developers. Record recent behavior, not hypothetical
   enthusiasm. If no recurring problem emerges, revise the customer hypothesis.
2. Invite up to five qualified teams to one observed first task each. Use the
   existing pilot worksheets to record setup, assistance, and human effort.
3. Observe whether they return without reminders. Record task rejection and
   abandonment as well as successful work. Keep live comparisons deferred until
   a provider, budget, and task set have been explicitly agreed.
4. Ask returning teams what they would pay for and why. The current CLI is free;
   distinguish requests for paid support or future team features from an actual
   purchase. Do not record revenue until a payment has occurred.

These counts are learning targets, not YC requirements. Review evidence before
expanding features or making performance claims. See [the pilot protocol](PILOT.md)
and [blank interview worksheet](../evaluations/pilot-templates/interviews.md).
