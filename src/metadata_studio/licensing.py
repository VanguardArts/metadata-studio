"""Licensing and tiering (Free vs. Pro).

Monetization model per the product brief: a Free basic version and a Pro tier
(€9–19). The tier gates the heavier/power features; everything else is free.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


FREE_FEATURES = [
    "inspect",
    "inspect_exif", "inspect_id3", "inspect_pdf", "inspect_document",
    "detect_hidden_metadata", "detect_thumbnails",
    "sanitize_level0", "sanitize_level1", "audio_clean",
    "document_clean",
]

PRO_FEATURES = [
    "sanitize_level2", "sanitize_level3",       # stronger watermark ladder
    "batch_processing", "folder_monitoring",
    "before_after_comparison", "report_export",
    "custom_credits", "detector_plugins",
]

PRO_PRICE_EUR = 19  # upper bound of the €9–19 tier; lower tier = 9 for basic pro

TIER_FREE = "free"
TIER_PRO = "pro"


@dataclass
class License:
    tier: str = TIER_FREE
    license_key: str = ""

    def is_pro(self) -> bool:
        return self.tier == TIER_PRO

    def allows(self, feature: str) -> bool:
        if self.tier == TIER_PRO:
            return True
        return feature in FREE_FEATURES


# Canonical feature->tier map for surfacing in the GUI/README/docs.
FEATURE_TIERS: Dict[str, str] = {}
for feat in FREE_FEATURES:
    FEATURE_TIERS[feat] = TIER_FREE
for feat in PRO_FEATURES:
    FEATURE_TIERS[feat] = TIER_PRO


def tiers_for(features: List[str]) -> Dict[str, str]:
    return {f: FEATURE_TIERS.get(f, TIER_FREE) for f in features}
