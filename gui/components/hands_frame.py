from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Dict
from .base import BaseFrame
from ..constants import CARD_VALUES, CARD_LABELS
from ..hand_utils import HandUtils

if TYPE_CHECKING:
    from ..app import BlackjackSimulatorGUI

class HandsFrame(BaseFrame):
    def _setup_ui(self):
        # Two columns: Player and Dealer
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        
        # --- Player Side ---
        p_frame = ttk.Frame(self)
        p_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        self.p_summary = tk.StringVar(value="Player Total: 0")
        ttk.Label(p_frame, textvariable=self.p_summary).pack(anchor="w")
        
        p_ctrl = ttk.Frame(p_frame)
        p_ctrl.pack(fill="x", pady=2)
        ttk.Button(p_ctrl, text="Add Hand", command=self.app.add_player_hand).pack(side="left", padx=2)
        ttk.Button(p_ctrl, text="Remove Hand", command=self.app.remove_player_hand).pack(side="left", padx=2)
        
        self.notebook = ttk.Notebook(p_frame)
        self.notebook.pack(fill="both", expand=True, pady=4)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)
        
        ttk.Label(p_frame, text="Click rank to add. Shift/Right-click removes.").pack(anchor="w")
        self.p_buttons = self._create_card_grid(p_frame, "player")

        # --- Dealer Side ---
        d_frame = ttk.Frame(self)
        d_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        self.d_summary = tk.StringVar(value="Dealer Total: 0")
        ttk.Label(d_frame, textvariable=self.d_summary).pack(anchor="w")
        
        self.d_listbox = tk.Listbox(d_frame, height=6)
        self.app.style_listbox(self.d_listbox)
        self.d_listbox.pack(fill="both", pady=4)
        
        d_ctrl = ttk.Frame(d_frame)
        d_ctrl.pack(fill="x", pady=2)
        ttk.Button(d_ctrl, text="Remove Selected", command=lambda: self.app.remove_selected_card("dealer")).pack(fill="x", pady=1)
        ttk.Button(d_ctrl, text="Clear Dealer", command=lambda: self.app.clear_hand("dealer")).pack(fill="x", pady=1)
        
        ttk.Label(d_frame, text="First card is up-card.").pack(anchor="w", pady=(6,0))
        self.d_buttons = self._create_card_grid(d_frame, "dealer")

    def _create_card_grid(self, parent, target) -> Dict[int, tk.Button]:
        frame = ttk.Frame(parent)
        frame.pack(fill="x")
        buttons = {}
        for i, val in enumerate(CARD_VALUES):
            btn = self.app.create_dark_button(frame, text="", width=6)
            row, col = divmod(i, 6)
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
            
            # Bindings
            btn.bind("<Button-1>", lambda e, v=val, t=target: self.app.modify_hand_card(t, v, 1))
            btn.bind("<Shift-Button-1>", lambda e, v=val, t=target: self.app.modify_hand_card(t, v, -1))
            btn.bind("<Button-3>", lambda e, v=val, t=target: self.app.modify_hand_card(t, v, -1))
            buttons[val] = btn
            frame.columnconfigure(col, weight=1)
        return buttons

    def _on_tab_change(self, _):
        try:
            idx = self.notebook.index("current")
            self.state.active_hand_index = idx
            self.refresh_buttons()
            self.refresh_summaries()
        except tk.TclError:
            pass

    def refresh(self):
        # Rebuild notebook tabs if count changed
        current_tabs = self.notebook.tabs()
        hands = self.state.player_hands
        
        # Naive rebuild if length mismatches
        if len(current_tabs) != len(hands):
            for tab in current_tabs:
                self.notebook.forget(tab)
            
            self.listboxes = []
            for i in range(len(hands)):
                frame = ttk.Frame(self.notebook)
                frame.columnconfigure(0, weight=1)
                
                lb = tk.Listbox(frame, height=6)
                self.app.style_listbox(lb)
                lb.grid(row=0, column=0, sticky="nsew")
                
                # Hand controls
                ctrl = ttk.Frame(frame)
                ctrl.grid(row=1, column=0, sticky="ew", pady=2)
                ttk.Button(ctrl, text="Clear", 
                          command=lambda idx=i: self.app.clear_hand("player", idx)).pack(side="right")
                ttk.Button(ctrl, text="Remove Sel", 
                          command=lambda idx=i: self.app.remove_selected_card("player", idx)).pack(side="right", padx=4)
                
                self.notebook.add(frame, text=f"Hand {i+1}")
                self.listboxes.append(lb)

            # Restore selection
            if 0 <= self.state.active_hand_index < len(self.notebook.tabs()):
                self.notebook.select(self.state.active_hand_index)
                
        self.refresh_listboxes()
        self.refresh_buttons()
        self.refresh_summaries()

    def refresh_listboxes(self):
        # Player
        for i, hand in enumerate(self.state.player_hands):
            if i < len(self.listboxes):
                lb = self.listboxes[i]
                if lb.size() != len(hand) or True: # Force refresh for simplicity
                    lb.delete(0, tk.END)
                    for card in hand:
                        lb.insert(tk.END, CARD_LABELS[card])
        
        # Dealer
        self.d_listbox.delete(0, tk.END)
        for card in self.state.dealer_cards:
            self.d_listbox.insert(tk.END, CARD_LABELS[card])

    def refresh_buttons(self):
        # Active Player Hand
        active_idx = self.state.active_hand_index
        if 0 <= active_idx < len(self.state.player_hands):
            active_hand = self.state.player_hands[active_idx]
            for val, btn in self.p_buttons.items():
                count = active_hand.count(val)
                face = self.app.get_card_face(val)
                btn.configure(text=f"{face}\n({count})")
        
        # Dealer Hand
        for val, btn in self.d_buttons.items():
            count = self.state.dealer_cards.count(val)
            face = self.app.get_card_face(val)
            btn.configure(text=f"{face}\n({count})")

    def refresh_summaries(self):
        # Player
        idx = self.state.active_hand_index
        if 0 <= idx < len(self.state.player_hands):
            hand = self.state.player_hands[idx]
            total = HandUtils.calculate_value(hand)
            self.p_summary.set(f"Hand {idx+1} Total: {total} ({len(hand)} cards)")
            
            # Update tab titles too
            for i, h in enumerate(self.state.player_hands):
                 t = HandUtils.calculate_value(h)
                 try:
                     self.notebook.tab(i, text=f"Hand {i+1} ({t})")
                 except tk.TclError: pass

        # Dealer
        d_hand = self.state.dealer_cards
        d_total = HandUtils.calculate_value(d_hand)
        self.d_summary.set(f"Dealer Total: {d_total} ({len(d_hand)} cards)")
