# Fixed questions that ask for one missing OPQRST field (pure Python, no database).
FIELD_QUESTIONS = {
    "onset": "Triệu chứng này bắt đầu từ khi nào?",
    "provocation_palliation": "Có điều gì làm triệu chứng nặng hơn hoặc đỡ hơn không, ví dụ nghỉ ngơi, vận động hay uống thuốc?",
    "quality": "Bạn cảm thấy triệu chứng như thế nào, ví dụ đau nhói, đau âm ỉ, nặng nề hay tức?",
    "region_radiation": "Triệu chứng ở vị trí nào và có lan sang chỗ khác không?",
    "severity": "Mức độ khó chịu hiện tại là bao nhiêu trên thang điểm từ 0 đến 10?",
    "time_course": "Từ lúc bắt đầu đến giờ, triệu chứng thay đổi thế nào: nặng dần, đỡ dần, liên tục hay từng cơn?",
}


def asked_keys_from_texts(texts):
    # Return the keys whose question text is one of the given chatbot message texts.
    texts = set(texts)
    return {key for key, question in FIELD_QUESTIONS.items() if question in texts}


def next_question_key(opqrst, asked_keys):
    # Return the first missing field that was not asked yet, or None.
    for key in FIELD_QUESTIONS:
        if opqrst.get(key) is None and key not in asked_keys:
            return key
    return None
