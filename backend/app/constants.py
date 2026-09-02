"""Predefined target-role and topic options for FL-03 (single source of truth
for both the API validation and the /sessions/target-options response the
frontend renders its pickers from)."""

PREDEFINED_ROLES: list[str] = [
    "Backend Engineer",
    "Frontend Engineer",
    "Data Analyst",
    "Product Manager",
]

PREDEFINED_TOPICS: list[dict[str, str]] = [
    {"value": "data_structures", "label": "Data Structures"},
    {"value": "algorithms", "label": "Algorithms"},
    {"value": "system_design", "label": "System Design"},
    {"value": "ai_ml", "label": "AI / Machine Learning"},
]

PREDEFINED_TOPIC_VALUES: set[str] = {t["value"] for t in PREDEFINED_TOPICS}
