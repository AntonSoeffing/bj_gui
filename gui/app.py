# -*- coding: utf-8 -*-
from __future__ import annotations

import collections
import dataclasses
import json
import re
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

# GUI Package Imports
from .state import GameState, GameRules, BettingSettings, SessionStats
from .theme import Theme
from .constants import STATE_FILE, CARD_LABELS, CARD_ICONS, CARD_VALUES, ACTION_LABELS
from .hand_utils import HandUtils
from .components.rules_frame import RulesFrame
from .components.seen_cards_frame import SeenCardsFrame
from .components.hands_frame import HandsFrame
from .components.results_frame import ResultsFrame
from .components.stats_frame import StatsFrame

# Logic Imports (Root level)
try:
    from betting_strategies import CardCountBetter
    from best_move import perfect_mover_cache
    from utils import DECK, get_hilo_running_count # Root utils
except ImportError:
    # If running as package without context, these might fail
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from betting_strategies import CardCountBetter
    from best_move import perfect_mover_cache
    from utils import DECK, get_hilo_running_count

class BlackjackSimulatorGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Blackjack Simulation GUI")
        self.root.geometry("980x760")
        
        self.state = GameState()
        self._load_state()
        self._apply_theme()
        
        self._build_main_ui()
        
        # Periodic auto-save or save on exit
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Button-2>", self.import_clipboard) # Middle click paste
        
        self.on_state_change() # Initial refresh

    def _build_main_ui(self):
        # Scrollable container
        canvas = tk.Canvas(self.root, bg=Theme.DARK_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=960) # Approx width
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Component frames
        pad = {'padx': 10, 'pady': 5}
        
        rf = ttk.LabelFrame(scroll_frame, text="Rules")
        rf.pack(fill="x", **pad)
        self.rules_ui = RulesFrame(rf, self)
        self.rules_ui.pack(fill="both", expand=True)
        
        scf = ttk.LabelFrame(scroll_frame, text="Seen Cards")
        scf.pack(fill="x", **pad)
        self.seen_ui = SeenCardsFrame(scf, self)
        self.seen_ui.pack(fill="both", expand=True)

        hf = ttk.LabelFrame(scroll_frame, text="Hands")
        hf.pack(fill="x", **pad)
        self.hands_ui = HandsFrame(hf, self)
        self.hands_ui.pack(fill="both", expand=True)

        # Actions
        af = ttk.Frame(scroll_frame)
        af.pack(fill="x", **pad)
        ttk.Button(af, text="Run Simulation", command=self.simulate).pack(side="left", padx=4)

        def _bind_result(btn: tk.Button, outcome: str, blackjack: bool = False):
            def handler(event=None, o=outcome, bj=blackjack):
                doubled = bool(event and (event.state & 0x0001))  # Shift held
                self.record_result(o, doubled=doubled, blackjack=bj)
            btn.bind("<Button-1>", handler)

        # Colored result buttons
        btn_frame = ttk.Frame(af)
        btn_frame.pack(side="left", padx=4)

        btn_bj = tk.Button(btn_frame, text="BJ", bg="#1f703d", fg="#e8f5ea",
                   activebackground="#2a8a4e", activeforeground="#e8f5ea", width=10)
        btn_win = tk.Button(btn_frame, text="Win", bg="#2e8b57", fg="#f7f7f7",
                    activebackground="#3fa76e", activeforeground="#ffffff", width=10)
        btn_push = tk.Button(btn_frame, text="Push", bg="#f6c945", fg="#1f1a00",
                     activebackground="#ffd75a", activeforeground="#1f1a00", width=10)
        btn_loss = tk.Button(btn_frame, text="Loss", bg="#e55353", fg="#ffffff",
                     activebackground="#f06b6b", activeforeground="#ffffff", width=10)

        btn_bj.grid(row=0, column=0, padx=(2, 10), pady=2)
        btn_win.grid(row=0, column=1, padx=2, pady=2)
        btn_push.grid(row=0, column=2, padx=2, pady=2)
        btn_loss.grid(row=0, column=3, padx=2, pady=2)

        _bind_result(btn_win, "win")
        _bind_result(btn_bj, "win", blackjack=True)
        _bind_result(btn_push, "push")
        _bind_result(btn_loss, "loss")

        ttk.Button(af, text="Reset All", command=self.confirm_clear_all).pack(side="right", padx=4)
        self.status_var = tk.StringVar()
        tk.Label(af, textvariable=self.status_var, fg="gray", bg=Theme.DARK_BG).pack(side="left", padx=10)

        resf = ttk.LabelFrame(scroll_frame, text="Results & Betting")
        resf.pack(fill="x", **pad)
        self.results_ui = ResultsFrame(resf, self)
        self.results_ui.pack(fill="both", expand=True)
        
        sf = ttk.LabelFrame(scroll_frame, text="Session Stats")
        sf.pack(fill="both", expand=True, **pad)
        self.stats_ui = StatsFrame(sf, self)
        self.stats_ui.pack(fill="both", expand=True)
        
        # Mousewheel
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    # --- THEME HELPERS ---
    def _apply_theme(self):
        self.root.configure(bg=Theme.DARK_BG)
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except: pass
        
        style.configure("TFrame", background=Theme.PANEL_BG)
        style.configure("TLabelframe", background=Theme.PANEL_BG, foreground=Theme.TEXT_COLOR)
        style.configure("TLabelframe.Label", background=Theme.PANEL_BG, foreground=Theme.TEXT_COLOR)
        style.configure("TLabel", background=Theme.PANEL_BG, foreground=Theme.TEXT_COLOR)
        style.configure("TButton", background=Theme.BUTTON_BG, foreground=Theme.TEXT_COLOR)
        style.map("TButton", background=[("active", Theme.BUTTON_ACTIVE_BG)])
        style.configure("TNotebook", background=Theme.PANEL_BG)
        style.configure("TCheckbutton", background=Theme.PANEL_BG, foreground=Theme.TEXT_COLOR)
        style.map("TCheckbutton", background=[("active", Theme.PANEL_BG)])
        
    def create_dark_button(self, parent, **kwargs):
        cnf = {
            "bg": Theme.BUTTON_BG, "fg": Theme.TEXT_COLOR,
            "activebackground": Theme.BUTTON_ACTIVE_BG, "activeforeground": Theme.TEXT_COLOR,
            "relief": tk.RAISED, "borderwidth": 1
        }
        cnf.update(kwargs)
        return tk.Button(parent, **cnf)
        
    def style_entry(self, widget: tk.Widget):
        widget.configure(bg=Theme.BUTTON_BG, fg=Theme.TEXT_COLOR, insertbackground=Theme.TEXT_COLOR,
                         highlightthickness=0, relief=tk.SOLID, borderwidth=1)
    
    def style_listbox(self, widget: tk.Listbox):
        widget.configure(bg=Theme.PANEL_BG, fg=Theme.TEXT_COLOR, selectbackground=Theme.ACCENT_COLOR,
                         highlightthickness=0, relief=tk.SOLID, borderwidth=1)

    # --- LOGIC ---
    
    def on_state_change(self):
        """Propagate state changes to all UI components."""
        # During early init, some frames may not be attached yet.
        if not all(hasattr(self, name) for name in ("rules_ui", "seen_ui", "hands_ui", "results_ui", "stats_ui")):
            return
        self.rules_ui.refresh()
        self.seen_ui.refresh()
        self.hands_ui.refresh()
        self.results_ui.refresh()
        self.calculate_betting_info()
        self.stats_ui.refresh()

    def get_card_face(self, val: int) -> str:
        return f"{CARD_ICONS.get(val, '')} {CARD_LABELS[val]}"

    def modify_seen_card(self, value: int, delta: int):
        current = self.state.cards_seen_counts[value]
        # Calculate max possible
        used_in_hands = sum(h.count(value) for h in self.state.player_hands) + self.state.dealer_cards.count(value)
        per_deck = 16 if value == 10 else 4
        capacity = self.state.rules.deck_number * per_deck
        max_seen = max(0, capacity - used_in_hands)
        
        new_val = max(0, min(current + delta, max_seen))
        if new_val != current:
            self.state.cards_seen_counts[value] = new_val
            self.on_state_change()

    def confirm_clear_seen_cards(self):
        if messagebox.askyesno("Confirm", "Clear all seen cards?"):
            self.state.cards_seen_counts.clear()
            self.state.unseen_burned_count = 0
            self.on_state_change()

    def burn_cards(self):
        # Burn logic
        self.on_state_change()

    def add_player_hand(self):
        # "Add Hand" behaves as a Split action if the current hand has cards
        # Otherwise, just adds a new empty hand for multi-hand play
        idx = self.state.active_hand_index
        if 0 <= idx < len(self.state.player_hands):
            hand = self.state.player_hands[idx]
            if len(hand) >= 2:
                # Split logic: Take last card, move to new hand inserted after current
                card = hand.pop()
                self.state.player_hands.insert(idx + 1, [card])
                self.state.round_bet_amount = None
                self.hands_ui.refresh()
                return

        # Fallback: Just add an empty hand
        self.state.player_hands.append([])
        self.hands_ui.refresh()

    def remove_player_hand(self):
        if len(self.state.player_hands) > 1:
            idx = self.state.active_hand_index
            self.state.player_hands.pop(idx)
            self.state.active_hand_index = max(0, min(idx, len(self.state.player_hands)-1))
            self.hands_ui.refresh()

    def modify_hand_card(self, target: str, value: int, delta: int):
        if delta > 0: # Add
            if target == "player":
                if 0 <= self.state.active_hand_index < len(self.state.player_hands):
                     self.state.player_hands[self.state.active_hand_index].append(value)
            else:
                self.state.dealer_cards.append(value)
        else: # Remove
            if target == "player":
                hand = self.state.player_hands[self.state.active_hand_index]
            else:
                hand = self.state.dealer_cards
            
            # Remove last instance
            for i in reversed(range(len(hand))):
                if hand[i] == value:
                    hand.pop(i)
                    break
        
        self.state.round_bet_amount = None # Clear locked bet if hand changes
        self.on_state_change()

    def remove_selected_card(self, target: str, hand_idx: int = None):
        if target == "dealer":
            sel = self.hands_ui.d_listbox.curselection()
            for i in reversed(sel):
                if i < len(self.state.dealer_cards):
                    self.state.dealer_cards.pop(i)
        elif target == "player" and hand_idx is not None:
             if hand_idx < len(self.hands_ui.listboxes):
                 sel = self.hands_ui.listboxes[hand_idx].curselection()
                 for i in reversed(sel):
                     if i < len(self.state.player_hands[hand_idx]):
                         self.state.player_hands[hand_idx].pop(i)
        
        self.on_state_change()

    def clear_hand(self, target: str, hand_idx: int = None):
        if target == "dealer":
            self.state.dealer_cards.clear()
        elif target == "player": # Specific hand
            if hand_idx is not None and 0 <= hand_idx < len(self.state.player_hands):
                self.state.player_hands[hand_idx].clear()
        self.on_state_change()

    def confirm_clear_all(self):
        if messagebox.askyesno("Reset", "Clear everything?"):
            self.state.player_hands = [[]]
            self.state.dealer_cards = []
            self.state.cards_seen_counts.clear()
            self.state.active_hand_index = 0
            self.state.round_bet_amount = None
            self.on_state_change()

    def calculate_betting_info(self):
        # Gather all cards
        seen_flat = []
        for v, c in self.state.cards_seen_counts.items():
            seen_flat.extend([v] * c)
        
        # Include current hands in calculation? Generally YES if they are on table
        for h in self.state.player_hands: seen_flat.extend(h)
        seen_flat.extend(self.state.dealer_cards)
        
        deck_n = max(1, self.state.rules.deck_number)
        running_cnt = get_hilo_running_count(seen_flat)
        
        total_cards = deck_n * 52
        cards_left = total_cards - len(seen_flat)
        phys_left = max(0, cards_left - self.state.unseen_burned_count)
        
        true_cnt = running_cnt / (cards_left / 52) if cards_left > 0 else 0
        
        # Bet Calculation
        bet_units = 0
        try:
            bet_units = CardCountBetter.get_bet(seen_flat, deck_n)
        except: pass

        # Clamp to table minimum when true count is very negative
        if true_cnt <= NEGATIVE_COUNT_THRESHOLD:
            bet_units = 0
        elif bet_units > 1 and phys_left < 20: # Low shoe logic check
            bet_units = max(1, bet_units // 2)

        # Money
        bank = self.state.betting.bankroll
        unit_val = bank * (self.state.betting.unit_percent / 100)
        rec_bet_amt = min(bank, bet_units * unit_val)
        min_bet = self.state.betting.min_bet
        
        if rec_bet_amt > 0 and rec_bet_amt < min_bet:
            rec_bet_amt = min(bank, min_bet)

        # Display
        self.state.last_bet_amount = rec_bet_amt
        
        txt_bet = f"Suggested: {bet_units} units (${rec_bet_amt:.2f})"
        if self.state.round_bet_amount is not None:
            txt_bet = f"Locked Bet: ${self.state.round_bet_amount:.2f}"
            
        self.results_ui.bet_var.set(txt_bet)
        self.results_ui.cnt_var.set(f"Run: {running_cnt} | True: {true_cnt:.2f} | Left: {phys_left}")

        # Copy bet to clipboard if not locked
        if self.state.round_bet_amount is None and rec_bet_amt > 0:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(f"$bj {int(rec_bet_amt)}")
            except: pass

    def simulate(self):
        if not any(self.state.player_hands) or not self.state.dealer_cards:
            self.status_var.set("Need cards to simulate.")
            return

        # Prepare shoe
        deck_cards = list(DECK) * self.state.rules.deck_number
        # Remove seen
        seen_flat = []
        for v, c in self.state.cards_seen_counts.items():
            seen_flat.extend([v] * c)
        for h in self.state.player_hands: seen_flat.extend(h)
        seen_flat.extend(self.state.dealer_cards)
        
        # Remove safely
        available_shoe = []
        counts = collections.Counter(deck_cards)
        seen_counts = collections.Counter(seen_flat)
        
        final_shoe = []
        for card in DECK: # Iterating types
            avail = counts[card] - seen_counts[card]
            if avail > 0:
                final_shoe.extend([card] * avail)
        
        final_shoe.sort()
        
        results = []
        dealer_up = self.state.dealer_cards[0]
        
        for i, hand in enumerate(self.state.player_hands):
            if not hand: continue
            try:
                profits = perfect_mover_cache(
                    cards=tuple(hand),
                    dealer_up_card=dealer_up,
                    cards_not_seen=tuple(final_shoe),
                    can_double=self.state.rules.allow_double,
                    can_insure=self.state.rules.allow_insurance,
                    can_surrender=self.state.rules.allow_surrender,
                    max_splits=self.state.rules.max_splits,
                    dealer_peeks_for_blackjack=self.state.rules.dealer_peeks,
                    das=self.state.rules.das,
                    dealer_stands_soft_17=not self.state.rules.dealer_hits_soft17,
                    return_all_profits=True
                )
                results.append((i, profits))
            except Exception as e:
                self.status_var.set(f"Sim Error: {e}")
                return

        # Display Logic
        if results:
            lines = []
            best_action_text = ""
            best_color = Theme.ACCENT_COLOR
            
            for idx, profits in results:
                # profits: stand, hit, double, split, surrender, insurance
                evs = dict(zip(ACTION_LABELS, profits[:5]))
                best_act = max(evs, key=evs.get)
                lines.append(f"H{idx+1}: {best_act} ({evs[best_act]:+.2f})")
                
                if idx == self.state.active_hand_index:
                    best_action_text = best_act
                    best_color = Theme.ACTION_COLORS.get(best_act, Theme.ACCENT_COLOR)

            self.results_ui.best_action_var.set(f"Best: {best_action_text} " + " | ".join(lines))
            self.results_ui.ba_label.configure(fg=best_color)
            
            # Detailed EV
            if results:
                p_idx, p_profits = results[0] # Show first hand
                ev_str = " | ".join([f"{k}: {v:+.2f}" for k, v in zip(ACTION_LABELS, p_profits)])
                self.results_ui.ev_var.set(ev_str)
                
                # Insurance
                if len(p_profits) > 5:
                    ins_ev = p_profits[5]
                    self.results_ui.ins_var.set(f"Insurance EV: {ins_ev:+.2f}")

    def record_result(self, outcome: str, doubled: bool = False, blackjack: bool = False):
        # If no hands, bail early
        if not self.state.player_hands:
            self.status_var.set("No hands to record.")
            return

        # 1. Lock current suggested bet if not set yet
        if self.state.round_bet_amount is None:
            self.state.round_bet_amount = self.state.last_bet_amount

        # Operate on active hand only
        idx = self.state.active_hand_index
        idx = max(0, min(idx, len(self.state.player_hands) - 1))
        hand = self.state.player_hands[idx]

        bet = self.state.round_bet_amount

        # Determine multiplier
        if blackjack:
            multiplier = 1.5
        elif outcome == "win":
            multiplier = 1
        elif outcome == "loss":
            multiplier = -1
        else:
            multiplier = 0

        # Double logic: either round_doubled or Shift+Click
        effective_doubled = (self.state.round_doubled or doubled) and not blackjack
        if effective_doubled:
            bet *= 2

        profit = bet * multiplier
        self.state.betting.bankroll += profit

        # 2. Update Stats
        s = self.state.stats
        if blackjack:
            s.wins += 1
        elif outcome == "win":
            s.wins += 1
        elif outcome == "loss":
            s.losses += 1
        else:
            s.pushes += 1

        s.net_profit += profit
        s.history.append({
            "game": s.total_games,
            "profit": s.net_profit,
            "win_rate": s.win_rate
        })

        # 3. Move only this hand's cards to seen counts
        for c in hand:
            self.state.cards_seen_counts[c] += 1

        # Remove this hand
        self.state.player_hands.pop(idx)

        # If no more player hands, clear dealer and reset round state
        if not self.state.player_hands:
            for c in self.state.dealer_cards:
                self.state.cards_seen_counts[c] += 1
            self.state.dealer_cards = []
            self.state.player_hands = [[]]
            self.state.round_bet_amount = None
            self.state.round_doubled = False
            self.state.active_hand_index = 0
        else:
            # Keep active index in bounds
            self.state.active_hand_index = max(0, min(idx, len(self.state.player_hands) - 1))

        label = "BJ" if blackjack else outcome
        self.status_var.set(f"Recorded {label} for hand {idx+1}. Profit: {profit:+.2f}")
        self.on_state_change()

    def reset_stats(self):
        if messagebox.askyesno("Reset", "Reset session stats?"):
            self.state.stats.reset()
            self.on_state_change()
            
    def import_clipboard(self, _):
        try:
            txt = self.root.clipboard_get()
            p_hands, d_cards = HandUtils.parse_clipboard_hands(txt)
            # Determine target hand index from clipboard label like "Hand 3"
            target_idx = None
            match = re.search(r"hand\s*(\d+)", txt, re.IGNORECASE)
            if match:
                target_idx = max(0, int(match.group(1)) - 1)

            if len(p_hands) > 1:
                # Clipboard has multiple hands: replace all
                self.state.player_hands = p_hands
                self.state.active_hand_index = 0
            else:
                # Single hand pasted
                if target_idx is not None:
                    # Ensure there are enough hands to receive the paste
                    while len(self.state.player_hands) <= target_idx:
                        self.state.player_hands.append([])
                    self.state.player_hands[target_idx] = p_hands[0]
                    self.state.active_hand_index = target_idx
                else:
                    # No explicit hand number in text: fallback behavior
                    if len(self.state.player_hands) > 1:
                        idx = self.state.active_hand_index
                        if 0 <= idx < len(self.state.player_hands):
                            self.state.player_hands[idx] = p_hands[0]
                    else:
                        self.state.player_hands = p_hands

            self.state.dealer_cards = d_cards
            self.on_state_change()
            self.status_var.set("Imported from clipboard!")
            self.simulate()
        except Exception as e:
            self.status_var.set(f"Paste failed: {e}")

    # --- PERSISTENCE ---
    def _load_state(self):
        if not STATE_FILE.exists(): return
        try:
            with open(STATE_FILE, "r") as f:
                d = json.load(f)
                
            # Naive hydration
            r = d.get("rules", {})
            self.state.rules = GameRules(**r)
            
            b = d.get("betting", {})
            self.state.betting = BettingSettings(**b)
            
            s = d.get("stats", {})
            self.state.stats = SessionStats(
                wins=s.get("wins",0), losses=s.get("losses",0),
                pushes=s.get("pushes",0), net_profit=s.get("net_profit", 0.0),
                history=s.get("history", [])
            )
            
            # Counts - ensure integer keys
            raw_counts = d.get("cards_seen_counts", {})
            self.state.cards_seen_counts = collections.Counter({int(k): v for k, v in raw_counts.items()})
            
            self.state.unseen_burned_count = d.get("unseen_burned_count", 0)
            
        except Exception as e:
            print(f"Failed to load state: {e}")

    def on_close(self):
        # Save state
        try:
            data = dataclasses.asdict(self.state)
            with open(STATE_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to save state: {e}")
        self.root.destroy()
