import re
import sys
from pathlib import Path

SRC = Path(r"C:\Users\Munachi\Documents\crash logs.txt")
ENV = Path(r"C:\Users\Munachi\ai-trading-system\.env")

def mask(v: str) -> str:
    if not v:
        return "<EMPTY>"
    if len(v) <= 16:
        return v
    return v[:14] + "...(" + str(len(v)) + ")"

url = pub = sec = None

raw = SRC.read_text(encoding="utf-8", errors="replace")
# format per line:  VALUE = LABEL  (label identifies which one)
for line in raw.splitlines():
    line = line.strip()
    if not line:
        continue
    m = re.match(r"^(\S+)\s*=\s*(Supabase (?:URL|publishable key|Secret))\s*$", line)
    if not m:
        print("skipped line: " + line[:40])
        continue
    val, label = m.group(1), m.group(2).lower()
    if "url" in label:
        url = val
    elif "publishable" in label:
        pub = val
    elif "secret" in label:
        sec = val

print("parsed from source txt:")
print("  URL :", mask(url))
print("  PUB :", mask(pub))
print("  SEC :", mask(sec))

missing = [n for n, v in (("URL", url), ("PUB", pub), ("SEC", sec)) if not v]
if missing:
    print("ERROR missing: " + ", ".join(missing))
    sys.exit(1)

keymap = {
    "SUPABASE_URL": url,
    "SUPABASE_PUBLISHABLE_KEY": pub,
    "SUPABASE_SECRET_KEY": sec,
}

text = ENV.read_text(encoding="utf-8", errors="replace")
had = {k: False for k in keymap}
new_lines = []
for line in text.splitlines():
    m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
    if m and m.group(1) in keymap:
        had[m.group(1)] = True
        new_lines.append(m.group(1) + "=" + keymap[m.group(1)])
        continue
    new_lines.append(line)

for k, v in keymap.items():
    if not had[k]:
        new_lines.append(k + "=" + v)

ENV.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

print("")
print("wrote to .env. superset now contains (masked):")
for k in keymap:
    m = re.search(r"^" + k + r"=(.*)$", ENV.read_text(encoding="utf-8"), re.M)
    print("  " + k + " = " + (mask(m.group(1)) if m else "<NOT PRESENT>"))
