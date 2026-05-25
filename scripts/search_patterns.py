with open(
    "C:/Users/THINKPAD/Desktop/Yazılım/BB-PAXDATA/DatabaseBuilder_v5_8.py",
    encoding="utf-8",
) as f:
    lines = f.readlines()

targets = ["DEMAND_PATTERNS = {", "DEMAND_CATEGORIES = {", "RHETORIC_PATTERNS = {"]

with open("scratch/patterns_def.txt", "w", encoding="utf-8") as out:
    for target in targets:
        out.write(f"=== Matches for {target} ===\n")
        for idx, line in enumerate(lines):
            if target in line:
                out.write(f"Line {idx+1}: {line.strip()}\n")
                # print 30 lines after the match
                for offset in range(1, 40):
                    if idx + offset < len(lines):
                        out.write(f"  +{offset}: {lines[idx+offset].rstrip()}\n")
