import { cp, mkdir, readdir, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import path from 'node:path';

const root = path.dirname(fileURLToPath(import.meta.url));
const source = path.resolve(root, '../design-lab');
const require = createRequire(path.join(source, 'package.json'));
for (const [pkg, script, args] of [
  ['typescript', 'bin/tsc', ['--noEmit']],
  ['vite', 'bin/vite.js', ['build']],
]) {
  const entry = path.join(path.dirname(require.resolve(`${pkg}/package.json`)), script);
  execFileSync(process.execPath, [entry, ...args], { cwd: source, stdio: 'inherit' });
}
const output = path.join(root, 'dist');
// Only remove the fixed build output within this website directory.
if (path.dirname(output) !== root || path.basename(output) !== 'dist') throw new Error('Invalid build output');
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await cp(path.join(source, 'dist'), output, { recursive: true });
const files = await readdir(output);
if (!files.includes('index.html') || !files.includes('assets')) throw new Error('Incomplete website build');
console.log('Built website/dist from design-lab source');
