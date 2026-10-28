import { useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { MotionProvider, useMotion } from './components/harbor/motion';
import { HarborPage } from './components/harbor/page';
import { Combined } from './routes/combined';
import { WorkflowLab } from './workflows';
import './styles.css';
import './workflows.css';
import './site.css';
function App(){
 const {paused,setPaused,reduced}=useMotion();
 useEffect(()=>{if(window.location.hash){const id=requestAnimationFrame(()=>document.getElementById(window.location.hash.slice(1))?.scrollIntoView({behavior:'instant'}));return()=>cancelAnimationFrame(id);}},[]);
 const variant=window.location.pathname==='/'?'constellation':window.location.pathname.slice(1);
 return <><a className="lab-skip" href="#workflow">Skip to workflow</a>{variant==='combined'?<Combined/>:<HarborPage><WorkflowLab variant={variant}/></HarborPage>}{new URLSearchParams(window.location.search).has('concepts')&&<div className="lab-dock"><span>DESIGN LAB</span><a href="/git-map#workflow">Git map</a><a href="/terminal#workflow">Terminal</a><a href="/constellation#workflow">Constellation</a><button disabled={reduced} onClick={()=>setPaused(!paused)}>{reduced?'Reduced motion':paused?'Play motion':'Pause motion'}</button></div>}</>;
}
const appRoot = import.meta.hot?.data.root ?? createRoot(document.getElementById('root')!);
if(import.meta.hot) import.meta.hot.data.root = appRoot;
appRoot.render(<MotionProvider><App/></MotionProvider>);
