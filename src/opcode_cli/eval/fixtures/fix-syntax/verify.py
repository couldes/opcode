import subprocess
import sys


def main():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "test_calc.py"],
        capture_output=True,
        text=True,
    )
    print(proc.stdout)
    print(proc.stderr, file=sys.stderr)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
