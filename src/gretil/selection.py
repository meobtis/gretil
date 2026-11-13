"""Which manifest entries a command works on."""

from typing import Any, Dict, List

# sanskrit: every Sanskrit text in GRETIL. buddhist: the two Buddhist sections (RLBuddh and Bauddha).
CATEGORIES = ["sanskrit", "buddhist", "rlbuddh", "bauddha"]


def select(entries: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    if category == "buddhist":
        return [e for e in entries if e.get("buddhist")]
    if category == "rlbuddh":
        return [e for e in entries if e.get("section_id") == "RLBuddh"]
    if category == "bauddha":
        return [e for e in entries if e.get("section_id") == "Bauddha"]
    return list(entries)
