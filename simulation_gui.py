# -*- coding: utf-8 -*-
"""Interactive GUI for blackjack simulations."""

from __future__ import annotations

import json
import random
import re
import tkinter as tk
from collections import Counter
from pathlib import Path

from tkinter import messagebox, ttk
from typing import Dict, Iterable, List

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from betting_strategies import CardCountBetter
from best_move import perfect_mover_cache
from utils import DECK, get_hilo_running_count

CARD_VALUES: tuple[int, ...] = tuple(range(2, 12))
CARD_LABELS: Dict[int, str] = {value: ("A" if value == 11 else str(value)) for value in CARD_VALUES}
CARD_ICONS: Dict[int, str] = {
    2: "🂢",
    3: "🂣",
    4: "🂤",
    5: "🂥",
    6: "🂦",
    7: "🂧",
    8: "🂨",
    9: "🂩",
    10: "🂪",
    11: "🂡",
}
ACTION_LABELS: tuple[str, ...] = ("Stand", "Hit", "Double", "Split", "Surrender")
CARD_CODE_PATTERN = re.compile(r":\s*((?:10|[2-9]|[TJQKA])[HDCS]?)\s*:", re.IGNORECASE)
NEGATIVE_COUNT_THRESHOLD = -0.5
STATS_HISTORY_LIMIT = 500

DARK_BG = "#1e1e1e"
PANEL_BG = "#252526"
BUTTON_BG = "#3a3d41"
BUTTON_ACTIVE_BG = "#005a9e"
TEXT_COLOR = "#f3f3f3"
ACCENT_COLOR = "#0a84ff"
BEST_ACTION_BG = "#111a2c"
BEST_ACTION_BORDER = "#1f6feb"
INFO_PANEL_BG = "#1b2233"
ACTION_COLORS = {
    "Stand": "#4caf50",
    "Hit": "#3ea4ff",
    "Double": "#ff5c5c",
    "Split": "#f6c945",
    "Surrender": "#c2c8d3",
}
STATE_FILE = Path(__file__).with_name("simulation_state.json")


class BlackjackSimulatorGUI:
    """Tkinter GUI that orchestrates rule selection, card tracking, and simulations."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Blackjack Simulation GUI")
        self.root.geometry("980x720")
        self._apply_dark_theme()

        self.deck_number_var = tk.IntVar(value=3)
        self.max_splits_var = tk.IntVar(value=2)
        self.dealer_hits_soft17_var = tk.BooleanVar(value=False)
        self.dealer_peeks_var = tk.BooleanVar(value=True)
        self.das_var = tk.BooleanVar(value=True)
        self.allow_double_var = tk.BooleanVar(value=True)
        self.allow_insurance_var = tk.BooleanVar(value=False)
        self.allow_surrender_var = tk.BooleanVar(value=False)
        self.bankroll_var = tk.DoubleVar(value=1000.0)
        self.unit_percent_var = tk.DoubleVar(value=0.5)
        self.min_bet_var = tk.DoubleVar(value=100.0)

        self._state_path = STATE_FILE
        self._suspend_state = False

        self.cards_seen_counts: Dict[int, int] = {value: 0 for value in CARD_VALUES}
        self.card_buttons: Dict[int, tk.Button] = {}
        self.player_hand_buttons: Dict[int, tk.Button] = {}
        self.dealer_hand_buttons: Dict[int, tk.Button] = {}
        self.burn_count_var = tk.IntVar(value=5)

        self.player_hands: List[List[int]] = [[]]
        self.dealer_cards: List[int] = []

        self.active_hand_index = 0
        self.player_notebook: ttk.Notebook | None = None
        self.player_tab_frames: List[ttk.Frame] = []
        self.player_listboxes: List[tk.Listbox] = []
        self.dealer_listbox: tk.Listbox
        self.player_summary_var = tk.StringVar(value="Hand 1 total: 0 (cards: 0)")
        self.dealer_summary_var = tk.StringVar(value="Dealer total: 0")

        self.best_action_var = tk.StringVar(value="Best action: —")
        self.best_action_label: tk.Label | None = None
        self.ev_breakdown_var = tk.StringVar(value="Stand: –, Hit: –, Double: –, Split: –, Surrender: –")
        self.insurance_var = tk.StringVar(value="Insurance EV: –")
        self.bet_var = tk.StringVar(value="Suggested bet: 1 unit")
        self.counts_var = tk.StringVar(value="Running: +0 | True: +0.00 | Left: 0 (Phys: 0)")
        self.status_var = tk.StringVar(value="")
        self._last_bet_amount = 0.0
        self._round_bet_amount: float | None = None
        self.round_doubled_var = tk.BooleanVar(value=False)
        self._double_check_btn: ttk.Checkbutton | None = None
        self.unseen_burned_count = 0
        self.session_stats = self._default_stats()
        self.stats_summary_var = tk.StringVar(value="Games: 0 | Win rate: 0.0% | Net: $0.00")
        self._stats_fig: Figure | None = None
        self._stats_canvas: FigureCanvasTkAgg | None = None
        self._winrate_ax = None
        self._profit_ax = None
        self._stats_container: ttk.Frame | None = None
        self._stats_toggle_btn: ttk.Button | None = None
        self._content_canvas: tk.Canvas | None = None
        self._content_frame: ttk.Frame | None = None
        self._content_scrollbar: ttk.Scrollbar | None = None
        self._content_window_id: int | None = None

        self._build_scroll_container()

        self._load_state()
        self._build_layout()
        self.root.bind("<Button-2>", self._handle_middle_click)
        self._sync_ui_from_state()
        self._register_traces()
        self._update_betting_info()
        self._update_stats_summary()
        self._update_stats_plot()
        self._state_changed()

    def _build_layout(self) -> None:
        if not self._content_frame:
            return
        self._content_frame.columnconfigure(0, weight=1)

        self._build_rules_section()
        self._build_seen_cards_section()
        self._build_hand_section()
        self._build_actions_section()
        self._build_results_section()
        self._build_stats_section()
        self._content_frame.rowconfigure(5, weight=1)

    def _build_scroll_container(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        canvas = tk.Canvas(self.root, bg=DARK_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        content = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def on_content_configure(_: object) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        content.bind("<Configure>", on_content_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._content_canvas = canvas
        self._content_frame = content
        self._content_scrollbar = scrollbar
        self._content_window_id = window_id

    def _on_mousewheel(self, event: tk.Event) -> None:
        if not self._content_canvas:
            return
        if event.delta == 0:
            return
        self._content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _register_traces(self) -> None:
        self.deck_number_var.trace_add("write", self._handle_deck_change)
        self.max_splits_var.trace_add("write", self._handle_max_splits_change)
        self.bankroll_var.trace_add("write", self._handle_bankroll_change)
        self.unit_percent_var.trace_add("write", self._handle_unit_percent_change)
        self.min_bet_var.trace_add("write", self._handle_min_bet_change)

    def _build_rules_section(self) -> None:
        if not self._content_frame:
            return
        frame = ttk.LabelFrame(self._content_frame, text="Rules")
        frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        frame.columnconfigure(9, weight=1)

        ttk.Label(frame, text="Decks:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        deck_spin = tk.Spinbox(frame, from_=1, to=12, textvariable=self.deck_number_var, width=5)
        deck_spin.grid(row=0, column=1, padx=4, pady=4)
        self._style_entry(deck_spin)

        ttk.Label(frame, text="Max splits:").grid(row=0, column=2, sticky="w", padx=4, pady=4)
        splits_spin = tk.Spinbox(frame, from_=0, to=3, textvariable=self.max_splits_var, width=5)
        splits_spin.grid(row=0, column=3, padx=4, pady=4)
        self._style_entry(splits_spin)

        ttk.Checkbutton(frame, text="Dealer hits soft 17", variable=self.dealer_hits_soft17_var,
                command=self._on_rule_toggle).grid(row=0, column=4, padx=4, pady=4, sticky="w")
        ttk.Checkbutton(frame, text="Dealer peeks for blackjack", variable=self.dealer_peeks_var,
                command=self._on_rule_toggle).grid(row=0, column=5, padx=4, pady=4, sticky="w")
        ttk.Checkbutton(frame, text="Double after split (DAS)", variable=self.das_var,
                command=self._on_rule_toggle).grid(row=0, column=6, padx=4, pady=4, sticky="w")
        ttk.Checkbutton(frame, text="Allow double", variable=self.allow_double_var,
                command=self._on_rule_toggle).grid(row=1, column=0, padx=4, pady=4, sticky="w")
        ttk.Checkbutton(frame, text="Allow insurance", variable=self.allow_insurance_var,
                command=self._on_rule_toggle).grid(row=1, column=1, padx=4, pady=4, sticky="w")
        ttk.Checkbutton(frame, text="Allow surrender", variable=self.allow_surrender_var,
                command=self._on_rule_toggle).grid(row=1, column=2, padx=4, pady=4, sticky="w")

        ttk.Label(frame, text="Bankroll ($):").grid(row=2, column=0, sticky="w", padx=4, pady=(8, 4))
        bankroll_spin = tk.Spinbox(frame, from_=0, to=10_000_000, increment=50, textvariable=self.bankroll_var, width=10)
        bankroll_spin.grid(row=2, column=1, padx=4, pady=(8, 4))
        self._style_entry(bankroll_spin)

        ttk.Label(frame, text="Unit % per count unit:").grid(row=2, column=2, sticky="w", padx=4, pady=(8, 4))
        unit_spin = tk.Spinbox(frame, from_=0.1, to=20.0, increment=0.1, textvariable=self.unit_percent_var, width=10)
        unit_spin.grid(row=2, column=3, padx=4, pady=(8, 4))
        self._style_entry(unit_spin)

        ttk.Label(frame, text="Min Bet ($):").grid(row=2, column=4, sticky="w", padx=4, pady=(8, 4))
        min_bet_spin = tk.Spinbox(frame, from_=0, to=10000, increment=5, textvariable=self.min_bet_var, width=10)
        min_bet_spin.grid(row=2, column=5, padx=4, pady=(8, 4))
        self._style_entry(min_bet_spin)

    def _build_seen_cards_section(self) -> None:
        if not self._content_frame:
            return
        frame = ttk.LabelFrame(self._content_frame, text="Seen Cards")
        frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        frame.columnconfigure(tuple(range(11)), weight=1)

        info = ("Left click adds. Shift+Click or right click removes. Use the result buttons to log both hands automatically.")
        ttk.Label(frame, text=info, wraplength=600).grid(row=0, column=0, columnspan=11, pady=(0, 6), sticky="w")

        for idx, value in enumerate(CARD_VALUES):
            btn = self._create_dark_button(frame, text=self._seen_card_text(value), width=8)
            btn.grid(row=1, column=idx, padx=2, pady=2, sticky="ew")
            btn.bind("<Button-1>", lambda event, val=value: self._modify_seen_card(val, 1))
            btn.bind("<Shift-Button-1>", lambda event, val=value: self._modify_seen_card(val, -1))
            btn.bind("<Button-3>", lambda event, val=value: self._modify_seen_card(val, -1))
            self.card_buttons[value] = btn

        ttk.Button(frame, text="Clear Seen Cards", command=self._confirm_clear_seen_cards).grid(row=2, column=0,
                              columnspan=11, pady=(8, 0))

        burn_frame = ttk.Frame(frame)
        burn_frame.grid(row=3, column=0, columnspan=11, pady=(6, 0), sticky="ew")
        ttk.Label(burn_frame, text="Remove unknown cards:").grid(row=0, column=0, padx=4, sticky="w")
        burn_spin = tk.Spinbox(burn_frame, from_=1, to=312, textvariable=self.burn_count_var, width=6)
        burn_spin.grid(row=0, column=1, padx=4)
        self._style_entry(burn_spin)
        ttk.Button(burn_frame, text="Burn", command=self._confirm_burn_cards).grid(row=0, column=2, padx=4)
        burn_frame.columnconfigure(3, weight=1)

    def _build_hand_section(self) -> None:
        if not self._content_frame:
            return
        container = ttk.LabelFrame(self._content_frame, text="Hands")
        container.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        player_frame = ttk.Frame(container)
        player_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        player_frame.columnconfigure(0, weight=1)
        player_frame.rowconfigure(2, weight=1)
        ttk.Label(player_frame, textvariable=self.player_summary_var).grid(row=0, column=0, sticky="w")
        controls = ttk.Frame(player_frame)
        controls.grid(row=1, column=0, sticky="ew", pady=(2, 2))
        ttk.Button(controls, text="Add Hand", command=self._add_player_hand).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(controls, text="Remove Hand", command=self._remove_current_player_hand).grid(row=0, column=1)
        controls.columnconfigure(2, weight=1)
        self.player_notebook = ttk.Notebook(player_frame)
        self.player_notebook.grid(row=2, column=0, sticky="nsew", pady=4)
        self.player_notebook.bind("<<NotebookTabChanged>>", self._on_player_tab_changed)
        ttk.Label(player_frame, text="Left click a rank to add to the active hand. Shift/right click to remove.").grid(
            row=3, column=0, sticky="w", pady=(6, 0))
        player_buttons_frame = ttk.Frame(player_frame)
        player_buttons_frame.grid(row=4, column=0, sticky="ew")
        self.player_hand_buttons = self._build_hand_card_buttons(player_buttons_frame, "player")

        dealer_frame = ttk.Frame(container)
        dealer_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        dealer_frame.columnconfigure(0, weight=1)
        dealer_frame.rowconfigure(1, weight=1)
        ttk.Label(dealer_frame, textvariable=self.dealer_summary_var).grid(row=0, column=0, sticky="w")
        self.dealer_listbox = tk.Listbox(dealer_frame, height=6)
        self.dealer_listbox.grid(row=1, column=0, sticky="nsew", pady=4)
        self._style_listbox(self.dealer_listbox)
        ttk.Button(dealer_frame, text="Remove Selected", command=lambda: self._remove_selected_card("dealer")) \
            .grid(row=2, column=0, pady=2, sticky="ew")
        ttk.Button(dealer_frame, text="Clear Dealer", command=lambda: self._clear_hand("dealer")) \
            .grid(row=3, column=0, pady=2, sticky="ew")
        ttk.Label(dealer_frame, text="Left click to add, Shift/right click to remove. First dealer card is the up card.").grid(
            row=4, column=0, sticky="w", pady=(6, 0))
        dealer_buttons_frame = ttk.Frame(dealer_frame)
        dealer_buttons_frame.grid(row=5, column=0, sticky="ew")
        self.dealer_hand_buttons = self._build_hand_card_buttons(dealer_buttons_frame, "dealer")
        self._rebuild_player_tabs()

    def _rebuild_player_tabs(self) -> None:
        if not self.player_notebook:
            return
        if not self.player_hands:
            self.player_hands = [[]]
        for frame in self.player_tab_frames:
            self.player_notebook.forget(frame)
            frame.destroy()
        self.player_tab_frames = []
        self.player_listboxes = []
        for idx in range(len(self.player_hands)):
            self._create_player_hand_tab(idx)
        self.active_hand_index = min(self.active_hand_index, len(self.player_hands) - 1)
        if self.player_tab_frames:
            self.player_notebook.select(self.player_tab_frames[self.active_hand_index])
        self._update_hand_summaries()

    def _create_player_hand_tab(self, index: int) -> None:
        if not self.player_notebook:
            return
        frame = ttk.Frame(self.player_notebook)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        listbox = tk.Listbox(frame, height=6)
        listbox.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        self._style_listbox(listbox)
        remove_btn = ttk.Button(frame, text="Remove Selected",
                                command=lambda idx=index: self._remove_selected_card("player", idx))
        remove_btn.grid(row=1, column=0, sticky="ew", pady=2)
        clear_btn = ttk.Button(frame, text="Clear Hand",
                               command=lambda idx=index: self._clear_hand("player", idx))
        clear_btn.grid(row=2, column=0, sticky="ew", pady=2)
        self.player_notebook.add(frame, text=f"Hand {index + 1}")
        self.player_tab_frames.append(frame)
        self.player_listboxes.append(listbox)
        self._refresh_listbox(listbox, self.player_hands[index])

    def _on_player_tab_changed(self, _: object) -> None:
        if not self.player_notebook:
            return
        self.active_hand_index = self.player_notebook.index("current")
        self._refresh_hand_buttons("player")
        self._update_hand_summaries()

    def _add_player_hand(self) -> None:
        split_index = self._resolve_hand_index(self.active_hand_index)
        split_hand = self.player_hands[split_index]
        if len(split_hand) == 2 and split_hand[0] == split_hand[1]:
            split_card = split_hand.pop()
            self.player_hands.append([split_card])
            # Keep focus on the original hand after splitting
            self._rebuild_player_tabs()
            self._update_betting_info()
            self._state_changed()
            self._set_status(f"Split Hand {split_index + 1}.")
            return
        self.player_hands.append([])
        # Keep focus on the current hand when adding a new empty hand
        self._rebuild_player_tabs()
        self._update_betting_info()
        self._state_changed()

    def _remove_current_player_hand(self) -> None:
        if len(self.player_hands) <= 1:
            self._set_status("At least one player hand is required.")
            return
        removed_idx = self.active_hand_index
        self.player_hands.pop(removed_idx)
        self.active_hand_index = min(removed_idx, len(self.player_hands) - 1)
        self._rebuild_player_tabs()
        self._update_betting_info()
        self._state_changed()
        self._set_status(f"Removed Hand {removed_idx + 1}.")

    def _build_actions_section(self) -> None:
        if not self._content_frame:
            return
        frame = ttk.Frame(self._content_frame)
        frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        frame.columnconfigure(4, weight=1)
        ttk.Button(frame, text="Run Simulation", command=self._simulate).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(frame, text="Game Ended (Push)", command=lambda: self._record_game_result("push")) \
            .grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(frame, text="Game Won", command=lambda: self._record_game_result("win")) \
            .grid(row=0, column=2, padx=4, pady=4)
        ttk.Button(frame, text="Game Lost", command=lambda: self._record_game_result("loss")) \
            .grid(row=0, column=3, padx=4, pady=4)
        ttk.Button(frame, text="Clear Everything", command=self._confirm_clear_everything) \
            .grid(row=0, column=4, padx=4, pady=4, sticky="w")
        ttk.Label(frame, textvariable=self.status_var, foreground="gray").grid(row=1, column=0, columnspan=5, sticky="w")

    def _build_results_section(self) -> None:
        if not self._content_frame:
            return
        frame = ttk.LabelFrame(self._content_frame, text="Results & Betting")
        frame.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        frame.columnconfigure(0, weight=1)
        best_frame = tk.Frame(frame, bg=BEST_ACTION_BG, highlightbackground=BEST_ACTION_BORDER,
                              highlightcolor=BEST_ACTION_BORDER, highlightthickness=1, bd=0)
        best_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        best_frame.columnconfigure(0, weight=1)
        self.best_action_label = tk.Label(
            best_frame,
            textvariable=self.best_action_var,
            font=("Segoe UI", 18, "bold"),
            bg=BEST_ACTION_BG,
            fg=ACCENT_COLOR,
            anchor="w",
            justify="left",
            wraplength=620,
            padx=8,
            pady=8,
        )
        self.best_action_label.grid(row=0, column=0, sticky="ew")
        self._set_best_action_display(self.best_action_var.get())

        info_frame = tk.Frame(frame, bg=INFO_PANEL_BG, bd=0, padx=8, pady=6)
        info_frame.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        info_frame.columnconfigure(0, weight=1)
        info_labels = (
            (self.ev_breakdown_var, "left"),
            (self.insurance_var, "left"),
            (self.bet_var, "left"),
            (self.counts_var, "left"),
        )
        for idx, (var, justify) in enumerate(info_labels):
            tk.Label(
                info_frame,
                textvariable=var,
                bg=INFO_PANEL_BG,
                fg=TEXT_COLOR,
                anchor="w",
                justify=justify,
                wraplength=640,
            ).grid(row=idx, column=0, sticky="ew", pady=2)

        self._build_round_multiplier_controls(frame)

    def _set_best_action_display(self, text: str, primary_action: str | None = None) -> None:
        self.best_action_var.set(text)
        if not self.best_action_label:
            return
        color = ACTION_COLORS.get(primary_action or "", ACCENT_COLOR)
        self.best_action_label.configure(fg=color)

    def _build_stats_section(self) -> None:
        if not self._content_frame:
            return
        frame = ttk.LabelFrame(self._content_frame, text="Session Tracking")
        frame.grid(row=5, column=0, padx=10, pady=(0, 10), sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)
        header = ttk.Frame(frame)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, textvariable=self.stats_summary_var).grid(row=0, column=0, sticky="w")
        self._stats_toggle_btn = ttk.Button(header, text="Hide", command=self._toggle_stats_section)
        self._stats_toggle_btn.grid(row=0, column=1, sticky="e", padx=(0, 4))
        ttk.Button(header, text="Reset Stats", command=self._confirm_reset_stats).grid(row=0, column=2, sticky="e", padx=4)
        self._stats_fig = Figure(figsize=(6.5, 3.5), dpi=100)
        self._stats_fig.patch.set_facecolor(PANEL_BG)
        self._winrate_ax = self._stats_fig.add_subplot(211)
        self._profit_ax = self._stats_fig.add_subplot(212)
        self._style_stats_axis(self._winrate_ax, "Win %")
        self._style_stats_axis(self._profit_ax, "Net $", xlabel="Games logged")
        self._stats_container = ttk.Frame(frame)
        self._stats_container.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        self._stats_container.columnconfigure(0, weight=1)
        self._stats_container.rowconfigure(0, weight=1)
        self._stats_canvas = FigureCanvasTkAgg(self._stats_fig, master=self._stats_container)
        canvas_widget = self._stats_canvas.get_tk_widget()
        canvas_widget.configure(bg=PANEL_BG)
        canvas_widget.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(1, weight=1)

    def _toggle_stats_section(self) -> None:
        if not self._stats_container or not self._stats_toggle_btn:
            return
        if self._stats_container.winfo_ismapped():
            self._stats_container.grid_remove()
            self._stats_toggle_btn.configure(text="Show")
        else:
            self._stats_container.grid()
            self._stats_toggle_btn.configure(text="Hide")

    def _build_round_multiplier_controls(self, parent: ttk.LabelFrame) -> None:
        container = ttk.LabelFrame(parent, text="Round Adjustment")
        container.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        container.columnconfigure(0, weight=1)
        double_text = "Double down (adds +1 unit)"
        self._double_check_btn = ttk.Checkbutton(
            container,
            text=double_text,
            variable=self.round_doubled_var,
        )
        self._double_check_btn.grid(row=0, column=0, sticky="w", pady=(2, 2))
        ttk.Label(
            container,
            text="Disabled automatically when multiple hands are in play.",
            foreground="gray",
        ).grid(row=1, column=0, sticky="w")
        self._sync_double_option()

    def _sync_double_option(self) -> None:
        multiple_hands = self._active_hand_count() > 1
        if multiple_hands and self.round_doubled_var.get():
            self.round_doubled_var.set(False)
        if self._double_check_btn:
            if multiple_hands:
                self._double_check_btn.state(["disabled"])
            else:
                self._double_check_btn.state(["!disabled"])

    def _reset_round_multipliers(self) -> None:
        self.round_doubled_var.set(False)
        self._sync_double_option()

    def _handle_middle_click(self, _: object) -> None:
        self._import_hands_from_clipboard()

    def _import_hands_from_clipboard(self) -> None:
        try:
            clipboard_text = self.root.clipboard_get()
        except tk.TclError:
            self._set_status("Clipboard unavailable.")
            return
        if not clipboard_text.strip():
            self._set_status("Clipboard is empty.")
            return
        try:
            player_hands, dealer_cards = self._parse_clipboard_hands(clipboard_text)
            self._validate_import_capacity(player_hands, dealer_cards)
        except ValueError as exc:
            self._set_status(str(exc))
            return
        if not any(player_hands):
            self._set_status("Clipboard player hand has no cards.")
            return
        if not dealer_cards:
            self._set_status("Clipboard dealer hand has no cards.")
            return
        self.player_hands = [hand[:] for hand in player_hands] or [[]]
        self.active_hand_index = 0
        self.dealer_cards = dealer_cards
        self._rebuild_player_tabs()
        self._refresh_listbox(self.dealer_listbox, self.dealer_cards)
        self._refresh_hand_buttons("player")
        self._refresh_hand_buttons("dealer")
        self._update_hand_summaries()
        self._update_betting_info()
        self._state_changed()
        self._set_status("Hands imported from clipboard.")

        # If the pasted text contains a result line, the hand is likely over; don't auto-simulate.
        if "result:" not in clipboard_text.lower():
            self.root.after_idle(self._simulate)

    def _parse_clipboard_hands(self, text: str) -> tuple[List[List[int]], List[int]]:
        lower = text.lower()
        dealer_idx = lower.find("dealer hand")
        if dealer_idx == -1:
            raise ValueError("Clipboard text must include 'Dealer Hand'.")
        player_block = text[:dealer_idx]
        dealer_block = text[dealer_idx:]
        player_blocks = self._extract_player_blocks(player_block)
        player_hands = [self._extract_cards_from_block(block) for block in player_blocks]
        player_hands = [hand for hand in player_hands if hand]
        if not player_hands:
            raise ValueError("Clipboard player hand has no cards.")
        return player_hands, self._extract_cards_from_block(dealer_block)

    def _extract_player_blocks(self, text: str) -> List[str]:
        matches = list(re.finditer(r"\bhand\s*\d+", text, re.IGNORECASE))
        if matches:
            blocks: List[str] = []
            for idx, match in enumerate(matches):
                start = match.end()
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
                blocks.append(text[start:end])
            return blocks
        lower = text.lower()
        player_idx = lower.find("your hand")
        if player_idx != -1:
            return [text[player_idx:]]
        return [text]

    def _extract_cards_from_block(self, block: str) -> List[int]:
        cards: List[int] = []
        for token in CARD_CODE_PATTERN.findall(block):
            token = token.strip()
            if not token:
                continue
            value = self._card_value_from_code(token)
            if value is not None:
                cards.append(value)
        return cards

    def _card_value_from_code(self, code: str) -> int | None:
        normalized = code.strip().upper()
        if not normalized:
            return None
        cleaned = normalized.replace(" ", "")
        if len(cleaned) > 1 and cleaned[-1] in "HDCS":
            rank = cleaned[:-1]
        else:
            rank = cleaned
        rank_map = {"A": 11, "K": 10, "Q": 10, "J": 10, "T": 10}
        if rank.isdigit():
            value = int(rank)
        else:
            value = rank_map.get(rank)
        if value not in CARD_VALUES:
            return None
        return value

    def _validate_import_capacity(self, player_hands: List[List[int]], dealer_cards: List[int]) -> None:
        combined: Counter[int] = Counter()
        for hand in player_hands:
            combined.update(hand)
        combined.update(dealer_cards)
        for value, amount in combined.items():
            capacity = self._total_card_capacity(value)
            manual = self.cards_seen_counts[value]
            if manual + amount > capacity:
                label = CARD_LABELS[value]
                raise ValueError(f"Not enough {label} cards remaining for clipboard import.")

    def _seen_card_text(self, value: int) -> str:
        return f"{self._card_face(value)}\n({self.cards_seen_counts[value]})"

    def _modify_seen_card(self, value: int, delta: int) -> None:
        max_manual = self._max_manual_seen_count(value)
        new_value = self.cards_seen_counts[value] + delta
        if new_value < 0:
            new_value = 0
        elif new_value > max_manual:
            new_value = max_manual
        if new_value == self.cards_seen_counts[value] and delta > 0 and max_manual == self.cards_seen_counts[value]:
            self._set_status(f"No {CARD_LABELS[value]} cards left to mark as seen.")
            return
        self.cards_seen_counts[value] = new_value
        self._update_seen_card_button(value)
        self._update_betting_info()
        self._state_changed()

    def _max_manual_seen_count(self, value: int) -> int:
        capacity = self._total_card_capacity(value)
        used_in_hands = self._all_player_cards().count(value) + self.dealer_cards.count(value)
        return max(capacity - used_in_hands, 0)

    def _total_card_capacity(self, value: int) -> int:
        per_deck = 16 if value == 10 else 4
        return self.deck_number_var.get() * per_deck

    def _update_seen_card_button(self, value: int) -> None:
        self.card_buttons[value].configure(text=self._seen_card_text(value))

    def _clear_seen_cards(self) -> None:
        for value in CARD_VALUES:
            self.cards_seen_counts[value] = 0
            self._update_seen_card_button(value)
        self.unseen_burned_count = 0
        self._update_betting_info()
        self._state_changed()

    def _burn_unknown_cards(self) -> None:
        count = max(self.burn_count_var.get(), 0)
        if count <= 0:
            self._set_status("Enter how many cards to remove.")
            return
        cards_seen = self._get_total_seen_cards(include_hands=True)
        deck_number = max(self.deck_number_var.get(), 1)
        cards_left = deck_number * 52 - len(cards_seen)
        physical_left = max(cards_left - self.unseen_burned_count, 0)
        if physical_left == 0:
            self._set_status("No cards left to remove.")
            return
        if count > physical_left:
            messagebox.showerror("Invalid burn", f"Only {physical_left} cards remain in the shoe.")
            return
        self.unseen_burned_count += count
        self._update_betting_info()
        self._set_status(f"Burned {count} unseen card(s).")
        self._state_changed()

    def _resolve_hand_index(self, hand_index: int | None) -> int:
        if not self.player_hands:
            self.player_hands = [[]]
        if hand_index is not None and 0 <= hand_index < len(self.player_hands):
            return hand_index
        return min(self.active_hand_index, len(self.player_hands) - 1)

    def _current_player_hand(self) -> List[int]:
        idx = self._resolve_hand_index(self.active_hand_index)
        return self.player_hands[idx]

    def _all_player_cards(self) -> List[int]:
        return [card for hand in self.player_hands for card in hand]

    def _active_player_hands(self) -> List[tuple[int, List[int]]]:
        return [(idx, hand) for idx, hand in enumerate(self.player_hands) if hand]

    def _active_hand_count(self) -> int:
        return len(self._active_player_hands())

    def _refresh_player_listbox(self, hand_index: int) -> None:
        if 0 <= hand_index < len(self.player_listboxes):
            self._refresh_listbox(self.player_listboxes[hand_index], self.player_hands[hand_index])

    def _modify_hand_card(self, target: str, value: int, delta: int, hand_index: int | None = None) -> None:
        if delta > 0:
            self._add_card_to_hand(target, value, hand_index)
        else:
            self._remove_card_by_value(target, value, hand_index)

    def _add_card_to_hand(self, target: str, value: int, hand_index: int | None = None) -> None:
        round_was_empty = not self._round_in_progress()
        capacity = self._total_card_capacity(value)
        manual_seen = self.cards_seen_counts[value]
        hand_count = self._all_player_cards().count(value) + self.dealer_cards.count(value)
        if manual_seen + hand_count >= capacity:
            self._set_status(f"All {CARD_LABELS[value]} cards already accounted for.")
            return
        if round_was_empty:
            self._maybe_lock_round_bet()
        if target == "player":
            idx = self._resolve_hand_index(hand_index)
            self.player_hands[idx].append(value)
            self._refresh_player_listbox(idx)
            if idx == self.active_hand_index:
                self._update_hand_button("player", value)
            self._update_player_summary(idx)
        else:
            self.dealer_cards.append(value)
            self._refresh_listbox(self.dealer_listbox, self.dealer_cards)
            self._update_hand_button("dealer", value)
            self._update_dealer_summary()
        self._update_betting_info()
        self._state_changed()

    def _remove_card_by_value(self, target: str, value: int, hand_index: int | None = None) -> None:
        if target == "player":
            idx = self._resolve_hand_index(hand_index)
            cards = self.player_hands[idx]
            listbox = self.player_listboxes[idx] if idx < len(self.player_listboxes) else None
        else:
            cards = self.dealer_cards
            listbox = self.dealer_listbox
        for pos in range(len(cards) - 1, -1, -1):
            if cards[pos] == value:
                cards.pop(pos)
                if listbox is not None:
                    self._refresh_listbox(listbox, cards)
                self._update_hand_button(target, value)
                if target == "player":
                    self._update_player_summary(idx)
                else:
                    self._update_dealer_summary()
                self._clear_round_bet_if_idle()
                self._update_betting_info()
                self._state_changed()
                return
        self._set_status(f"No {CARD_LABELS[value]} cards to remove from {target} hand.")

    def _remove_selected_card(self, target: str, hand_index: int | None = None) -> None:
        if target == "player":
            idx = self._resolve_hand_index(hand_index)
            if idx >= len(self.player_listboxes):
                return
            listbox = self.player_listboxes[idx]
            cards = self.player_hands[idx]
        else:
            listbox = self.dealer_listbox
            cards = self.dealer_cards
            idx = None
        selection = listbox.curselection()
        if not selection:
            return
        changed = False
        for index in reversed(selection):
            if 0 <= index < len(cards):
                cards.pop(index)
                changed = True
        self._refresh_listbox(listbox, cards)
        self._refresh_hand_buttons(target)
        if target == "player" and idx is not None:
            self._update_player_summary(idx)
        else:
            self._update_dealer_summary()
        self._clear_round_bet_if_idle()
        self._update_betting_info()
        if changed:
            self._state_changed()

    def _clear_hand(self, target: str, hand_index: int | None = None) -> None:
        if target == "player":
            if hand_index is None:
                self.player_hands = [[]]
                self.active_hand_index = 0
                self._rebuild_player_tabs()
            else:
                idx = self._resolve_hand_index(hand_index)
                self.player_hands[idx].clear()
                self._refresh_player_listbox(idx)
            self._refresh_hand_buttons("player")
        else:
            self.dealer_cards.clear()
            self._refresh_listbox(self.dealer_listbox, self.dealer_cards)
            self._refresh_hand_buttons("dealer")
        self._update_hand_summaries()
        self._clear_round_bet_if_idle()
        self._update_betting_info()
        self._state_changed()

    def _refresh_listbox(self, listbox: tk.Listbox, cards: List[int]) -> None:
        listbox.delete(0, tk.END)
        for card in cards:
            listbox.insert(tk.END, CARD_LABELS[card])

    def _update_hand_summaries(self) -> None:
        for idx in range(len(self.player_hands)):
            self._update_player_summary(idx)
        self._update_dealer_summary()
        self._sync_double_option()

    def _update_player_summary(self, hand_index: int) -> None:
        if not self.player_hands:
            return
        if hand_index >= len(self.player_hands):
            return
        cards = self.player_hands[hand_index]
        total = self._hand_value(cards)
        label = f"Hand {hand_index + 1} total: {total} (cards: {len(cards)})"
        if hand_index == self.active_hand_index:
            self.player_summary_var.set(label)
        if self.player_notebook and hand_index < len(self.player_tab_frames):
            tab_label = f"Hand {hand_index + 1}"
            if cards:
                tab_label += f" ({total})"
            self.player_notebook.tab(self.player_tab_frames[hand_index], text=tab_label)

    def _update_dealer_summary(self) -> None:
        dealer_total = self._hand_value(self.dealer_cards)
        self.dealer_summary_var.set(f"Dealer total: {dealer_total} (cards: {len(self.dealer_cards)})")

    def _hand_value(self, cards: List[int]) -> int:
        total = sum(cards)
        aces = cards.count(11)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def _clear_all(self) -> None:
        self._clear_hand("player")
        self._clear_hand("dealer")
        self._clear_seen_cards()
        self._set_best_action_display("Best action: —")
        self.ev_breakdown_var.set("Stand: –, Hit: –, Double: –, Split: –, Surrender: –")
        self.insurance_var.set("Insurance EV: –")
        self.status_var.set("")
        self._round_bet_amount = None
        self._reset_round_multipliers()

    def _record_game_result(self, outcome: str) -> None:
        if not (self._all_player_cards() or self.dealer_cards):
            self._set_status("Nothing to record. Add cards first.")
            return
        hand_outcomes = self._collect_hand_outcomes(outcome)
        if hand_outcomes is None:
            self._set_status("Result entry cancelled.")
            return
        bet_amount = self._current_round_bet()
        profit_delta = self._calculate_profit_delta(bet_amount, hand_outcomes)
        units_wagered = self._units_wagered(hand_outcomes)
        if not self._log_current_hands_as_seen():
            return
        outcome = outcome.lower()
        counted_outcome = outcome in {"win", "loss"}
        if outcome == "win":
            self.session_stats["wins"] += 1
            self._apply_bankroll_delta(profit_delta)
            status = "Logged win"
        elif outcome == "loss":
            self.session_stats["losses"] += 1
            self._apply_bankroll_delta(profit_delta)
            status = "Logged loss"
        else:
            self.session_stats["pushes"] += 1
            status = "Logged neutral result (not counted in stats)"
        self.session_stats["net_profit"] += profit_delta
        if counted_outcome:
            self._append_history_entry()
        self._update_stats_summary()
        self._update_stats_plot()
        amount_note = ""
        if outcome in {"win", "loss"} and units_wagered > 0:
            per_unit = self._format_currency(bet_amount)
            amount_note = f" using {units_wagered} unit{'s' if units_wagered != 1 else ''} at {per_unit} each"
        change_note = ""
        if profit_delta != 0:
            sign = "+" if profit_delta > 0 else "-"
            change_note = f" ({sign}{self._format_currency(abs(profit_delta))} impact)"
        self._round_bet_amount = None
        self._update_betting_info()
        self._copy_next_bet_command()
        self._reset_round_multipliers()
        self._set_status(f"{status}.{change_note}{amount_note} Hands recorded as seen cards.")
        self._state_changed()

    def _collect_hand_outcomes(self, default_outcome: str) -> List[str] | None:
        active_hands = self._active_player_hands()
        if not active_hands:
            return []
        default_outcome = default_outcome.lower()
        if len(active_hands) == 1 or default_outcome not in {"win", "loss"}:
            return [default_outcome]

        dialog = tk.Toplevel(self.root)
        dialog.title("Resolve Hands")
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog, text="Select the result for each hand:").grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 4), sticky="w")
        outcome_vars: List[tk.StringVar] = []
        for row, (hand_idx, hand_cards) in enumerate(active_hands, start=1):
            label = f"Hand {hand_idx + 1}: total {self._hand_value(hand_cards)}"
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=2)
            var = tk.StringVar(value=default_outcome)
            outcome_vars.append(var)
            for col, choice in enumerate(("win", "loss", "push"), start=1):
                ttk.Radiobutton(dialog, text=choice.title(), value=choice, variable=var).grid(row=row, column=col, padx=5, pady=2)

        action_frame = ttk.Frame(dialog)
        action_frame.grid(row=len(active_hands) + 1, column=0, columnspan=3, pady=(10, 10))
        dialog_result: dict[str, List[str] | None] = {"values": None}

        def confirm() -> None:
            dialog_result["values"] = [var.get() for var in outcome_vars]
            dialog.destroy()

        def cancel() -> None:
            dialog.destroy()

        ttk.Button(action_frame, text="Cancel", command=cancel).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(action_frame, text="Confirm", command=confirm).grid(row=0, column=1)
        dialog.wait_window()
        return dialog_result["values"]

    def _calculate_profit_delta(self, bet_amount: float, hand_outcomes: List[str]) -> float:
        if not hand_outcomes:
            return 0.0
        total_units = 0
        for result in hand_outcomes:
            result = result.lower()
            if result == "win":
                total_units += 1
            elif result == "loss":
                total_units -= 1
        if len(hand_outcomes) == 1 and self.round_doubled_var.get():
            total_units *= 2
        return bet_amount * total_units

    def _units_wagered(self, hand_outcomes: List[str]) -> int:
        if not hand_outcomes:
            return 0
        if len(hand_outcomes) == 1 and self.round_doubled_var.get():
            return 2
        return len(hand_outcomes)

    def _log_current_hands_as_seen(self) -> bool:
        all_player_cards = self._all_player_cards()
        if not all_player_cards and not self.dealer_cards:
            self._set_status("Nothing to record. Add cards first.")
            return False
        moved_cards = all_player_cards + self.dealer_cards
        for card in moved_cards:
            self.cards_seen_counts[card] += 1
            self._update_seen_card_button(card)
        self._clear_hand("player")
        self._clear_hand("dealer")
        self._clear_round_bet_if_idle()
        self._reset_round_multipliers()
        return True

    def _simulate(self) -> None:
        active_indices = [idx for idx, hand in enumerate(self.player_hands) if hand]
        if not active_indices:
            messagebox.showerror("Missing data", "Add at least one player card before simulating.")
            return
        if not self.dealer_cards:
            messagebox.showerror("Missing data", "Add at least one dealer card (the up card).")
            return
        try:
            cards_not_seen = self._build_cards_not_seen()
        except ValueError as exc:
            messagebox.showerror("Invalid shoe", str(exc))
            return
        dealer_up_card = self.dealer_cards[0]
        hand_results: List[tuple[int, List[int], tuple[float, ...]]] = []
        for idx in active_indices:
            hand = self.player_hands[idx]
            try:
                profits = perfect_mover_cache(
                    cards=tuple(hand),
                    dealer_up_card=dealer_up_card,
                    cards_not_seen=cards_not_seen,
                    can_double=self.allow_double_var.get(),
                    can_insure=self.allow_insurance_var.get(),
                    can_surrender=self.allow_surrender_var.get(),
                    max_splits=self.max_splits_var.get(),
                    dealer_peeks_for_blackjack=self.dealer_peeks_var.get(),
                    das=self.das_var.get(),
                    dealer_stands_soft_17=not self.dealer_hits_soft17_var.get(),
                    return_all_profits=True,
                )
            except Exception as exc:  # pragma: no cover - safeguard for unexpected runtime issues
                messagebox.showerror("Simulation error", str(exc))
                return
            hand_results.append((idx, list(hand), profits))
        self._display_results(hand_results)

    def _build_cards_not_seen(self) -> tuple[int, ...]:
        deck_number = self.deck_number_var.get()
        if deck_number <= 0:
            raise ValueError("Deck number must be at least 1.")
        shoe = list(DECK) * deck_number
        total_seen = self._get_total_seen_cards(include_hands=True)
        for card in total_seen:
            try:
                shoe.remove(card)
            except ValueError as exc:
                label = CARD_LABELS[card]
                raise ValueError(f"Too many {label}s have been entered for {deck_number} deck(s).") from exc
        return tuple(sorted(shoe))

    def _get_total_seen_cards(self, include_hands: bool) -> List[int]:
        cards: List[int] = []
        for value, count in self.cards_seen_counts.items():
            cards.extend([value] * count)
        if include_hands:
            for hand in self.player_hands:
                cards.extend(hand)
            cards.extend(self.dealer_cards)
        return cards

    def _display_results(self, hand_results: List[tuple[int, List[int], tuple[float, ...]]]) -> None:
        if not hand_results:
            return
        best_lines: List[str] = []
        breakdown_lines: List[str] = []
        insurance_value: float | None = None
        for hand_idx, _, profits in hand_results:
            action_profits = profits[:5]
            if len(profits) > 5 and insurance_value is None:
                insurance_value = profits[5]
            best_index = max(range(len(action_profits)), key=lambda idx: action_profits[idx])
            best_action = ACTION_LABELS[best_index]
            best_value = action_profits[best_index]
            best_lines.append(f"Hand {hand_idx + 1}: {best_action} (EV: {best_value:+.3f})")
            breakdown = ", ".join(f"{label}: {value:+.3f}" for label, value in zip(ACTION_LABELS, action_profits))
            breakdown_lines.append(f"Hand {hand_idx + 1}: {breakdown}")
        if len(hand_results) == 1:
            # Strip the "Hand 1:" prefix for brevity
            best_action_text = best_lines[0].split(": ", 1)[1]
            self._set_best_action_display(f"Best action: {best_action_text}", best_action)
        else:
            self._set_best_action_display("Best actions:\n" + "\n".join(best_lines))
        self.ev_breakdown_var.set("\n".join(breakdown_lines))
        if insurance_value is None or insurance_value != insurance_value:  # NaN guard
            self.insurance_var.set("Insurance EV: –")
        else:
            insurance_text = f"Insurance EV: {insurance_value:+.3f} (" + ("Take" if insurance_value > 0 else "Skip") + ")"
            self.insurance_var.set(insurance_text)
        self._set_status("Simulation complete.")
        self._copy_next_bet_command()

    def _update_betting_info(self) -> None:
        cards_seen = self._get_total_seen_cards(include_hands=True)
        deck_number = max(self.deck_number_var.get(), 1)
        running = get_hilo_running_count(cards_seen)
        cards_left = deck_number * 52 - len(cards_seen)
        physical_left = max(cards_left - self.unseen_burned_count, 0)
        true_count = 0.0 if cards_left <= 0 else running / (cards_left / 52)
        try:
            bet_units = CardCountBetter.get_bet(cards_seen, deck_number)
        except ZeroDivisionError:
            bet_units = 0

        bet_note = ""
        if bet_units > 1 and physical_left > 0:
            active_hands = max(self._active_hand_count(), 1)
            estimated_needed = (active_hands + 1) * 4
            if physical_left < estimated_needed:
                factor = physical_left / estimated_needed
                adjusted_units = 1 + (bet_units - 1) * factor
                reduced_units = max(1, int(adjusted_units))
                if reduced_units < bet_units:
                    bet_units = reduced_units
                    bet_note = " (reduced: low shoe)"

        actual_bet = self._calculate_actual_bet(bet_units)
        min_bet_val = max(self.min_bet_var.get(), 0.0)
        bankroll = max(self.bankroll_var.get(), 0.0)

        # Enforce minimum bet if betting > 0
        if actual_bet > 0 and actual_bet < min_bet_val:
            actual_bet = min(min_bet_val, bankroll)

        forced_min = False
        if true_count < NEGATIVE_COUNT_THRESHOLD:
            actual_bet = min(min_bet_val, bankroll) if bankroll > 0 else 0.0
            forced_min = actual_bet > 0
        locked_round = self._round_in_progress() and self._round_bet_amount is not None
        if locked_round:
            locked_text = self._format_currency(max(self._round_bet_amount or 0.0, 0.0))
            bet_text = f"Locked bet: {locked_text} (log result to refresh)"
        elif forced_min:
            bet_text = f"Suggested bet: Table min (~{self._format_currency(actual_bet)})"
        elif bet_units == 0:
            bet_text = "Suggested bet: Sit out"
        else:
            approx_text = f" (~{self._format_currency(actual_bet)})" if actual_bet > 0 else ""
            bet_text = f"Suggested bet: {bet_units} unit{'s' if bet_units != 1 else ''}{approx_text}{bet_note}"
        if not locked_round:
            self._last_bet_amount = actual_bet
        self.bet_var.set(bet_text)
        self.counts_var.set(
            f"Running: {running:+} | True: {true_count:+.2f} | Left: {max(cards_left, 0)} (Phys: {physical_left})"
        )

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)
        if message:
            self.root.after(4000, lambda: self.status_var.set(""))

    def _handle_deck_change(self, *_: object) -> None:
        try:
            value = self.deck_number_var.get()
        except tk.TclError:
            value = 1
        if value < 1:
            value = 1
        self.deck_number_var.set(value)
        self._clamp_seen_counts()
        cards_left = self.deck_number_var.get() * 52 - len(self._get_total_seen_cards(include_hands=True))
        self.unseen_burned_count = min(self.unseen_burned_count, max(cards_left, 0))
        self._update_betting_info()
        self._state_changed()

    def _handle_max_splits_change(self, *_: object) -> None:
        try:
            value = self.max_splits_var.get()
        except tk.TclError:
            value = 0
        if value < 0:
            self.max_splits_var.set(0)
        elif value > 3:
            self.max_splits_var.set(3)
        else:
            self.max_splits_var.set(value)
        self._state_changed()

    def _handle_bankroll_change(self, *_: object) -> None:
        try:
            value = float(self.bankroll_var.get())
        except (tk.TclError, ValueError):
            value = 0.0
        if value < 0:
            value = 0.0
        self.bankroll_var.set(value)
        self._update_betting_info()
        self._state_changed()

    def _handle_unit_percent_change(self, *_: object) -> None:
        try:
            value = float(self.unit_percent_var.get())
        except (tk.TclError, ValueError):
            value = 0.0
        if value < 0:
            value = 0.0
        elif value > 100:
            value = 100.0
        self.unit_percent_var.set(value)
        self._update_betting_info()
        self._state_changed()

    def _handle_min_bet_change(self, *_: object) -> None:
        try:
            value = float(self.min_bet_var.get())
        except (tk.TclError, ValueError):
            value = 0.0
        if value < 0:
            value = 0.0
        self.min_bet_var.set(value)
        self._update_betting_info()
        self._state_changed()

    def _clamp_seen_counts(self) -> None:
        for value in CARD_VALUES:
            max_manual = self._max_manual_seen_count(value)
            if self.cards_seen_counts[value] > max_manual:
                self.cards_seen_counts[value] = max_manual
            self._update_seen_card_button(value)
        self._state_changed()

    def _build_hand_card_buttons(self, parent: ttk.Frame, target: str) -> Dict[int, tk.Button]:
        buttons: Dict[int, tk.Button] = {}
        columns = 6
        for idx, value in enumerate(CARD_VALUES):
            btn = self._create_dark_button(parent, text=self._hand_button_text(target, value), width=6)
            btn.grid(row=idx // columns, column=idx % columns, padx=2, pady=2, sticky="ew")
            btn.bind("<Button-1>", lambda event, val=value, tgt=target: self._modify_hand_card(tgt, val, 1))
            btn.bind("<Shift-Button-1>", lambda event, val=value, tgt=target: self._modify_hand_card(tgt, val, -1))
            btn.bind("<Button-3>", lambda event, val=value, tgt=target: self._modify_hand_card(tgt, val, -1))
            buttons[value] = btn
        for col in range(columns):
            parent.columnconfigure(col, weight=1)
        return buttons

    def _hand_button_text(self, target: str, value: int) -> str:
        if target == "player":
            hand = self._current_player_hand()
            count = hand.count(value)
        else:
            count = self.dealer_cards.count(value)
        return f"{self._card_face(value)}\n({count})"

    def _update_hand_button(self, target: str, value: int) -> None:
        buttons = self.player_hand_buttons if target == "player" else self.dealer_hand_buttons
        if value in buttons:
            buttons[value].configure(text=self._hand_button_text(target, value))

    def _refresh_hand_buttons(self, target: str, values: Iterable[int] | None = None) -> None:
        if values is None:
            values = CARD_VALUES
        for value in values:
            self._update_hand_button(target, value)

    def _card_face(self, value: int) -> str:
        icon = CARD_ICONS.get(value, CARD_LABELS[value])
        return f"{icon} {CARD_LABELS[value]}"

    def _calculate_actual_bet(self, units: int) -> float:
        bankroll = max(self.bankroll_var.get(), 0.0)
        unit_percent = max(self.unit_percent_var.get(), 0.0)
        base_bet = bankroll * (unit_percent / 100)
        if bankroll <= 0 or base_bet <= 0 or units <= 0:
            return 0.0
        return min(units * base_bet, bankroll)

    def _format_currency(self, amount: float) -> str:
        return f"${amount:,.2f}"

    def _round_in_progress(self) -> bool:
        return any(hand for hand in self.player_hands) or bool(self.dealer_cards)

    def _maybe_lock_round_bet(self) -> None:
        if self._round_bet_amount is not None:
            return
        self._round_bet_amount = max(self._last_bet_amount, 0.0)

    def _clear_round_bet_if_idle(self) -> None:
        if not self._round_in_progress():
            self._round_bet_amount = None

    def _current_round_bet(self) -> float:
        if self._round_bet_amount is None:
            return max(self._last_bet_amount, 0.0)
        return max(self._round_bet_amount, 0.0)

    def _apply_bankroll_delta(self, delta: float) -> None:
        if delta == 0:
            return
        new_value = max(self.bankroll_var.get() + delta, 0.0)
        self.bankroll_var.set(new_value)

    def _update_stats_summary(self) -> None:
        total_games = self._total_games_played()
        win_rate = self._win_rate() * 100
        summary = (
            f"Games (W/L only): {total_games} | Wins: {self.session_stats['wins']} | Losses: {self.session_stats['losses']} | "
            f"Pushes: {self.session_stats['pushes']} | Win rate: {win_rate:.1f}% | Net: {self._format_currency(self.session_stats['net_profit'])}"
        )
        self.stats_summary_var.set(summary)

    def _update_stats_plot(self) -> None:
        if not (self._stats_fig and self._stats_canvas and self._winrate_ax and self._profit_ax):
            return
        history = list(self.session_stats.get("history", []))
        self._winrate_ax.clear()
        self._profit_ax.clear()
        self._style_stats_axis(self._winrate_ax, "Win %")
        self._style_stats_axis(self._profit_ax, "Net $", xlabel="Games logged")
        if not history:
            self._winrate_ax.text(0.5, 0.5, "Log games to see win %", color=TEXT_COLOR,
                                   ha="center", va="center", transform=self._winrate_ax.transAxes)
            self._profit_ax.text(0.5, 0.5, "Net profit history will appear here", color=TEXT_COLOR,
                                 ha="center", va="center", transform=self._profit_ax.transAxes)
        else:
            games: List[int] = []
            win_rates: List[float] = []
            profits: List[float] = []
            for idx, entry in enumerate(history):
                try:
                    game_value = int(entry.get("game", idx + 1))
                except (TypeError, ValueError):
                    game_value = idx + 1
                games.append(max(game_value, 1))
                try:
                    rate_value = float(entry.get("win_rate", 0.0))
                except (TypeError, ValueError):
                    rate_value = 0.0
                if rate_value != rate_value:  # NaN guard
                    rate_value = 0.0
                win_rates.append(max(0.0, min(1.0, rate_value)) * 100)
                try:
                    profit_value = float(entry.get("profit", 0.0))
                except (TypeError, ValueError):
                    profit_value = 0.0
                profits.append(profit_value)
            self._winrate_ax.plot(games, win_rates, color=ACCENT_COLOR, linewidth=2)
            self._winrate_ax.set_ylim(0, 100)
            self._profit_ax.plot(games, profits, color="#66ff99", linewidth=2)
            min_profit = min(profits + [0.0])
            max_profit = max(profits + [0.0])
            if min_profit == max_profit:
                pad = 10.0 if max_profit == 0 else abs(max_profit) * 0.15
                min_profit -= pad
                max_profit += pad
            self._profit_ax.set_ylim(min_profit, max_profit)
            self._profit_ax.axhline(0, color="#888888", linestyle="--", linewidth=1)
        self._stats_fig.tight_layout(pad=1.0)
        self._stats_canvas.draw_idle()

    def _style_stats_axis(self, axis, ylabel: str, xlabel: str | None = None) -> None:
        axis.set_facecolor(DARK_BG)
        axis.set_ylabel(ylabel, color=TEXT_COLOR)
        if xlabel:
            axis.set_xlabel(xlabel, color=TEXT_COLOR)
        axis.tick_params(colors=TEXT_COLOR)
        axis.grid(color="#444444", linestyle="--", linewidth=0.5, alpha=0.5)
        for spine in axis.spines.values():
            spine.set_color(TEXT_COLOR)

    def _total_games_played(self) -> int:
        return int(self.session_stats.get("wins", 0)) + int(self.session_stats.get("losses", 0))

    def _win_rate(self) -> float:
        total = self._total_games_played()
        if total <= 0:
            return 0.0
        return self.session_stats.get("wins", 0) / total

    def _append_history_entry(self) -> None:
        total_games = self._total_games_played()
        if total_games <= 0:
            self.session_stats["history"] = []
            return
        entry = {
            "game": total_games,
            "profit": float(self.session_stats.get("net_profit", 0.0)),
            "win_rate": self._win_rate(),
        }
        history = self.session_stats.setdefault("history", [])
        history.append(entry)
        if len(history) > STATS_HISTORY_LIMIT:
            del history[: len(history) - STATS_HISTORY_LIMIT]

    def _confirm_reset_stats(self) -> None:
        if messagebox.askyesno("Reset Stats", "Clear logged wins, losses, pushes, and profit history?"):
            self._reset_stats()

    def _reset_stats(self) -> None:
        self.session_stats = self._default_stats()
        self._update_stats_summary()
        self._update_stats_plot()
        self._state_changed()
        self._set_status("Session tracking reset.")

    def _default_stats(self) -> Dict[str, object]:
        return {"wins": 0, "losses": 0, "pushes": 0, "net_profit": 0.0, "history": []}

    def _copy_next_bet_command(self) -> None:
        amount = int(round(max(self._last_bet_amount, 0.0)))
        command = f"$bj {amount}"
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(command)
        except tk.TclError:
            self._set_status("Could not copy bet command to clipboard.")

    def run(self) -> None:
        self.root.mainloop()

    def _sync_ui_from_state(self) -> None:
        if self.card_buttons:
            for value in CARD_VALUES:
                self._update_seen_card_button(value)
        if self.player_notebook:
            self._rebuild_player_tabs()
            self._refresh_hand_buttons("player")
        if hasattr(self, "dealer_listbox"):
            self._refresh_listbox(self.dealer_listbox, self.dealer_cards)
            self._refresh_hand_buttons("dealer")
        self._update_hand_summaries()

    def _load_state(self) -> None:
        self._suspend_state = True
        if not self._state_path.exists():
            self._suspend_state = False
            return
        try:
            with self._state_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            self._suspend_state = False
            return

        self.deck_number_var.set(int(data.get("deck_number", self.deck_number_var.get())))
        self.max_splits_var.set(int(data.get("max_splits", self.max_splits_var.get())))
        self.dealer_hits_soft17_var.set(bool(data.get("dealer_hits_soft17", self.dealer_hits_soft17_var.get())))
        self.dealer_peeks_var.set(bool(data.get("dealer_peeks", self.dealer_peeks_var.get())))
        self.das_var.set(bool(data.get("das", self.das_var.get())))
        self.allow_double_var.set(bool(data.get("allow_double", self.allow_double_var.get())))
        self.allow_insurance_var.set(bool(data.get("allow_insurance", self.allow_insurance_var.get())))
        self.allow_surrender_var.set(bool(data.get("allow_surrender", self.allow_surrender_var.get())))
        self.burn_count_var.set(int(data.get("burn_count", self.burn_count_var.get())))
        try:
            self.bankroll_var.set(float(data.get("bankroll", self.bankroll_var.get())))
        except (TypeError, ValueError):
            self.bankroll_var.set(0.0)
        try:
            self.unit_percent_var.set(float(data.get("unit_percent", self.unit_percent_var.get())))
        except (TypeError, ValueError):
            self.unit_percent_var.set(1.0)
        try:
            self.min_bet_var.set(float(data.get("min_bet", self.min_bet_var.get())))
        except (TypeError, ValueError):
            self.min_bet_var.set(100.0)
        try:
            self.unseen_burned_count = max(int(data.get("unseen_burned_count", 0)), 0)
        except (TypeError, ValueError):
            self.unseen_burned_count = 0

        counts_data = data.get("cards_seen_counts", {})
        if isinstance(counts_data, dict):
            for value in CARD_VALUES:
                stored = counts_data.get(str(value), counts_data.get(value, 0))
                try:
                    self.cards_seen_counts[value] = max(int(stored), 0)
                except (TypeError, ValueError):
                    self.cards_seen_counts[value] = 0

        def sanitize_cards(cards: Iterable[int | str]) -> List[int]:
            valid: List[int] = []
            for card in cards or []:
                try:
                    value = int(card)
                except (TypeError, ValueError):
                    continue
                if value in CARD_VALUES:
                    valid.append(value)
            return valid

        player_hands_data = data.get("player_hands")
        if isinstance(player_hands_data, list):
            parsed_hands = [sanitize_cards(hand) for hand in player_hands_data]
            self.player_hands = parsed_hands or [[]]
        else:
            self.player_hands = [sanitize_cards(data.get("player_cards", []))]
            if not self.player_hands:
                self.player_hands = [[]]
        try:
            active_idx = int(data.get("active_hand_index", 0))
        except (TypeError, ValueError):
            active_idx = 0
        self.active_hand_index = min(max(active_idx, 0), len(self.player_hands) - 1)
        self.dealer_cards = sanitize_cards(data.get("dealer_cards", []))
        stats_data = data.get("session_stats")
        if isinstance(stats_data, dict):
            parsed = self._default_stats()
            for key in ("wins", "losses", "pushes"):
                try:
                    parsed[key] = max(int(stats_data.get(key, 0)), 0)
                except (TypeError, ValueError):
                    parsed[key] = 0
            try:
                parsed["net_profit"] = float(stats_data.get("net_profit", 0.0))
            except (TypeError, ValueError):
                parsed["net_profit"] = 0.0
            history_data = stats_data.get("history", [])
            parsed_history: List[Dict[str, float]] = []
            if isinstance(history_data, list):
                for entry in history_data:
                    if not isinstance(entry, dict):
                        continue
                    try:
                        game = max(int(entry.get("game", 0)), 0)
                        profit = float(entry.get("profit", 0.0))
                        win_rate = float(entry.get("win_rate", 0.0))
                    except (TypeError, ValueError):
                        continue
                    parsed_history.append({"game": game, "profit": profit, "win_rate": win_rate})
            parsed["history"] = parsed_history[-STATS_HISTORY_LIMIT:]
            self.session_stats = parsed
        else:
            self.session_stats = self._default_stats()
        round_bet_raw = data.get("round_bet_amount")
        try:
            self._round_bet_amount = max(float(round_bet_raw), 0.0) if round_bet_raw is not None else None
        except (TypeError, ValueError):
            self._round_bet_amount = None
        if self._round_bet_amount is not None and not self._round_in_progress():
            self._round_bet_amount = None
        self._suspend_state = False

    def _save_state(self) -> None:
        if self._suspend_state:
            return
        data = {
            "deck_number": self.deck_number_var.get(),
            "max_splits": self.max_splits_var.get(),
            "dealer_hits_soft17": self.dealer_hits_soft17_var.get(),
            "dealer_peeks": self.dealer_peeks_var.get(),
            "das": self.das_var.get(),
            "allow_double": self.allow_double_var.get(),
            "allow_insurance": self.allow_insurance_var.get(),
            "min_bet": self.min_bet_var.get(),
            "allow_surrender": self.allow_surrender_var.get(),
            "burn_count": self.burn_count_var.get(),
            "bankroll": self.bankroll_var.get(),
            "unit_percent": self.unit_percent_var.get(),
            "unseen_burned_count": self.unseen_burned_count,
            "cards_seen_counts": self.cards_seen_counts,
            "player_hands": self.player_hands,
            "dealer_cards": self.dealer_cards,
            "active_hand_index": self.active_hand_index,
            "session_stats": self.session_stats,
            "round_bet_amount": self._round_bet_amount,
        }
        try:
            with self._state_path.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _state_changed(self) -> None:
        if self._suspend_state:
            return
        self._save_state()

    def _on_rule_toggle(self) -> None:
        self._update_betting_info()
        self._state_changed()

    def _double_confirm(self, title: str, message: str) -> bool:
        if not messagebox.askyesno(title, message):
            return False
        return messagebox.askyesno(title, "Please confirm once more.")

    def _confirm_clear_seen_cards(self) -> None:
        if self._double_confirm("Clear Seen Cards", "Clear all manually logged seen cards?"):
            self._clear_seen_cards()

    def _confirm_burn_cards(self) -> None:
        count = self.burn_count_var.get()
        if self._double_confirm("Burn Cards", f"Remove {count} unseen card(s) from the shoe?"):
            self._burn_unknown_cards()

    def _confirm_clear_everything(self) -> None:
        if self._double_confirm("Clear Everything", "Reset hands and seen cards?"):
            self._clear_all()

    def _apply_dark_theme(self) -> None:
        self.root.configure(bg=DARK_BG)
        self.root.tk_setPalette(background=DARK_BG, foreground=TEXT_COLOR, activeBackground=BUTTON_ACTIVE_BG,
                                activeForeground=TEXT_COLOR, highlightColor=ACCENT_COLOR,
                                selectBackground=ACCENT_COLOR, selectForeground=TEXT_COLOR,
                                troughColor=BUTTON_BG)
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=PANEL_BG)
        style.configure("TLabelframe", background=PANEL_BG, foreground=TEXT_COLOR)
        style.configure("TLabelframe.Label", background=PANEL_BG, foreground=TEXT_COLOR)
        style.configure("TLabel", background=PANEL_BG, foreground=TEXT_COLOR)
        style.configure("TCheckbutton", background=PANEL_BG, foreground=TEXT_COLOR)
        style.configure("TButton", background=BUTTON_BG, foreground=TEXT_COLOR)
        style.map("TButton",
               background=[("active", BUTTON_ACTIVE_BG), ("pressed", BUTTON_ACTIVE_BG)],
               foreground=[("active", TEXT_COLOR), ("pressed", TEXT_COLOR), ("disabled", "#888888")])
        style.configure("TNotebook", background=PANEL_BG)
        style.configure("TCheckbutton", background=PANEL_BG, foreground=TEXT_COLOR)
        style.map("TCheckbutton",
               foreground=[("active", TEXT_COLOR), ("selected", TEXT_COLOR)],
               background=[("active", PANEL_BG), ("selected", PANEL_BG)])
        style.configure("Treeview", background=PANEL_BG, fieldbackground=PANEL_BG, foreground=TEXT_COLOR)
        style.configure("TMenubutton", background=BUTTON_BG, foreground=TEXT_COLOR)
        self.style = style

    def _create_dark_button(self, parent: tk.Widget, **kwargs) -> tk.Button:
        defaults = {
            "bg": BUTTON_BG,
            "fg": TEXT_COLOR,
            "activebackground": BUTTON_ACTIVE_BG,
            "activeforeground": TEXT_COLOR,
            "highlightthickness": 0,
            "borderwidth": 1,
            "relief": tk.RAISED,
        }
        defaults.update(kwargs)
        return tk.Button(parent, **defaults)

    def _style_entry(self, widget: tk.Widget) -> None:
        widget.configure(bg=BUTTON_BG, fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
                         highlightthickness=0, relief=tk.SOLID, borderwidth=1)

    def _style_listbox(self, widget: tk.Listbox) -> None:
        widget.configure(bg=PANEL_BG, fg=TEXT_COLOR, selectbackground=ACCENT_COLOR,
                         selectforeground=TEXT_COLOR, highlightbackground=BUTTON_BG,
                         highlightcolor=BUTTON_ACTIVE_BG, borderwidth=1, relief=tk.SOLID)


def main() -> None:
    root = tk.Tk()
    gui = BlackjackSimulatorGUI(root)
    gui.run()


if __name__ == "__main__":
    main()
