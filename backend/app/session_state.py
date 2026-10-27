# Reads the saved rows of one session and builds the "state" object shown on the screen (read only).
from app.extractor import FIELD_KEYS

ROLE_USER = 1

# Column of tt_tinnhan_phantich for each OPQRST key, in display order.
PHANTICH_COLUMNS = (
    ("onset", "traloi_khoiphat"),
    ("provocation_palliation", "traloi_yeuto_tanggiam"),
    ("quality", "traloi_trieuchung"),
    ("region_radiation", "traloi_vitri_huonglan"),
    ("severity", "traloi_mucdo"),
    ("time_course", "traloi_dienbien"),
)

COUNT_PATIENT_MESSAGES_SQL = "SELECT COUNT(*) FROM tt_tinnhan WHERE hoithoai_id = %s AND vaitro_id = %s"

SELECT_PHANTICH_SQL = f"""
    SELECT ketqua_id, {", ".join(column for _, column in PHANTICH_COLUMNS)}
    FROM tt_tinnhan_phantich WHERE hoithoai_id = %s ORDER BY phantich_id DESC
"""

SELECT_SYMPTOMS_SQL = """
    SELECT latest.trieuchung_diengiai, s.trieuchung_ten, latest.trangthai
    FROM (
        SELECT DISTINCT ON (trieuchung_diengiai)
            tinnhan_trieuchung_id, trieuchung_diengiai, trieuchung_id, trangthai
        FROM tt_tinnhan_trieuchung WHERE hoithoai_id = %s
        ORDER BY trieuchung_diengiai, tinnhan_trieuchung_id DESC
    ) latest
    LEFT JOIN tm_trieuchung s ON s.trieuchung_id = latest.trieuchung_id
    ORDER BY latest.tinnhan_trieuchung_id
"""

SELECT_RESULT_SQL = """
    SELECT h.lydoketthuc_id, h.huongxutri_id, l.luat_id, l.luat_mota
    FROM tt_hoithoai h LEFT JOIN tm_luat_capcuu l ON l.luat_id = h.luat_id
    WHERE h.hoithoai_id = %s
"""

COUNT_OFF_TOPIC_SQL = "SELECT COUNT(*) FROM tt_tinnhan_ketqua WHERE hoithoai_id = %s AND off_topic"

SELECT_LAST_RUN_SQL = """
    SELECT ketqua_id, tinnhan_hople, off_topic, tongthoigian_xuly
    FROM tt_tinnhan_ketqua WHERE hoithoai_id = %s ORDER BY ketqua_id DESC LIMIT 1
"""


def build_state(cur, session_id):
    # Read the saved rows of the session and return the state object.
    cur.execute(COUNT_PATIENT_MESSAGES_SQL, (session_id, ROLE_USER))
    round_no = cur.fetchone()[0]

    cur.execute(SELECT_PHANTICH_SQL, (session_id,))
    phantich_rows = cur.fetchall()
    opqrst = newest_values(phantich_rows)
    filled_count = sum(1 for value in opqrst.values() if value is not None)

    cur.execute(SELECT_SYMPTOMS_SQL, (session_id,))
    symptoms = [
        {"phrase": phrase, "standard_name": name, "status": status}
        for phrase, name, status in cur.fetchall()
    ]

    cur.execute(SELECT_LAST_RUN_SQL, (session_id,))
    last_run = last_run_json(cur.fetchone(), phantich_rows)

    # End reason, outcome and matched emergency rule of the session (None while not set).
    cur.execute(SELECT_RESULT_SQL, (session_id,))
    end_reason_id, outcome_id, rule_id, rule_name = cur.fetchone()

    # Number of off-topic patient messages in the session.
    cur.execute(COUNT_OFF_TOPIC_SQL, (session_id,))
    off_topic_count = cur.fetchone()[0]

    return {
        "round": round_no,
        "opqrst": opqrst,
        "filled_count": filled_count,
        "completeness_percent": round(filled_count / len(FIELD_KEYS) * 100),
        "symptoms": symptoms,
        "last_run": last_run,
        "result": {"end_reason_id": end_reason_id, "outcome_id": outcome_id, "rule_id": rule_id, "rule_name": rule_name},
        "off_topic_count": off_topic_count,
    }


def newest_values(phantich_rows):
    # Newest non-null value of each field; rows arrive newest first.
    values = {key: None for key in FIELD_KEYS}
    for row in phantich_rows:
        for (key, _), value in zip(PHANTICH_COLUMNS, row[1:]):
            if values[key] is None and value is not None:
                values[key] = value
    return values


def last_run_json(run_row, phantich_rows):
    # Build the last_run object; new_keys are the fields filled in that run's phantich row.
    if run_row is None:
        return None
    ketqua_id, valid, off_topic, processing_ms = run_row
    new_keys = []
    for row in phantich_rows:
        if row[0] == ketqua_id:
            new_keys = [key for (key, _), value in zip(PHANTICH_COLUMNS, row[1:]) if value is not None]
            break
    return {"valid": valid, "off_topic": off_topic, "processing_ms": processing_ms, "new_keys": new_keys}
