from __future__ import annotations
import dataclasses
import collections
from typing import List, Optional, Dict

@dataclasses.dataclass
class GameRules:
    deck_number: int = 3
    max_splits: int = 2
    dealer_hits_soft17: bool = False
    dealer_peeks: bool = True
    das: bool = True
    allow_double: bool = True
    allow_insurance: bool = False
    allow_surrender: bool = False
    burn_count: int = 5


@dataclasses.dataclass
class BettingSettings:
    bankroll: float = 1000.0
    unit_percent: float = 0.5
    min_bet: float = 100.0


@dataclasses.dataclass
class SessionStats:
    wins: int = 0
    losses: int = 0
    pushes: int = 0
    net_profit: float = 0.0
    history: List[Dict[str, float]] = dataclasses.field(default_factory=list)

    @property
    def total_games(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        total = self.total_games
        return (self.wins / total) if total > 0 else 0.0

    def reset(self) -> None:
        self.wins = 0
        self.losses = 0
        self.pushes = 0
        self.net_profit = 0.0
        self.history.clear()


@dataclasses.dataclass
class GameState:
    """Encapsulates the entire mutable state of the application."""
    rules: GameRules = dataclasses.field(default_factory=GameRules)
    betting: BettingSettings = dataclasses.field(default_factory=BettingSettings)
    stats: SessionStats = dataclasses.field(default_factory=SessionStats)
    
    cards_seen_counts: collections.Counter[int] = dataclasses.field(default_factory=collections.Counter)
    player_hands: List[List[int]] = dataclasses.field(default_factory=lambda: [[]])
    dealer_cards: List[int] = dataclasses.field(default_factory=list)
    active_hand_index: int = 0
    unseen_burned_count: int = 0
    
    # Transient state (not always saved/restored perfectly)
    round_bet_amount: Optional[float] = None
    last_bet_amount: float = 0.0
    round_doubled: bool = False
