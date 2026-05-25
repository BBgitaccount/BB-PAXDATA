with open(
    "C:/Users/THINKPAD/Desktop/Yazılım/BB-PAXDATA/DatabaseBuilder_v5_8.py",
    encoding="utf-8",
) as f:
    text = f.read()

import re

matches = re.findall(
    r"def (?:compute_politeness|politeness|detect_politeness|face_threat|face_save)\b.*?:.*?(?=def |\Z)",
    text,
    re.DOTALL | re.IGNORECASE,
)
if not matches:
    # try searching for any mention of politeness_ratio
    matches = [
        line
        for line in text.splitlines()
        if "politeness_ratio" in line or "face_threat_count" in line
    ]

with open("scratch/politeness_def.txt", "w", encoding="utf-8") as out:
    for m in matches:
        out.write(m + "\n")
