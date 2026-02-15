from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Dict
from .base import BaseFrame
from ..constants import CARD_VALUES

if TYPE_CHECKING:
    from ..app import BlackjackSimulatorGUI

class SeenCardsFrame(BaseFrame):
    def _setup_ui(self):
        info = ("Left click adds. Shift+Click or right click removes. "
                "Use the result buttons to log both hands automatically.")
        ttk.Label(self, text=info, wraplength=600).pack(anchor="w", pady=(0, 6))

        grid = ttk.Frame(self)
        grid.pack(fill="x")
        self.buttons: Dict[int, tk.Button] = {}
        
        for idx, value in enumerate(CARD_VALUES):
            btn = self.app.create_dark_button(grid, text="", width=8)
            btn.grid(row=0, column=idx, padx=2, pady=2, sticky="ew")
            
            # Bindings
            btn.bind("<Button-1>", lambda e, v=value: self.app.modify_seen_card(v, 1))
            btn.bind("<Shift-Button-1>", lambda e, v=value: self.app.modify_seen_card(v, -1))
            btn.bind("<Button-3>", lambda e, v=value: self.app.modify_seen_card(v, -1))
            self.buttons[value] = btn
            grid.columnconfigure(idx, weight=1)

        # Bottom controls
        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(8, 0))
        
        ttk.Button(controls, text="Clear Seen Cards", command=self.app.confirm_clear_seen_cards).pack(side="left")
        
        # Burn controls
        burn_frame = ttk.Frame(controls)
        burn_frame.pack(side="left", padx=20)
        ttk.Label(burn_frame, text="Remove unknown:").pack(side="left", padx=2)
        
        self.burn_var = tk.IntVar(value=self.state.rules.burn_count)
        spin = tk.Spinbox(burn_frame, from_=1, to=312, width=5, textvariable=self.burn_var)
        self.app.style_entry(spin)
        spin.pack(side="left", padx=2)

        def do_burn():
            self.state.rules.burn_count = self.burn_var.get()
            self.app.burn_cards()

        ttk.Button(burn_frame, text="Burn", command=do_burn).pack(side="left", padx=2)

    def refresh(self):
        for val, btn in self.buttons.items():
            count = self.state.cards_seen_counts[val]
            face = self.app.get_card_face(val)
            btn.configure(text=f"{face}\n({count})")
