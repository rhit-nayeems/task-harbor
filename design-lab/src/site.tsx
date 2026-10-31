import { useState } from 'react';
import { GITHUB, ISSUES, PYPI, LICENSE, InstallCommand, copyText } from './components/harbor/shared';

export function SiteHeader(){
 return <header className="site-header site-shell"><nav aria-label="Main navigation">
  <a href="#team">The team</a><a href="#workflow">Workflow</a>
  <a className="site-brand nav-brand" href="#top" aria-label="Task Harbor home">TASK/HARBOR</a>
  <a href={GITHUB+'/blob/main/README.md'}>Docs</a><a href="#install" className="nav-install">Get started</a>
 </nav></header>;
}

const ROLES = [
 ['Planning', 'Turn backlog tasks into implementation plans.'],
 ['Implementation', 'Work through each task in its own Git worktree, one task at a time.'],
 ['Quality assurance', 'Run configured checks, then model QA against the task.'],
 ['Code review', 'Review accumulated changes and address findings.'],
];
export function EngineeringTeam(){
 return <section className="site-team site-shell team-compact" id="team" aria-labelledby="team-title">
  <div className="team-intro"><h2 id="team-title">Your engineering team</h2><p>Four agent roles, powered by Claude Code or Codex.</p></div>
  <dl className="team-roster">{ROLES.map(([title,body])=><div key={title}><dt>{title}</dt><dd>{body}</dd></div>)}</dl>
 </section>;
}

export function ReviewSection(){return <section className="review-section"><div className="site-shell review-layout"><div><h2>Review before you merge</h2><p>Changes collect on a local integration branch. Inspect the diff, test the behavior, and accept the work when you’re ready.</p><a href={GITHUB+'/blob/main/docs/VERIFICATION.md'} className="text-link">Read the verification guide ↗</a></div><dl className="review-facts"><div><dt>Isolated work</dt><dd>Each task gets a separate Git worktree.</dd></div><div><dt>Visible checks</dt><dd>Your configured commands run before model QA.</dd></div><div><dt>Saved state</dt><dd>Pause the run and resume from its saved state.</dd></div><div><dt>Human review</dt><dd>No automatic push or merge into your original branch.</dd></div></dl></div></section>;}

function Command({text}:{text:string}){const [state,setState]=useState('Copy');return <div className="setup-command"><code>{text}</code><button onClick={async()=>{setState(await copyText(text)?'Copied':'Select to copy');}} aria-label={'Copy '+text}><span role="status">{state}</span></button></div>;}
export function GettingStarted(){return <section className="setup-section site-shell" id="install" aria-labelledby="setup-title">
 <div className="site-section-intro"><h2 id="setup-title">Try it on a small task</h2><p>Start with the demo. For your own Python maintenance backlog, use a repository with tests and a committed starting point.</p></div>
 <ol className="setup-steps">
  <li><span className="step-count">01</span><div><h3>Install and try the demo</h3><InstallCommand tone="mono"/><Command text="task-harbor demo"/><p>Requires Python 3.11+ and Git. The demo applies a scripted fix, runs real tests, and creates a review report. No provider account or model calls. Available on <a className="text-link" href={PYPI}>PyPI</a>.</p></div></li>
  <li><span className="step-count">02</span><div><h3>Set up your first real task</h3><Command text="task-harbor setup"/><p>Run inside your project. The wizard collects your provider, model, check commands, call limit, first task, and acceptance criteria. New setups require checks and default to 20 calls per run. Real tasks need Claude Code or Codex installed and signed in.</p><p>Add another task with <code>task-harbor add-task</code>, or use the dashboard’s <strong>Set up</strong> form.</p><a href={GITHUB+'/blob/main/docs/CONFIGURATION.md'} className="text-link">Configuration reference ↗</a></div></li>
  <li><span className="step-count">03</span><div><h3>Check, run, and review</h3><p>Commit project changes, then check your setup and run the baseline tests:</p><Command text="task-harbor check"/><Command text="task-harbor preflight --run-checks"/><Command text="task-harbor"/><p>In the dashboard, choose <strong>New run</strong> to review settings and start agent work. Review the recorded checks and diff before accepting changes. Provider usage begins when you launch a run.</p></div></li>
 </ol><div className="setup-help"><p>Command not found? Use <code>python -m task_harbor</code> with the same arguments.</p><a className="text-link" href={GITHUB+'#quick-start'}>Full quick start ↗</a></div>
 </section>;}

const QUESTIONS=[
 ['What does it cost?', 'Task Harbor is open source under the MIT license. Agent work consumes usage through your provider account. Dashboard viewing and local readiness checks do not make model calls.'],
 ['Does it push or merge my code?', 'Passing work lands on a local integration branch. Task Harbor does not automatically push it or merge it into your original branch. You review and decide.'],
 ['What happens when a check fails?', 'A failed required check prevents approval. Task Harbor can attempt repairs within configured limits. Blocked tasks and verification results remain visible in the run evidence.'],
 ['Can I stop a run?', 'Yes. Stop requests a pause after current agent calls finish. Run state is saved for resume. Closing the dashboard alone does not stop a launched run.']
];
export function SiteClosing(){return <><section className="faq-section site-shell" aria-labelledby="faq-title"><h2 id="faq-title">Common questions</h2><div className="faq-list">{QUESTIONS.map(([q,a])=><details key={q}><summary>{q}<span aria-hidden="true">+</span></summary><p>{a}</p></details>)}</div></section><section className="contribution-section site-shell" id="contribute"><div><h2>Contribute to Task Harbor</h2><p>Task Harbor is open source. Report bugs or contribute to the CLI, checks, and documentation.</p></div><nav aria-label="Contribute"><a href={GITHUB} className="text-link">Source ↗</a><a href={ISSUES} className="text-link">Report an issue ↗</a><a href={GITHUB+'/blob/main/CONTRIBUTING.md'} className="text-link">Contribute ↗</a></nav></section><footer className="site-footer site-shell"><a className="site-brand" href="#top">TASK/HARBOR</a><nav aria-label="Footer"><a href={PYPI}>PyPI ↗</a><a href={LICENSE}>MIT license</a></nav></footer></>;}
