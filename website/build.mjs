import { mkdir, copyFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
const root = path.dirname(fileURLToPath(import.meta.url));
await mkdir(path.join(root, "dist"), { recursive: true });
for (const file of ["index.html", "style.css", "app.js", "mark.svg"]) {
  await copyFile(path.join(root, file), path.join(root, "dist", file));
}
console.log("Built static website in dist/");
