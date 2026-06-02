"""
tier_limits.py — Fuente de verdad de los límites por tier de suscripción.

Tiers:
  free   → hasta 5 nadadores, historial 3 meses, sin exportación
  coach  → hasta 20 nadadores, historial completo, exportación PDF
  club   → ilimitado, multi-entrenador, exportación

Uso:
  from app.core.tier_limits import get_tier_limit
  max_swimmers = get_tier_limit("coach", "swimmers")  # → 20
"""

TIER_LIMITS: dict[str, dict[str, int | bool]] = {
    "free": {
        "swimmers": 5,
        "history_months": 3,
        "export": False,
        "multi_coach": False,
        "macrocycles": 1,
    },
    "coach": {
        "swimmers": 20,
        "history_months": 9999,
        "export": True,
        "multi_coach": False,
        "macrocycles": 9999,
    },
    "club": {
        "swimmers": 9999,
        "history_months": 9999,
        "export": True,
        "multi_coach": True,
        "macrocycles": 9999,
    },
}


def get_tier_limit(tier: str, resource: str) -> int | bool:
    tier_data = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    return tier_data.get(resource, False)
