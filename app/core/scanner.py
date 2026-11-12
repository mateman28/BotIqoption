import time
from typing import List, Dict, Optional
from app.config import config
from app.core.client import iq_client
from app.utils.logger import logger

class AssetScanner:
    def __init__(self, min_payout: float = None):
        self.min_payout = min_payout if min_payout is not None else config.MIN_PAYOUT
        self._cache: List[Dict] = []
        self._last_scan_time: float = 0.0
        self._cache_ttl: float = 20.0  # Cache for 20 seconds

    def get_high_payout_pairs(self, force_refresh: bool = False) -> List[Dict]:
        """
        Scans all available assets on IQ Option and returns pairs with payout >= min_payout (default 80%).
        Uses get_all_init_v2 and get_all_profit directly, avoiding the broken get_all_open_time.
        """
        now = time.time()
        if not force_refresh and self._cache and (now - self._last_scan_time < self._cache_ttl):
            return self._cache

        if not iq_client.is_connected or not iq_client.api:
            # Fallback mock pairs for offline mode filtered by min_payout
            demo_pairs = [
                {"pair": "DXY", "payout": 0.88, "type": "binary", "is_open": True},
                {"pair": "JXY", "payout": 0.88, "type": "binary", "is_open": True},
                {"pair": "EURUSD-OTC", "payout": 0.90, "type": "turbo", "is_open": True},
                {"pair": "EURUSD", "payout": 0.88, "type": "turbo", "is_open": True},
                {"pair": "GBPUSD", "payout": 0.88, "type": "turbo", "is_open": True},
            ]
            filtered = [p for p in demo_pairs if p["payout"] >= self.min_payout]
            self._cache = filtered if filtered else demo_pairs[:config.TOP_PAIRS_COUNT]
            self._last_scan_time = now
            return self._cache

        high_payout_list = []
        try:
            # 1. Fetch active instruments status using v2 (fast and reliable)
            init_v2 = iq_client.api.get_all_init_v2() or {}
            all_profit = iq_client.api.get_all_profit() or {}

            # Support both Turbo (1-5 min) and Binary (>= 15 min) options based on EXPIRY_MINUTES
            # When EXPIRY_MINUTES <= 5: scan Turbo category (which includes 5-minute expiry)
            # When EXPIRY_MINUTES > 5: scan Binary category
            target_category = "turbo" if config.EXPIRY_MINUTES <= 5 else "binary"
            category_keys = [target_category]

            seen_pairs = set()

            for cat in category_keys:
                actives = init_v2.get(cat, {}).get("actives", {}) if isinstance(init_v2, dict) else {}
                for act_id, act in actives.items():
                    if not isinstance(act, dict):
                        continue
                    raw_name = str(act.get("name", ""))
                    name = raw_name.replace("front.", "").strip()
                    is_open = (act.get("enabled") is True and not act.get("is_suspended", False))

                    # Register in OP_code
                    try:
                        import iqoptionapi.constants as OP_code
                        OP_code.ACTIVES[name] = int(act_id)
                    except Exception:
                        pass

                    profit_info = all_profit.get(name, {}) if isinstance(all_profit, dict) else {}
                    payout = profit_info.get(cat, 0.0) if isinstance(profit_info, dict) else 0.0

                    if is_open and payout >= self.min_payout and name not in seen_pairs:
                        seen_pairs.add(name)
                        high_payout_list.append({
                            "pair": name,
                            "payout": round(float(payout), 2),
                            "type": cat,
                            "is_open": True
                        })

            # Sort by highest payout descending
            high_payout_list.sort(key=lambda x: x["payout"], reverse=True)
            self._cache = high_payout_list
            self._last_scan_time = now
            logger.info(f"[Scanner] Found {len(high_payout_list)} open pairs with payout >= {self.min_payout:.0%}")
        except Exception as e:
            logger.error(f"[Scanner] Error scanning payouts: {e}")
            if not self._cache:
                self._cache = [
                    {"pair": "EURUSD", "payout": 0.87, "type": "turbo", "is_open": True},
                    {"pair": "GBPUSD", "payout": 0.85, "type": "turbo", "is_open": True},
                ]

        return self._cache

    def get_top_pairs(self, limit: int = None) -> List[Dict]:
        """Returns the top N pairs with the highest payout >= min_payout."""
        limit = limit or config.TOP_PAIRS_COUNT
        pairs = self.get_high_payout_pairs()
        return pairs[:limit]

    def get_best_pair(self) -> Optional[Dict]:
        """Returns the top pair with the highest payout."""
        pairs = self.get_top_pairs(1)
        return pairs[0] if pairs else None

scanner = AssetScanner()
