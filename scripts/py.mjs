// Runs Python inside backend/.venv, creating the venv and installing requirements on first use.
// Usage: node scripts/py.mjs -m uvicorn app.main:app --reload
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
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

// On Windows, uvicorn --reload signals Ctrl+C to its whole console group, which would also stop
// `npm run dev`. Run Python in its own (hidden) process group and relay its output instead.
const child = spawn(venvPython, process.argv.slice(2), {
  cwd: backend,
  stdio: win ? ["ignore", "pipe", "pipe"] : "inherit",
  detached: win,
  windowsHide: true,
  env: { ...process.env, PYTHONUNBUFFERED: "1" },
});
if (win) {
  child.stdout.pipe(process.stdout);
  child.stderr.pipe(process.stderr);
}
const stop = () => {
  if (win) spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
  else child.kill("SIGTERM");
};
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
child.on("exit", (code) => process.exit(code ?? 1));
