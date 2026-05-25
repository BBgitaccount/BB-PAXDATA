# Load SPEAKER_MAP from old DatabaseBuilder
with open(
    "C:/Users/THINKPAD/Desktop/Yazılım/BB-PAXDATA/DatabaseBuilder_v5_8.py",
    encoding="utf-8",
) as f:
    text = f.read()

import re

matches = re.search(r"SPEAKER_MAP = \{(.*?)\}", text, re.DOTALL)
if matches:
    content = matches.group(1)
    # Parse the content line by line
    speaker_power = {}
    power_levels = {
        "head_of_state": 10,
        "head_of_government": 9,
        "vice_president": 8,
        "minister": 7,
        "deputy_minister": 6,
        "intl_official": 7,
        "diplomat": 6,
        "advisor": 5,
        "expert": 4,
        "moderator": 3,
        "journalist": 2,
        "panelist": 3,
    }
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Extract name and details
        # e.g., "Recep Tayyip Erdoğan":          ("Turkey",          "President",                                         "head_of_state"),
        m = re.match(r'"([^"]+)"\s*:\s*\(([^)]+)\)', line)
        if m:
            name = m.group(1)
            details = m.group(2)
            parts = [p.strip().strip('"') for p in details.split(",")]
            if len(parts) >= 3:
                role_key = parts[2]
                p_level = power_levels.get(role_key, 3)
                speaker_power[name] = p_level

    with open("scratch/speaker_power_map.txt", "w", encoding="utf-8") as out:
        out.write("SPEAKER_POWER_MAP = {\n")
        for k, v in sorted(speaker_power.items()):
            out.write(f'    "{k}": {v},\n')
        out.write("}\n")
    print(f"Extracted {len(speaker_power)} speakers.")
else:
    print("SPEAKER_MAP not found")
