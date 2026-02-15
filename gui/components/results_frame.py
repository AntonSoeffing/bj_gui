from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING
from .base import BaseFrame
from ..theme import Theme

if TYPE_CHECKING:
    from ..app import BlackjackSimulatorGUI

class ResultsFrame(BaseFrame):
    def _setup_ui(self):
        # Best Action Display - BIG
        ba_frame = tk.Frame(self, bg=Theme.BEST_ACTION_BG, highlightthickness=1,
                            highlightbackground=Theme.BEST_ACTION_BORDER)
        ba_frame.pack(fill="x", pady=(0, 6))
        
        self.best_action_var = tk.StringVar(value="Best action: -")
        self.ba_label = tk.Label(ba_frame, textvariable=self.best_action_var,
                                 font=("Segoe UI", 18, "bold"), bg=Theme.BEST_ACTION_BG,
                                 fg=Theme.ACCENT_COLOR, anchor="w", padx=10, pady=10)
        self.ba_label.pack(fill="both")

        # Info Grid
        info = tk.Frame(self, bg=Theme.INFO_PANEL_BG)
        info.pack(fill="x", pady=(0, 4))
        
        self.ev_var = tk.StringVar(value="Stand: -, Hit: -, Double: -, Split: -, Surrender: -")
        self.ins_var = tk.StringVar(value="Insurance EV: -")
        self.bet_var = tk.StringVar(value="Suggested bet: 1 unit")
        self.cnt_var = tk.StringVar(value="Running: +0 | True: +0.00")

        for var in (self.ev_var, self.ins_var, self.bet_var, self.cnt_var):
            tk.Label(info, textvariable=var, bg=Theme.INFO_PANEL_BG, fg=Theme.TEXT_COLOR,
                     anchor="w", justify="left").pack(fill="x", padx=8, pady=2)

        # Round Adjustment (Double Down)
        adj_frame = ttk.LabelFrame(self, text="Round Adjustment")
        adj_frame.pack(fill="x", pady=8)
        
        self.dd_var = tk.BooleanVar(value=False)
        self.dd_chk = ttk.Checkbutton(adj_frame, text="Double down (+1 unit)", variable=self.dd_var,
                                      command=self._on_dd_change)
        self.dd_chk.pack(anchor="w", padx=5, pady=2)

    def _on_dd_change(self):
        self.state.round_doubled = self.dd_var.get()

    def refresh(self):
        self.dd_var.set(self.state.round_doubled)
        # Main text vars are updated by app.update_betting_info and app.run_simulation
