with open(
    "C:/Users/THINKPAD/Desktop/Yazılım/BB-PAXDATA/DatabaseBuilder_v5_8.py",
    encoding="utf-8",
) as f:
    text = f.read()

import re

matches = re.findall(
    r"POLITENESS_SIGNALS = \{.*?\}(?=\s*#|\s*\n\n|\s*\w+\s*=)",
    text,
    re.DOTALL | re.IGNORECASE,
)
if not matches:
    # try broader match
    matches = re.findall(r"POLITENESS_SIGNALS = \{.*?\n\}", text, re.DOTALL)
if not matches:
    # search lines matching POLITENESS_SIGNALS
    lines = text.splitlines()
    matches = []
    for idx, line in enumerate(lines):
        if "POLITENESS_SIGNALS" in line:
            matches.append("\n".join(lines[idx : idx + 40]))

with open("scratch/politeness_signals.txt", "w", encoding="utf-8") as out:
    for m in matches:
        out.write(m + "\n")
