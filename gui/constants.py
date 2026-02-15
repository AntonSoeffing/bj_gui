from typing import Tuple, Dict
import re
from pathlib import Path

# --- CONSTANTS & CONFIGURATION ---

CARD_VALUES: Tuple[int, ...] = tuple(range(2, 12))
CARD_LABELS: Dict[int, str] = {
    value: ("A" if value == 11 else str(value)) for value in CARD_VALUES
}
CARD_ICONS: Dict[int, str] = {
    2: "🂢", 3: "🂣", 4: "🂤", 5: "🂥", 6: "🂦",
    7: "🂧", 8: "🂨", 9: "🂩", 10: "🂪", 11: "🂡",
}
ACTION_LABELS: Tuple[str, ...] = ("Stand", "Hit", "Double", "Split", "Surrender")
CARD_CODE_PATTERN = re.compile(r":\s*((?:10|[2-9]|[TJQKA])[HDCS]?)\s*:", re.IGNORECASE)

NEGATIVE_COUNT_THRESHOLD = -0.5
STATS_HISTORY_LIMIT = 500
STATE_FILE = Path(__file__).parent.parent / "simulation_state.json"
