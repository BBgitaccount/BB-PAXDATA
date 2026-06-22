with open(
    "C:/Users/THINKPAD/Desktop/Yazılım/BB-PAXDATA/DatabaseBuilder_v5_8.py",
    encoding="utf-8",
) as f:
    lines = f.readlines()

with open("scratch/dynamics_def.txt", "w", encoding="utf-8") as out:
    out.write("=== Matches for all_dynamics_rows ===\n")
    for idx, line in enumerate(lines):
        if "all_dynamics_rows" in line:
            out.write(f"Line {idx + 1}: {line.strip()}\n")
            # print 15 lines before/after
            for offset in range(-15, 15):
                if 0 <= idx + offset < len(lines):
                    out.write(f"  {offset:+d}: {lines[idx + offset].rstrip()}\n")
