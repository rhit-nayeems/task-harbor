import type { AnchorHTMLAttributes, ComponentType } from 'react';
export function useLocation(){return {pathname:window.location.pathname};}
export function Link({to,hash,...props}:AnchorHTMLAttributes<HTMLAnchorElement>&{to:string;hash?:string}){return <a href={to+(hash?'#'+hash:'')} {...props}/>;}
export function createFileRoute(_path:string){return (options:{head?:()=>unknown;component:ComponentType})=>options;}
