import os, re, subprocess

ROOT = r"C:\Users\Munachi\ai-trading-system"
SKIP = {".next", "node_modules", ".git", "__pycache__", ".venv", "venv"}

ENV_NAME_RE = re.compile(r"^\.?env(?:\..*)?$|^\.env\.example$|^\.env\.local$", re.I)
SECRET_FILE_RE = re.compile(r"(credential|service_account|\.pem$|id_rsa|secret_key|api_key\.json)", re.I)


def repos_under(root):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP and not d.endswith("site-packages") and "local-packages" not in d]
        if ".git" in dirnames:
            found.append(dirpath)
            dirnames.remove(".git")  # don't descend into the repo's own .git internals
    return found


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


print("=== 1) git repos found under the tree (excluding build/deps) ===")
repos = repos_under(ROOT)
if not repos:
    print("   -> NO .git directories found under the project itself")
else:
    for r in repos:
        print("   - {0}".format(r[len(ROOT) + 1:]))
print()

print("=== 2) for each repo: what git remotes are configured (URLs only, not keys) ===")
for r in repos:
    out = git(r, "remote", "-v")
    name = r[len(ROOT) + 1:]
    if out.returncode == 0 and out.stdout.strip():
        print("   [{0}]".format(name or "<project root>"))
        for line in out.stdout.splitlines():
            # show fetch/push URL host without leaking path segments that could be secrets
            m = re.match(r"^(\S+)\s+(.*?)\s+\((.*)\)$", line)
            if m:
                remote_name, url, verb = m.group(1), m.group(2), m.group(3)
                if url.startswith("http") and "@" in url.split("//", 1)[1]:
                    print("      {0:7} {1} (basic-auth host; credentials NOT shown)".format(remote_name, verb))
                else:
                    print("      {0:7} {1} ({2})".format(remote_name, url, verb))
            else:
                print("      {0}".format(line))
    else:
        print("   [{0}] no remotes configured".format(name or "<project root>"))
print()

print("=== 3) for each repo: is ANY env/secret file present in git COMMIT HISTORY (current OR past)? ===")
print("    (this is the Cloudflare-scary one: history never forgets)")
any_history = False
for r in repos:
    name = r[len(ROOT) + 1:]
    out = git(r, "log", "--all", "--name-only", "--pretty=format:@@COMMIT %H")
    found = []
    if out.returncode == 0:
        # every file path ever touched, dedup preserving order
        seen = set()
        for line in out.stdout.splitlines():
            p = line.strip()
            if not p or p.startswith("@@"):
                continue
            base = os.path.basename(p)
            hits = ENV_NAME_RE.search(base) or SECRET_FILE_RE.search(p)
            if hits and p not in seen:
                seen.add(p)
                found.append(p)
    if found:
        any_history = True
        print("   !! [{0}] SECRET/ENV FILE(S) IN HISTORY ({1} unique path):".format(name or "<root>", len(found)))
        for p in found[:15]:
            print("         - {0}".format(p))
        if len(found) > 15:
            print("         ... and {0} more".format(len(found) - 15))
    else:
        print("   OK  [{0}] no env/secret file in history".format(name or "<root>"))
print()

print("=== 4) authoritative: is .env ignored by git in the root repo (current status)? ===")
root_repo = None
for r in repos:
    if (r + os.sep + ".git").rstrip(os.sep + ".") == r or os.path.abspath(r) == ROOT or os.path.normcase(r) == os.path.normcase(ROOT):
        root_repo = r
        break
if root_repo:
    check = git(root_repo, "check-ignore", os.path.join(ROOT, ".env"))
    print("   git check-ignore .env -> {0}".format("IGNORED (good)" if check.returncode == 0 else "NOT IGNORED (!!)"))
    ls = git(root_repo, "ls-files")
    tracked_env = [l for l in ls.stdout.splitlines() if ENV_NAME_RE.search(os.path.basename(l))]
    print("   git ls-files (tracked) .env* -> {0}".format(tracked_env if tracked_env else "none tracked (good)"))
else:
    print("   (root itself is not a git repo)")
print()
print("=== 5) do the CLOUDFLARE-PUSHED .next bundle(s) contain any live secret marker (path-only, not values)? ===")
nextdir = os.path.join(ROOT, "frontend", ".next")
markers_found = []
if os.path.isdir(nextdir):
    pats = ("NEXT_PUBLIC_", "SUPABASE_URL", "sb_publishable", "sb_secret", "sb_ publishable")
    for dirpath, dirnames, filenames in os.walk(nextdir):
        for fn in filenames:
            if not fn.endswith((".js", ".mjs", ".json", ".map")):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                    data = fh.read(2000000)
            except Exception:
                continue
            for pat in pats:
                if pat in data:
                    markers_found.append((fp[len(ROOT) + 1:], pat))
                    break
if markers_found:
    print("   !! {0} bundle(s) contain supabase/env marker strings:".format(len(markers_found)))
    for fp, pat in markers_found[:10]:
        print("      - {0}  [marker: {1}]".format(fp, pat))
else:
    print("   CLEAN - no supabase/env marker strings found in .next bundles")
