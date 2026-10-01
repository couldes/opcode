import os
import sys

sys.path.insert(0, os.getcwd())


def main():
    import app
    import config
    import data

    ok = True
    for feature, key in config.FEATURES.items():
        want = data.LOOKUP[key]
        got = app.render_color(feature)
        if got != want:
            print(f"MISMATCH {feature}: want {want!r}, got {got!r}")
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
