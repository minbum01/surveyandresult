"""
claude CLI 동작 테스트
"""
import subprocess, os, sys

CLAUDE_CMD = r"C:\Users\admin\AppData\Roaming\npm\claude.cmd"

env = os.environ.copy()
env.pop("CLAUDECODE", None)
env.pop("CLAUDE_CODE", None)

print(f"CLAUDECODE in env: {'CLAUDECODE' in os.environ}")
print(f"Testing claude CLI...")

try:
    result = subprocess.run(
        [CLAUDE_CMD, "-p", "1+1은? 숫자만 답해"],
        capture_output=True,
        timeout=60,
        shell=False,
        env=env
    )
    print(f"returncode: {result.returncode}")
    print(f"stdout: {result.stdout.decode('utf-8', errors='replace')[:300]}")
    print(f"stderr: {result.stderr.decode('utf-8', errors='replace')[:300]}")
except Exception as e:
    print(f"Exception: {e}")

sys.stdout.flush()
