with open(
    "C:/Users/THINKPAD/Desktop/Yazılım/BB-PAXDATA/DatabaseBuilder_v5_8.py",
    encoding="utf-8",
) as f:
    lines = f.readlines()

targets = [
    "demand_records",
    "pattern_records",
    "panel_dynamics",
    "discourse_network_edges",
    "country_references",
    "negation_aware_diplo",
]

with open("scratch/matches.txt", "w", encoding="utf-8") as out:
    for target in targets:
        out.write(f"=== Matches for {target} ===\n")
        for idx, line in enumerate(lines):
            if target in line:
                out.write(f"Line {idx + 1}: {line.strip()}\n")
