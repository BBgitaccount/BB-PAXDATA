with open(
    "C:/Users/THINKPAD/Desktop/Yazılım/BB-PAXDATA/DatabaseBuilder_v5_8.py",
    encoding="utf-8",
) as f:
    text = f.read()

matches = []
for idx, line in enumerate(text.splitlines()):
    if "s_polit" in line:
        matches.append(f"Line {idx + 1}: {line.strip()}")
        # print 5 lines before and after
        for offset in range(-10, 10):
            if 0 <= idx + offset < len(text.splitlines()):
                matches.append(
                    f"  {offset:+d}: {text.splitlines()[idx + offset].rstrip()}"
                )

with open("scratch/s_polit_search.txt", "w", encoding="utf-8") as out:
    for m in matches:
        out.write(m + "\n")
