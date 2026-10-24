// Runs Python inside backend/.venv, creating the venv and installing requirements on first use.
// Usage: node scripts/py.mjs -m uvicorn app.main:app --reload
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync, watch, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const backend = join(dirname(fileURLToPath(import.meta.url)), "..", "backend");
const win = process.platform === "win32";
const venvPython = join(backend, ".venv", win ? "Scripts/python.exe" : "bin/python");
const reqs = join(backend, "requirements.txt");
const stamp = join(backend, ".venv", ".requirements-installed");

function run(cmd, args) {
  const r = spawnSync(cmd, args, { cwd: backend, stdio: "inherit" });
  if (r.error) throw r.error;
  return r.status ?? 1;
}

if (!existsSync(venvPython)) {
  const candidates = win ? [["py", ["-3"]], ["python", []]] : [["python3", []], ["python", []]];
  let made = false;
  for (const [cmd, pre] of candidates) {
    try {
      if (run(cmd, [...pre, "-m", "venv", ".venv"]) === 0) { made = true; break; }
    } catch { /* try next */ }
  }
  if (!made) {
    console.error("Could not create a Python virtualenv. Install Python 3.11+ and try again.");
    process.exit(1);
  }
}

const wanted = readFileSync(reqs, "utf8");
if (!existsSync(stamp) || readFileSync(stamp, "utf8") !== wanted) {
  console.log("Installing backend requirements...");
  if (run(venvPython, ["-m", "pip", "install", "--quiet", "-r", "requirements.txt"]) !== 0) process.exit(1);
  writeFileSync(stamp, wanted);
}

// `--watch <dir>` restarts Python when a .py file under backend/<dir> changes. We do this instead of
// `uvicorn --reload` because on Windows its reloader stops the worker with a console Ctrl+C, which
// also stops `npm run dev` (and hangs if Python has no console of its own).
const args = process.argv.slice(2);
const watchAt = args.indexOf("--watch");
const watchDir = watchAt >= 0 ? args.splice(watchAt, 2)[1] : null;

let child = null;
let restarting = false;

function start() {
  child = spawn(venvPython, args, { cwd: backend, stdio: "inherit", env: { ...process.env, PYTHONUNBUFFERED: "1" } });
  child.on("exit", (code) => {
    if (restarting) {
      restarting = false;
      start();
    } else if (!watchDir) {
      process.exit(code ?? 1);
    } else {
      console.log("[py] Server stopped. Fix the error and save a file to restart.");
    }
  });
}

function kill(proc) {
  if (!proc || proc.exitCode !== null) return false;
  if (win) spawnSync("taskkill", ["/pid", String(proc.pid), "/T", "/F"], { stdio: "ignore" });
  else proc.kill("SIGTERM");
  return true;
}

start();

if (watchDir) {
  let timer = 0;
  watch(join(backend, watchDir), { recursive: true }, (_event, file) => {
    if (!file || !String(file).endsWith(".py")) return;
    clearTimeout(timer);
    timer = setTimeout(() => {
      console.log(`[py] ${file} changed, restarting...`);
      restarting = kill(child);
      if (!restarting) start(); // it had crashed; start fresh
    }, 200);
  });
}

const stop = () => {
  restarting = false;
  kill(child);
  process.exit(0);
};
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
