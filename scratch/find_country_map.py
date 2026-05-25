with open(
    "C:/Users/THINKPAD/Desktop/Yazılım/BB-PAXDATA/DatabaseBuilder_v5_8.py",
    encoding="utf-8",
) as f:
    text = f.read()

import re

matches = re.findall(
    r"COUNTRY_MENTION_MAP = \{.*?\}(?=\s*#|\s*\n\n|\s*\w+\s*=)",
    text,
    re.DOTALL | re.IGNORECASE,
)
if not matches:
    # try broader match
    lines = text.splitlines()
    matches = []
    for idx, line in enumerate(lines):
        if "COUNTRY_MENTION_MAP" in line:
            matches.append("\n".join(lines[idx : idx + 45]))

with open("scratch/country_mention_map.txt", "w", encoding="utf-8") as out:
    for m in matches:
        out.write(m + "\n")
