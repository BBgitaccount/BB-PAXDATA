# scratch/search_agg.py
import subprocess

result = subprocess.run(
    ["git", "fsck", "--lost-found"], capture_output=True, text=True, check=True
)
blobs = []
for line in result.stdout.splitlines():
    if "dangling blob" in line:
        blobs.append(line.split()[2])

with open("scratch/agg_search.txt", "w", encoding="utf-8") as f:
    for blob in blobs:
        content_res = subprocess.run(
            ["git", "cat-file", "-p", blob], capture_output=True, check=False
        )
        content = content_res.stdout
        if b"AggregationEngine" in content or b"aggregation_engine" in content:
            f.write(f"Match in blob {blob}\n")
            f.write(content.decode("utf-8", errors="replace")[:1000])
            f.write("\n===================================\n")
