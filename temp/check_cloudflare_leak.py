import subprocess, os, re, io, sys

ROOT = r"C:\Users\Munachi\ai-trading-system"
PAT_RE = re.compile(r"(^|[\\/])\.?(env|env\.example|env\.local|env\.dev|flaskenv|venv|f).*$", re.I)
ENVNAME_RE = re.compile(r"(^|[\\/])\.env($|\.)", re.I)
SECRET_RE = re.compile(r"(\.pem$|^id_rsa$|service_account|rsa_private|\.key$|credentials\.json$|secret_file)", re.I)


def git(repo, *args, cwd=None):
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True, text=True, cwd=cwd,
    )


def repos_under(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        if any(x in dirpath for x in ("node_modules", "\\.git", "\\node_modules", "\\__pycache__", "\\.next")):
            if "\\node_modules" in dirpath or "\\.next" in dirpath or "\\__pycache__" in dirpath:
                dirnames[:] = []
                continue
        if ".git" in dirnames:
            out.append(dirpath)
            dirnames.remove(".git")
    return out


def env_like(name):
    return bool(ENVNAME_RE.search(name) or SECRET_RE.search(name))


print("=== 1) git repos inside the project (excluding node_modules/.next/venv) ===")
repos = repos_under(ROOT)
if not repos:
    print("   (none found via walk) -> fall back: explicit frontend/backend check below")
for r in repos:
    print("   repo: {}".format(r[len(ROOT) + 1:]))

print()
print("=== 2) for EVERY repo: any .env or secret file EVER in git history? (the Cloudflare risk) ===")
any_history = False
for r in repos:
    name = r[len(ROOT) + 1:] or "<root>"
    # all commits, all files ever referenced
    rr = git(r, "log", "--all", "--name-only", "--pretty=format:@@COMMIT %H", cwd=r)
    blob_hit = None
    if rr.returncode == 0 and rr.stdout:
        for rawline in rr.stdout.splitlines():
            line = rawline.strip()
            if line.startswith("@@COMMIT"):
                continue
            if env_like(line):
                blob_hit = line
                any_history = True
                break
    if blob_hit:
        print("   !! repo '{0}': {1} was referenced in git history -> REAL exposure" .format(name, blob_hit))
    else:
        print("   OK  repo '{0}': no .env / secret path ever tracked in history".format(name))

print()
print("=== 3) even if not git: is any env value BAKED into the built frontend (.next) bundles? ===")
# NEXT_PUBLIC_* gets inlined at build time by Next.js into client JS. Check only NON-secret
# usage pattern presence; never print values.
baked = []
for dirpath, _, files in os.walk(os.path.join(ROOT, "frontend", ".next")):
    for f in files:
        if f.endswith((".js", ".map")):
            p = os.path.join(dirpath, f)
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except Exception:
                continue
            for pat in ("NEXT_PUBLIC_", "SUPABASE_", "sb_publishable", "sb_secret"):
                if pat in content:
                    baked.append((p[len(ROOT) + 1:], pat))
if baked:
    print("   !! found {} marker(s) inside .next bundles (paths only, values NOT dumped):".format(len(baked)))
    for p, pat in baked[:12]:
        print("      - {0}  (marker: {1})".format(p, pat))
else:
    print("   CLEAN: no SUPABASE_/sb_/NEXT_PUBLIC marker baked into .next bundles")
