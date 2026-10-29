import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { MOTION_SPEED, useMotion } from './components/harbor/motion';
import { WTASKS } from './components/harbor/workflow';
import './kanban.css';

type Position = 0 | 1 | 2 | 3;
type Snapshot = { positions: Position[]; caption: string; held?: boolean };
const COLUMNS = ['Backlog', 'In progress', 'Checks', 'Ready for review'];
const TITLES = ['Retry fetch', 'Read TOML', 'Round dates', 'Document retries'];
// Snapshots preserve sequential implementation and the T-101 → T-104 dependency.
const RUN: Snapshot[] = [
 {positions:[0,0,0,0],caption:'Four tasks from BACKLOG.md. Document retries waits for Retry fetch.'},
 {positions:[1,0,0,0],caption:'T-101 runs in its own Git worktree. The other tasks wait.'},
 {positions:[2,0,0,0],caption:'T-101 runs configured checks, followed by model QA.'},
 {positions:[3,1,0,0],caption:'T-101 passes checks and QA. T-102 starts next.'},
 {positions:[3,2,0,0],caption:'T-102 is checked against its acceptance criteria.'},
 {positions:[3,3,1,0],caption:'T-102 passes. T-103 starts in a separate worktree.'},
 {positions:[3,3,2,0],caption:'T-103 fails test_dst and is held for repair. Model QA does not run.',held:true},
 {positions:[3,3,2,1],caption:'T-104 can start because T-101 passed. T-103 remains held.',held:true},
 {positions:[3,3,2,2],caption:'T-104 runs its documentation check, followed by model QA.',held:true},
 {positions:[3,3,2,3],caption:'Three tasks are ready for your review. The failed task stays out of integration.',held:true},
];
const TESTS = ['test_retry_limit', 'test_toml_config', 'test_dst', 'docs check'];

export function KanbanWorkflow(){
 const [step,setStep]=useState(0),[playing,setPlaying]=useState(true),[selected,setSelected]=useState(0),[visible,setVisible]=useState(false);
 const {reduced,paused}=useMotion();
 const root=useRef<HTMLElement>(null),cards=useRef<HTMLDivElement>(null),previous=useRef(new Map<string,{left:number;top:number}>());
 const snapshot=RUN[step],task=WTASKS[selected],position=snapshot.positions[selected],failed=selected===2&&!!snapshot.held;
 useEffect(()=>{const io=new IntersectionObserver(([e])=>setVisible(e.isIntersecting),{threshold:.2});if(root.current)io.observe(root.current);return()=>io.disconnect();},[]);
 useEffect(()=>{
  if(!playing||reduced||paused||!visible)return;
  let timer:number|undefined;
  const start=()=>{window.clearInterval(timer);if(!document.hidden)timer=window.setInterval(()=>setStep(s=>Math.min(s+1,RUN.length-1)),4000/MOTION_SPEED);};
  start();document.addEventListener('visibilitychange',start);
  return()=>{window.clearInterval(timer);document.removeEventListener('visibilitychange',start);};
 },[playing,reduced,paused,visible]);
 useEffect(()=>{if(step===RUN.length-1)setPlaying(false);},[step]);
 useEffect(()=>{const reset=()=>previous.current.clear();window.addEventListener('resize',reset);return()=>window.removeEventListener('resize',reset);},[]);
 useLayoutEffect(()=>{
  const animations:Animation[]=[];
  cards.current?.querySelectorAll<HTMLElement>('[data-task]').forEach(card=>{
   const rect=card.getBoundingClientRect(),parent=cards.current!.getBoundingClientRect(),left=rect.left-parent.left,top=rect.top-parent.top,old=previous.current.get(card.dataset.task!);
   if(old&&!reduced&&!paused&&!document.hidden){const x=old.left-left,y=old.top-top;if(x||y)animations.push(card.animate([{transform:`translate(${x}px,${y}px)`},{transform:'translate(0,0)'}],{duration:500/MOTION_SPEED,easing:'cubic-bezier(.2,.7,.2,1)'}));}
   previous.current.set(card.dataset.task!,{left,top});
  });
  return()=>animations.forEach(a=>a.cancel());
 },[step,reduced,paused]);
 const go=(next:number)=>{setPlaying(false);setStep(next);};
 const label=(i:number)=>snapshot.held&&i===2?'Failed: test_dst':snapshot.positions[i]===0?(i===3&&step<3?'Waits for T-101':'Queued'):snapshot.positions[i]===1?'Separate Git worktree':snapshot.positions[i]===2?'Checks, then model QA':'Checks + QA passed';
 return <section className="workflow-lab kanban-workflow" id="workflow" ref={root} aria-labelledby="workflow-title">
  <div className="wf-heading"><h2 id="workflow-title">How a run works</h2></div>
  <div className="kanban-toolbar"><span>Example run</span><div><button onClick={()=>go(step-1)} disabled={step===0} aria-label="Previous step">Previous</button><span>{step+1} / {RUN.length}</span><button onClick={()=>go(step+1)} disabled={step===RUN.length-1} aria-label="Next step">Next</button><button disabled={reduced} onClick={()=>{if(step===RUN.length-1)setStep(0);setPlaying(!playing);}}>{reduced?'Manual playback':playing?'Pause':step===RUN.length-1?'Replay':'Play'}</button></div></div>
  <p className="kanban-caption" aria-live="polite">{snapshot.caption}</p>
  <div className="kanban-board" aria-label="Example task board">
   <div className="kanban-columns">{COLUMNS.map((name,column)=><h3 key={name}>{name}<span aria-label="tasks">{snapshot.positions.filter(p=>p===column).length}</span></h3>)}</div>
   <div className="kanban-cards" ref={cards}>{WTASKS.map((t,i)=>{
    const col=snapshot.positions[i],rank=snapshot.positions.slice(0,i).filter(p=>p===col).length;
    return <button key={t.id} data-task={t.id} style={{gridColumn:col+1,gridRow:rank+1}} className={`kanban-card ${selected===i?'selected':''} ${snapshot.held&&i===2?'failed':''}`} aria-pressed={selected===i} aria-label={`${t.id}: ${TITLES[i]}, ${COLUMNS[col]}, ${label(i)}`} onClick={()=>{setSelected(i);setPlaying(false);}}><span className="kanban-id">{t.id}</span><strong>{TITLES[i]}</strong><span className="kanban-status">{label(i)}</span>{snapshot.held&&i===2&&<span className="kanban-failure">Held for repair · QA not run</span>}</button>;
   })}</div>
   <div className="kanban-mobile">{COLUMNS.map((name,col)=><section key={name} aria-label={name}><h3>{name}<span>{snapshot.positions.filter(p=>p===col).length}</span></h3>{WTASKS.map((t,i)=>snapshot.positions[i]===col&&<button key={t.id} className={`kanban-card ${selected===i?'selected':''} ${snapshot.held&&i===2?'failed':''}`} aria-pressed={selected===i} onClick={()=>{setSelected(i);setPlaying(false);}}><span className="kanban-id">{t.id}</span><strong>{TITLES[i]}</strong><span className="kanban-status">{label(i)}</span>{snapshot.held&&i===2&&<span className="kanban-failure">Held for repair · QA not run</span>}</button>)}</section>)}</div>
  </div>
  <div className="kanban-evidence" aria-live="polite"><div><span className="kanban-id">{task.id}</span><h3>{task.title}</h3><p>{position===0?'Waiting for implementation.':position===1?'Implementation in its own Git worktree.':failed?'Required check failed. This task cannot join integration.':position===2?'Configured checks must pass before model QA.':'Saved on the local integration branch for human review.'}</p></div><dl><div><dt>Configured check</dt><dd>{failed?`${TESTS[selected]} failed`:position===3?`${TESTS[selected]} passed`:position===2?'Pending result':'Not run'}</dd></div><div><dt>Model QA</dt><dd>{position===3?'Passed':'Not run'}</dd></div><div><dt>Your review</dt><dd>{position===3?'Pending':'Not ready'}</dd></div></dl></div>
  <p className="kanban-note">Illustrative tasks. Passing checks do not merge or push your code.</p>
 </section>;
}
