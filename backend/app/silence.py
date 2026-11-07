"""Silence map: compare replies we'd expect from a block with replies we actually got."""

BASELINE_REPLY_RATE = 0.7
FLAG_RATIO = 0.4
MIN_HOUSEHOLDS = 5
SETTLE_MINUTES = 30  # give replies time to arrive before flagging anything


def block_stats(blocks, households, cases_by_id, outreach_at, now):
    max_depth = max((b["flood_depth_ft"] for b in blocks), default=1) or 1
    by_block = {}
    for h in households:
        if not h.get("hidden_from_map"):
            by_block.setdefault(h["block_id"], []).append(h)

    settled = outreach_at is not None and (now - outreach_at) >= SETTLE_MINUTES
    out = []
    for b in blocks:
        hh = by_block.get(b["id"], [])
        n = len(hh)
        replies = sum(1 for h in hh if cases_by_id[h["id"]]["last_reply_at"] is not None)
        expected = round(n * BASELINE_REPLY_RATE, 1)
        in_zone = b["flood_depth_ft"] > 0
        ratio = (replies / expected) if expected else 1.0
        priority = round(max(0.0, 1 - ratio) * (b["flood_depth_ft"] / max_depth) * (0.5 + b["svi"]), 3) if in_zone else 0
        flagged = bool(in_zone and settled and n >= MIN_HOUSEHOLDS and ratio < FLAG_RATIO)
        out.append({**b, "households": n, "replies": replies, "expected": expected,
                    "ratio": round(ratio, 2), "priority": priority if outreach_at is not None else 0,
                    "flagged": flagged})
    return out
