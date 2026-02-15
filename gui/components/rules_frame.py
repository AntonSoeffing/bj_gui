from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING
from .base import BaseFrame
from ..theme import Theme

if TYPE_CHECKING:
    from ..app import BlackjackSimulatorGUI

class RulesFrame(BaseFrame):
    def _setup_ui(self):
        row1 = ttk.Frame(self)
        row1.pack(fill="x", pady=4)
        
        # Spinboxes and labels helper
        def add_spin(parent, label, attr, from_, to_, width=5, increment=1, is_float=False):
            ttk.Label(parent, text=label).pack(side="left", padx=(4, 2))
            
            # Variable binding
            target_obj = self.state.betting if is_float else self.state.rules
            var_type = tk.DoubleVar if is_float else tk.IntVar
            var = var_type(value=getattr(target_obj, attr))
            
            # Trace to update state object and tripper app update
            def on_change(*_):
                try:
                    val = var.get()
                    setattr(target_obj, attr, val)
                    self.app.on_state_change()
                except tk.TclError:
                    pass
            var.trace_add("write", on_change)
            
            spin = tk.Spinbox(parent, from_=from_, to=to_, width=width, 
                             increment=increment, textvariable=var)
            self.app.style_entry(spin)
            spin.pack(side="left", padx=2)
            return var

        # Decks & Splits
        add_spin(row1, "Decks:", "deck_number", 1, 12)
        add_spin(row1, "Max splits:", "max_splits", 0, 3)

        # Switches
        def add_check(parent, label, attr):
            var = tk.BooleanVar(value=getattr(self.state.rules, attr))
            def on_toggle():
                setattr(self.state.rules, attr, var.get())
                self.app.on_state_change()
            chk = ttk.Checkbutton(parent, text=label, variable=var, command=on_toggle)
            chk.pack(side="left", padx=8)
            return var

        add_check(row1, "Dealer hits soft 17", "dealer_hits_soft17")
        add_check(row1, "Dealer peeks", "dealer_peeks")
        add_check(row1, "DAS", "das")
        
        row2 = ttk.Frame(self)
        row2.pack(fill="x", pady=4)
        add_check(row2, "Allow double", "allow_double")
        add_check(row2, "Allow insurance", "allow_insurance")
        add_check(row2, "Allow surrender", "allow_surrender")

        row3 = ttk.Frame(self)
        row3.pack(fill="x", pady=(8, 4))
        add_spin(row3, "Bankroll ($):", "bankroll", 0, 10000000, 10, 50, True)
        add_spin(row3, "Unit %:", "unit_percent", 0.1, 20.0, 5, 0.1, True)
        add_spin(row3, "Min Bet ($):", "min_bet", 0, 10000, 6, 5, True)
