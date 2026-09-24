import re
import os
import sys
from pathlib import Path

SRC = Path(r"C:\Users\Munachi\Documents\crash logs.txt")
DOTENV = Path(r"C:\Users\Munachi\ai-trading-system\.env")

def mask(v: str) -> str:
    if not v:
        return "<EMPTY>"
    if len(v) <= 14:
        return v
    return v[:14] + "..." + " [" + str(len(v)) + "]"

# 1) parse the source txt (format: "<VALUE> = <LABEL>" per line)
url = None
pub = None
sec = None
for line in SRC.read_text(encoding="utf-8", errors="replace").splitlines():
    s = line.strip()
    if not s:
        continue
    if "=" in s:
        val, label = [p.strip() for p in s.split("=", 1)]
    else:
        val, label = s, ""
    low = (val + " " + label).lower()
    if val.startswith("https://") and "supabase" in low and url is None:
        url = val
    elif re.fullmatch(r"sb_publishable_[A-Za-z0-9_]+", val) and pub is None:
        pub = val
    elif re.fullmatch(r"sb_secret_[A-Za-z0-9_]+", val) and sec is None:
        sec = val

print("parsed from source:")
print("  URL :", mask(url))
print("  PUB :", mask(pub))
print("  SEC :", mask(sec))
missing = [n for n, v in (("URL", url), ("PUB", pub), ("SEC", sec)) if not v]
if missing:
    print("ERROR missing:", missing)
    sys.exit(1)

# 2) load existing .env lines
orig = DOTENV.read_text(encoding="utf-8", errors="replace").splitlines()
wrote = {"SUPABASE_URL": False, "SUPABASE_PUBLISHABLE_KEY": False, "SUPABASE_SECRET_KEY": False}
out = []
for line in orig:
    m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
    if m:
        name = m.group(1)
        if name in wrote and not wrote[name]:
            if name == "SUPABASE_URL":
                out.append("SUPABASE_URL=" + url)
            else:
                out.append(name + "=" + pub if name == "SUPABASE_PUBLISHABLE_KEY" else name + "=" + sec)
            wrote[name] = True
            continue
    out.append(line)

# append any not already present
for name, val in (("SUPABASE_URL", url),
                  ("SUPABASE_PUBLISHABLE_KEY", pub),
                  ("SUPABASE_SECRET_KEY", sec)):
    if not wrote[name]:
        out.append(name + "=" + val)
        wrote[name] = True

DOTENV.write_text("\n".join(out) + "\n", encoding="utf-8")
print("updated .env | wrote:", {k: wrote[k] for k in wrote})
