"""Offline decision boundary. Live Jev selection is deliberately not enabled.

This normalized contract is independent of the vendor wire format. Confidence
is a routing threshold, never a claim of calibrated accuracy or authority.
"""
import math


def validate_disabled_config(config):
    """Do not turn a credential/configuration edit into unvalidated Jev traffic."""
    if config != {"mode": "deterministic", "jev_enabled": False} or type(config.get("jev_enabled")) is not bool:
        raise ValueError("Only deterministic routing with Jev explicitly disabled is supported")


def validate_catalogue(allowed):
    """Validate route catalogue: nonempty list/tuple/set/frozenset of unique nonempty string IDs <= 128 chars, max 64 IDs."""
    if type(allowed) not in (list, tuple, set, frozenset):
        return False
    if not (1 <= len(allowed) <= 64):
        return False
    seen = set()
    for item in allowed:
        if type(item) is not str or not (1 <= len(item) <= 128):
            return False
        if item in seen:
            return False
        seen.add(item)
    return True


def normalize_choice(response, allowed, *, in_domain=False):
    """Validate the documented TypeSafe Choice wire response, fail to None.

    in_domain comes from the evaluator's labelled domain, never the model.
    """
    if not validate_catalogue(allowed):
        return None
    try:
        answer = response["answers"]["route"]
        probabilities = answer["probabilities"]
        confidence = answer["confidence"]
        if (answer["type"] != "choice" or not isinstance(probabilities, dict)
            or set(probabilities) != set(allowed)
            or any(type(v) not in (int, float) or not 0 <= v <= 1 or not math.isfinite(v) for v in probabilities.values())
            or not math.isclose(sum(probabilities.values()), 1, abs_tol=0.001)
            or type(confidence) not in (int, float) or not 0 <= confidence <= 1 or not math.isfinite(confidence)
            or answer["choice"] not in probabilities
            or probabilities[answer["choice"]] < max(probabilities.values())):
            return None
        return {"route": answer["choice"], "confidence": confidence, "in_domain": in_domain}
    except (TypeError, KeyError, ValueError):
        return None


def select_route(decision, allowed, deterministic, *, calibrated=False, threshold=0.9):
    if not validate_catalogue(allowed):
        raise ValueError("Catalogue must be a nonempty list/tuple/set/frozenset of unique nonempty string IDs")
    if type(deterministic) is not str:
        return None, "invalid_deterministic_route"
    if deterministic not in allowed:
        raise ValueError("Deterministic route must already be allowed")
    if not calibrated:
        return deterministic, "live_calibration_pending"
    if (type(threshold) not in (int, float) or isinstance(threshold, bool)
            or not 0 <= threshold <= 1 or not math.isfinite(threshold)):
        return deterministic, "invalid_threshold"
    if not isinstance(decision, dict) or set(decision) != {"route", "confidence", "in_domain"}:
        return deterministic, "malformed_or_unavailable"
    confidence = decision["confidence"]
    if type(confidence) not in (float, int) or not 0 <= confidence <= 1 or not math.isfinite(confidence):
        return deterministic, "invalid_confidence"
    if decision["route"] not in allowed:
        return deterministic, "authority_violation"
    if decision["in_domain"] is not True or confidence < threshold:
        return deterministic, "review_or_deterministic"
    return decision["route"], "evaluated_decision"
