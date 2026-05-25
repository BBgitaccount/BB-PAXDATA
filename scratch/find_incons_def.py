with open(
    "C:/Users/THINKPAD/Desktop/Yazılım/BB-PAXDATA/DatabaseBuilder_v5_8.py",
    encoding="utf-8",
) as f:
    text = f.read()

import re

matches = re.findall(
    r"def \w*inconsistency\w*.*?:.*?(?=def |\Z)", text, re.DOTALL | re.IGNORECASE
)
with open("scratch/incons_def.txt", "w", encoding="utf-8") as out:
    for m in matches:
        out.write(m + "\n")
