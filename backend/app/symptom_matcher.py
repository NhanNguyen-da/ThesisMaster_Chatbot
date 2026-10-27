# Matches a symptom phrase from the LLM to the symptom catalog (tm_trieuchung_type).
import re
import unicodedata

SELECT_CATALOG_SQL = """
    SELECT t.trieuchung_noidung, t.trieuchung_id
    FROM tm_trieuchung_type t JOIN tm_trieuchung s ON s.trieuchung_id = t.trieuchung_id
    WHERE t.active AND s.active
"""


def load_catalog(cur):
    # Read the active catalog phrases as (normalized_phrase, trieuchung_id) pairs.
    cur.execute(SELECT_CATALOG_SQL)
    return [(normalize_text(phrase), trieuchung_id) for phrase, trieuchung_id in cur.fetchall()]


def normalize_text(text):
    # NFC, lowercase, non-letters to spaces, collapsed spaces; diacritics are kept.
    text = unicodedata.normalize("NFC", text).lower()
    return re.sub(r"[^\w]+", " ", text).strip()


def match_symptom(phrase, catalog):
    # Return the trieuchung_id of the longest catalog phrase inside the symptom phrase, or None.
    padded = f" {normalize_text(phrase)} "
    best_length = 0
    best_id = None
    for catalog_phrase, trieuchung_id in catalog:
        if not catalog_phrase or f" {catalog_phrase} " not in padded:
            continue
        length = len(catalog_phrase)
        if length > best_length or (length == best_length and trieuchung_id < best_id):
            best_length = length
            best_id = trieuchung_id
    return best_id
