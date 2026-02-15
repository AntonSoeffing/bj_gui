from __future__ import annotations
import re
from typing import List, Optional, Tuple
from .constants import CARD_VALUES, CARD_CODE_PATTERN

class HandUtils:
    @staticmethod
    def calculate_value(cards: List[int]) -> int:
        total = sum(cards)
        aces = cards.count(11)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    @staticmethod
    def parse_card_code(code: str) -> Optional[int]:
        normalized = code.strip().upper()
        if not normalized:
            return None
        cleaned = normalized.replace(" ", "")
        
        # Strip suit if present
        if len(cleaned) > 1 and cleaned[-1] in "HDCS":
            rank = cleaned[:-1]
        else:
            rank = cleaned
            
        rank_map = {"A": 11, "K": 10, "Q": 10, "J": 10, "T": 10}
        
        if rank.isdigit():
            val = int(rank)
        else:
            val = rank_map.get(rank, 0)
            
        return val if val in CARD_VALUES else None

    @staticmethod
    def parse_clipboard_hands(text: str) -> Tuple[List[List[int]], List[int]]:
        lower = text.lower()
        dealer_idx = lower.find("dealer hand")
        if dealer_idx == -1:
            raise ValueError("Clipboard text must include 'Dealer Hand'.")
            
        player_part = text[:dealer_idx]
        dealer_part = text[dealer_idx:]
        
        # Extract player hands
        # Look for explicit "Hand X" markers
        matches = list(re.finditer(r"\bhand\s*\d+", player_part, re.IGNORECASE))
        player_hands_list = []
        
        if matches:
            for i, match in enumerate(matches):
                start = match.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(player_part)
                player_hands_list.append(HandUtils._extract_cards(player_part[start:end]))
        else:
            # Maybe just "Your Hand" or raw cards
            start_idx = lower.find("your hand")
            block = player_part[start_idx:] if start_idx != -1 else player_part
            player_hands_list.append(HandUtils._extract_cards(block))
            
        # Filter empty
        player_hands_list = [h for h in player_hands_list if h]
        if not player_hands_list:
            raise ValueError("Clipboard player hand has no cards.")
            
        dealer_cards = HandUtils._extract_cards(dealer_part)
        return player_hands_list, dealer_cards

    @staticmethod
    def _extract_cards(block: str) -> List[int]:
        cards = []
        for token in CARD_CODE_PATTERN.findall(block):
            if val := HandUtils.parse_card_code(token):
                cards.append(val)
        return cards
