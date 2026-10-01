import os
import sys

sys.path.insert(0, os.getcwd())


def main():
    import feature

    # After the mid-task config drift, the implementation must reflect feature: new.
    ok = feature.label() == "enabled"
    print(f"label() = {feature.label()!r}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
