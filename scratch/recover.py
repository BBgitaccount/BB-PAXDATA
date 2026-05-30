# scratch/recover.py
import subprocess

# Get all dangling blobs
result = subprocess.run(
    ["git", "fsck", "--lost-found"], capture_output=True, text=True, check=True
)
blobs = []
for line in result.stdout.splitlines():
    if "dangling blob" in line:
        blobs.append(line.split()[2])

print(f"Found {len(blobs)} dangling blobs. Checking contents...")

keywords = [
    b"SegmentAnalyzedEvent",
    b"sentence_code",
    b"actor_topic",
    b"aggregation_lineage",
    b"topic_model_versions",
    b"topic_mappings",
]

for blob in blobs:
    # Get content of the blob as bytes
    content_res = subprocess.run(
        ["git", "cat-file", "-p", blob], capture_output=True, check=False
    )
    content = content_res.stdout

    # Check if this blob matches any keywords
    matches = [kw for kw in keywords if kw in content]
    if matches:
        # Try decoding with replace
        text_content = content.decode("utf-8", errors="replace")
        first_lines = [
            line.strip() for line in text_content.splitlines()[:5] if line.strip()
        ]
        first_few = " | ".join(first_lines)
        print(f"\nBlob {blob} matches {[kw.decode() for kw in matches]}:")
        print(f"  First lines: {first_few[:200]}")
        print(f"  Size: {len(content)} bytes, lines: {len(text_content.splitlines())}")
