import subprocess
import sys

commands = [
    [sys.executable, "generate_daily_report.py"],
    [sys.executable, "push_to_notion.py"]
]

for cmd in commands:
    result = subprocess.run(cmd, check=True)
