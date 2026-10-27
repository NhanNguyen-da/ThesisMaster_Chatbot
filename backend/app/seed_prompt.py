# One-off script: stores the v1 and v2 extraction prompts in tm_prompt (run by hand).
from pathlib import Path

from app.db import get_connection

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
PROMPT_FILES = (("v1", PROMPT_DIR / "extract_v1.txt"), ("v2", PROMPT_DIR / "extract_v2.txt"))


def seed_prompt():
    # Insert each prompt version row unless it already exists.
    with get_connection() as conn, conn.cursor() as cur:
        for version, path in PROMPT_FILES:
            cur.execute("SELECT prompt_id FROM tm_prompt WHERE prompt_version = %s", (version,))
            existing = cur.fetchone()
            if existing is not None:
                print(f"prompt {version} already exists (prompt_id {existing[0]}); nothing inserted")
                continue
            cur.execute(
                "INSERT INTO tm_prompt (prompt_version, prompt_noidung, active) VALUES (%s, %s, true) RETURNING prompt_id",
                (version, path.read_text(encoding="utf-8")),
            )
            print(f"inserted prompt {version} (prompt_id {cur.fetchone()[0]})")


if __name__ == "__main__":
    seed_prompt()
