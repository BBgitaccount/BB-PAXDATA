with open(
    "C:/Users/THINKPAD/Desktop/Yazılım/BB-PAXDATA/DatabaseBuilder_v5_8.py",
    encoding="utf-8",
) as f:
    text = f.read()

import re

matches = re.findall(
    r"def hedging_score\b.*?:.*?(?=def |\Z)", text, re.DOTALL | re.IGNORECASE
)
with open("scratch/hedging_impl.txt", "w", encoding="utf-8") as out:
    for m in matches:
        out.write(m + "\n")
