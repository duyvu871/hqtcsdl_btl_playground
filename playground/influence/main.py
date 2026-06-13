"""Backward-compatible entrypoint.

Cho phép chạy:
    uv run python main.py
hoặc:
    uv run python run.py
"""

from run import main


if __name__ == "__main__":
    main()
