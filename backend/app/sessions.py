# Flask blueprint for chat sessions and messages, saved to PostgreSQL.
from flask import Blueprint, jsonify, request

from app.config import OLLAMA_MODEL
from app.db import get_connection
from app.extractor import ExtractionResult, FIELD_KEYS, extract_fields
from app.field_questions import FIELD_QUESTIONS, asked_keys_from_texts, next_question_key
from app.session_state import build_state
from app.symptom_matcher import load_catalog, match_symptom

sessions_bp = Blueprint("sessions", __name__)

GREETING_TEXT = "Xin chào. Bạn hãy mô tả triệu chứng chính, thời điểm bắt đầu và mức độ khó chịu hiện tại."
MAX_TEXT_LENGTH = 1000

MAX_TURNS = 6
OFF_TOPIC_LIMIT = 3
END_REASON_COMPLETED = 1
END_REASON_HANDOVER = 4
OUTCOME_EMERGENCY = 1
OUTCOME_CLINICAL = 2
HANDOVER_TEXT = "NAI sẽ chuyển hồ sơ của bạn đến nhân viên hỗ trợ gần nhất! Bạn vui lòng đợi một tí nhé."

EMERGENCY_TEXT = "Triệu chứng của bạn cần được chuyển cấp cứu. NAI sẽ thông báo cho nhân viên y tế gần nhất! Bạn vui lòng đợi một tí nhé."
EMERGENCY_EVIDENCE_TEMPLATE = "Theo luật cấp cứu số {rule_id}: Triệu chứng của bạn có dấu hiệu {rule_name}."
CLINICAL_TEXT = "NAI đã ghi nhận thông tin của bạn. Hồ sơ sẽ được chuyển đến bộ phận khám lâm sàng, bạn vui lòng đợi một tí nhé."

ROLE_USER = 1
ROLE_CHATBOT = 2

INSERT_SESSION_SQL = "INSERT INTO tt_hoithoai DEFAULT VALUES RETURNING hoithoai_id"

INSERT_MESSAGE_SQL = """
    INSERT INTO tt_tinnhan (hoithoai_id, vaitro_id, tinnhan_thutu, soluot_hoidap, hoithoai_noidung)
    VALUES (
        %s, %s,
        (SELECT COALESCE(MAX(tinnhan_thutu), 0) + 1 FROM tt_tinnhan WHERE hoithoai_id = %s),
        %s, %s
    )
    RETURNING tinnhan_id, vaitro_id, tinnhan_thutu, soluot_hoidap, hoithoai_noidung, thoigian_tao
"""

SELECT_SESSION_FOR_UPDATE_SQL = """
    SELECT hoithoai_trangthai, thoigian_ketthuc, lydoketthuc_id, huongxutri_id
    FROM tt_hoithoai WHERE hoithoai_id = %s FOR UPDATE
"""

SELECT_SESSION_SQL = """
    SELECT hoithoai_trangthai, thoigian_ketthuc, lydoketthuc_id, huongxutri_id
    FROM tt_hoithoai WHERE hoithoai_id = %s
"""

COUNT_PATIENT_MESSAGES_SQL = "SELECT COUNT(*) FROM tt_tinnhan WHERE hoithoai_id = %s AND vaitro_id = %s"

SELECT_MESSAGES_SQL = """
    SELECT tinnhan_id, vaitro_id, tinnhan_thutu, soluot_hoidap, hoithoai_noidung, thoigian_tao
    FROM tt_tinnhan WHERE hoithoai_id = %s ORDER BY tinnhan_thutu
"""

UPDATE_SESSION_END_SQL = """
    UPDATE tt_hoithoai
    SET hoithoai_trangthai = false, thoigian_ketthuc = now(), khoahoithoai = true,
        lydoketthuc_id = %s, huongxutri_id = %s, luat_id = %s
    WHERE hoithoai_id = %s
"""

CHECK_REASON_SQL = "SELECT 1 FROM tm_lydoketthuc WHERE lydoketthuc_id = %s AND active"
CHECK_OUTCOME_SQL = "SELECT 1 FROM tm_huongxutri WHERE huongxutri_id = %s AND active"

SELECT_ACTIVE_PROMPT_SQL = """
    SELECT prompt_id, prompt_noidung FROM tm_prompt
    WHERE active ORDER BY prompt_id DESC LIMIT 1
"""

COUNT_OFF_TOPIC_SQL = "SELECT COUNT(*) FROM tt_tinnhan_ketqua WHERE hoithoai_id = %s AND off_topic"

SELECT_CHATBOT_TEXTS_SQL = "SELECT hoithoai_noidung FROM tt_tinnhan WHERE hoithoai_id = %s AND vaitro_id = %s"

SELECT_QUESTION_SQL = """
    SELECT hoithoai_noidung FROM tt_tinnhan
    WHERE hoithoai_id = %s AND vaitro_id = %s AND tinnhan_thutu < %s
    ORDER BY tinnhan_thutu DESC LIMIT 1
"""

INSERT_KETQUA_SQL = """
    INSERT INTO tt_tinnhan_ketqua (
        hoithoai_id, tinnhan_id, prompt_id, phanhoi_mohinh_goc, tongthoigian_xuly,
        tinnhan_hople, noidung_loi_text, off_topic, phienban_model
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING ketqua_id
"""

INSERT_PHANTICH_SQL = """
    INSERT INTO tt_tinnhan_phantich (
        hoithoai_id, ketqua_id, traloi_khoiphat, traloi_yeuto_tanggiam, traloi_trieuchung,
        traloi_vitri_huonglan, traloi_mucdo, traloi_dienbien
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""

SELECT_MATCHING_RULE_SQL = """
    SELECT l.luat_id, l.luat_mota
    FROM tm_luat_capcuu l
    JOIN tt_capcuu_trieuchung c ON c.luat_id = l.luat_id
    WHERE l.active
    GROUP BY l.luat_id
    HAVING COUNT(*) = COUNT(*) FILTER (WHERE c.trieuchung_id IN (
        SELECT trieuchung_id FROM tt_tinnhan_trieuchung
        WHERE hoithoai_id = %s AND trangthai AND trieuchung_id IS NOT NULL
    ))
    ORDER BY l.luat_id
    LIMIT 1
"""

INSERT_TRIEUCHUNG_SQL = """
    INSERT INTO tt_tinnhan_trieuchung (hoithoai_id, ketqua_id, trieuchung_diengiai, trieuchung_id, trangthai)
    VALUES (%s, %s, %s, %s, %s)
"""


@sessions_bp.post("/sessions")
def create_session():
    # Create a session with column defaults and save the greeting.
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(INSERT_SESSION_SQL)
        session_id = cur.fetchone()[0]
        greeting = insert_message(cur, session_id, ROLE_CHATBOT, 0, GREETING_TEXT)
        state = build_state(cur, session_id)
    return jsonify(session_id=session_id, active=True, messages=[message_json(greeting)], state=state), 201


@sessions_bp.post("/sessions/<int:session_id>/messages")
def send_message(session_id):
    # Save the patient message, extract OPQRST, save the result, then check the rules and reply.
    body = request.get_json(silent=True)
    text = body.get("text") if isinstance(body, dict) else None
    if not isinstance(text, str) or not text.strip():
        return jsonify(detail="text is required"), 400
    text = text.strip()
    if len(text) > MAX_TEXT_LENGTH:
        return jsonify(detail=f"text must be at most {MAX_TEXT_LENGTH} characters"), 400

    with get_connection() as conn, conn.cursor() as cur:
        session = fetch_session_for_update(cur, session_id)
        if session is None:
            return jsonify(detail="session not found"), 404
        if not session[0]:
            return jsonify(detail="session already ended"), 409
        prompt = fetch_active_prompt(cur)
        if prompt is None:
            return jsonify(detail="no active prompt in tm_prompt; run seed_prompt"), 500
        cur.execute(COUNT_PATIENT_MESSAGES_SQL, (session_id, ROLE_USER))
        round_no = cur.fetchone()[0] + 1
        patient = insert_message(cur, session_id, ROLE_USER, round_no, text)
        question_text = fetch_question(cur, session_id, patient[2])

    prompt_id, prompt_text = prompt
    try:
        result = extract_fields(prompt_text, question_text, text)
    except Exception as error:
        print(f"extraction failed unexpectedly: {type(error).__name__}")
        result = ExtractionResult(False, "", OLLAMA_MODEL, 0, error_text="unexpected error")

    try:
        with get_connection() as conn, conn.cursor() as cur:
            ketqua_id = insert_ketqua(cur, session_id, patient[0], prompt_id, result)
            if result.valid and not result.off_topic:
                insert_phantich(cur, session_id, ketqua_id, result.fields)
                catalog = load_catalog(cur)
                for symptom in result.symptoms:
                    insert_trieuchung(cur, session_id, ketqua_id, symptom, match_symptom(symptom["phrase"], catalog))
    except Exception as error:
        print(f"saving extraction failed: {type(error).__name__}")
        result = ExtractionResult(False, result.raw_text, result.model, result.elapsed_ms, error_text="save failed")

    with get_connection() as conn, conn.cursor() as cur:
        fetch_session_for_update(cur, session_id)
        rule = find_matching_rule(cur, session_id)
        if rule is not None:
            rule_id, rule_name = rule
            evidence_text = EMERGENCY_EVIDENCE_TEMPLATE.format(rule_id=rule_id, rule_name=rule_name)
            reply_text, session_ended = f"{evidence_text} {EMERGENCY_TEXT}", True
            end_values = (END_REASON_COMPLETED, OUTCOME_EMERGENCY, rule_id)
        elif count_off_topic(cur, session_id) >= OFF_TOPIC_LIMIT:
            reply_text, session_ended = HANDOVER_TEXT, True
            end_values = (END_REASON_HANDOVER, None, None)
        else:
            state = build_state(cur, session_id)
            next_key = next_question_key(state["opqrst"], fetch_asked_keys(cur, session_id))
            if state["filled_count"] == len(FIELD_KEYS) or round_no >= MAX_TURNS or next_key is None:
                reply_text, session_ended = CLINICAL_TEXT, True
                end_values = (END_REASON_COMPLETED, OUTCOME_CLINICAL, None)
            else:
                reply_text, session_ended = FIELD_QUESTIONS[next_key], False
        reply = insert_message(cur, session_id, ROLE_CHATBOT, round_no, reply_text)
        if session_ended:
            cur.execute(UPDATE_SESSION_END_SQL, (*end_values, session_id))

    return jsonify(
        session_id=session_id,
        messages=[message_json(patient), message_json(reply)],
        extraction=extraction_json(result),
        ended=session_ended,
        state=fetch_state(session_id),
    ), 201


@sessions_bp.get("/sessions/<int:session_id>")
def get_session(session_id):
    # Return the session status and all its messages in order.
    with get_connection() as conn, conn.cursor() as cur:
        session = fetch_session(cur, SELECT_SESSION_SQL, session_id)
        if session is None:
            return jsonify(detail="session not found"), 404
        cur.execute(SELECT_MESSAGES_SQL, (session_id,))
        messages = [message_json(row) for row in cur.fetchall()]
        state = build_state(cur, session_id)
    is_active, ended_at, reason_id, outcome_id = session
    return jsonify(
        session_id=session_id,
        active=is_active,
        ended_at=ended_at.isoformat() if ended_at else None,
        end_reason_id=reason_id,
        outcome_id=outcome_id,
        messages=messages,
        state=state,
    )


@sessions_bp.post("/sessions/<int:session_id>/end")
def end_session(session_id):
    # Mark the session ended with a reason and an optional outcome.
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(detail="JSON body is required"), 400
    reason_id = body.get("end_reason_id")
    outcome_id = body.get("outcome_id")
    if not is_valid_id(reason_id, 1, 3):
        return jsonify(detail="end_reason_id must be 1, 2 or 3"), 400
    if outcome_id is not None and (reason_id != 1 or not is_valid_id(outcome_id, 1, 2)):
        return jsonify(detail="outcome_id must be 1 or 2, only when end_reason_id is 1"), 400

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(CHECK_REASON_SQL, (reason_id,))
        if cur.fetchone() is None:
            return jsonify(detail="end_reason_id is not an active reason"), 400
        if outcome_id is not None:
            cur.execute(CHECK_OUTCOME_SQL, (outcome_id,))
            if cur.fetchone() is None:
                return jsonify(detail="outcome_id is not an active outcome"), 400
        session = fetch_session_for_update(cur, session_id)
        if session is None:
            return jsonify(detail="session not found"), 404
        if not session[0]:
            return jsonify(detail="session already ended"), 409
        cur.execute(UPDATE_SESSION_END_SQL, (reason_id, outcome_id, None, session_id))
    return jsonify(session_id=session_id, active=False, end_reason_id=reason_id, outcome_id=outcome_id)


def is_valid_id(value, low, high):
    # True when value is an integer between low and high (booleans excluded).
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def fetch_session(cur, sql, session_id):
    # Return the session row for the given SQL, or None when not found.
    cur.execute(sql, (session_id,))
    return cur.fetchone()


def fetch_session_for_update(cur, session_id):
    # Lock the session row for the rest of the transaction.
    return fetch_session(cur, SELECT_SESSION_FOR_UPDATE_SQL, session_id)


def insert_message(cur, session_id, role_id, round_no, text):
    # Insert one message; its order number is assigned in SQL.
    cur.execute(INSERT_MESSAGE_SQL, (session_id, role_id, session_id, round_no, text))
    return cur.fetchone()


def fetch_active_prompt(cur):
    # Return (prompt_id, prompt_text) of the newest active prompt, or None.
    cur.execute(SELECT_ACTIVE_PROMPT_SQL)
    return cur.fetchone()


def fetch_question(cur, session_id, patient_order):
    # Return the last chatbot message before the patient message.
    cur.execute(SELECT_QUESTION_SQL, (session_id, ROLE_CHATBOT, patient_order))
    row = cur.fetchone()
    return row[0] if row else ""


def insert_ketqua(cur, session_id, message_id, prompt_id, result):
    # Save one extraction run and return its ketqua_id.
    cur.execute(
        INSERT_KETQUA_SQL,
        (
            session_id,
            message_id,
            prompt_id,
            result.raw_text,
            result.elapsed_ms,
            result.valid,
            result.error_text,
            result.off_topic,
            result.model,
        ),
    )
    return cur.fetchone()[0]


def insert_phantich(cur, session_id, ketqua_id, fields):
    # Save the six OPQRST values of a valid, on-topic answer.
    cur.execute(INSERT_PHANTICH_SQL, (session_id, ketqua_id, *[fields[key] for key in FIELD_KEYS]))


def count_off_topic(cur, session_id):
    # Count the off-topic patient messages saved for the session.
    cur.execute(COUNT_OFF_TOPIC_SQL, (session_id,))
    return cur.fetchone()[0]


def fetch_asked_keys(cur, session_id):
    # Read the chatbot texts of the session and return the keys of the questions already asked.
    cur.execute(SELECT_CHATBOT_TEXTS_SQL, (session_id, ROLE_CHATBOT))
    return asked_keys_from_texts(row[0] for row in cur.fetchall())


def find_matching_rule(cur, session_id):
    # Run the emergency rule query and return (luat_id, luat_mota), or None.
    cur.execute(SELECT_MATCHING_RULE_SQL, (session_id,))
    row = cur.fetchone()
    return (row[0], row[1]) if row else None


def insert_trieuchung(cur, session_id, ketqua_id, symptom, trieuchung_id):
    # Save one symptom phrase with its catalog id (None when nothing matched).
    cur.execute(INSERT_TRIEUCHUNG_SQL, (session_id, ketqua_id, symptom["phrase"], trieuchung_id, symptom["status"]))


def fetch_state(session_id):
    # Read the state with a fresh connection; None when the read fails.
    try:
        with get_connection() as conn, conn.cursor() as cur:
            return build_state(cur, session_id)
    except Exception as error:
        print(f"building state failed: {type(error).__name__}")
        return None


def extraction_json(result):
    # Convert an extraction result to the response shape.
    return {
        "valid": result.valid,
        "off_topic": result.off_topic,
        "fields": result.fields,
        "processing_ms": result.elapsed_ms,
    }


def message_json(row):
    # Convert a message row to the JSON shape used by the frontend.
    message_id, role_id, order, round_no, text, created_at = row
    return {
        "id": message_id,
        "role": "user" if role_id == ROLE_USER else "chatbot",
        "order": order,
        "round": round_no,
        "text": text,
        "created_at": created_at.isoformat(),
    }
