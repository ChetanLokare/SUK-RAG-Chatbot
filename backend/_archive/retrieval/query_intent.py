def classify_intent(query: str) -> str:

    q = query.lower()

    # =====================================================
    # INTENTS
    # =====================================================

    if any(x in q for x in ["fee", "fees", "cost", "price"]):
        return "fees"

    if any(x in q for x in ["admission", "apply", "eligibility"]):
        return "admission"

    if any(x in q for x in ["syllabus", "subjects", "curriculum"]):
        return "academic"

    if any(x in q for x in ["contact", "phone", "email"]):
        return "contact"

    if any(x in q for x in ["scholarship", "grant"]):
        return "scholarship"

    if any(x in q for x in ["result", "exam", "timetable"]):
        return "exam"

    if any(x in q for x in ["department", "faculty", "staff"]):
        return "department"

    return "general"