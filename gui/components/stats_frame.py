from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from .base import BaseFrame
from ..theme import Theme

if TYPE_CHECKING:
    from ..app import BlackjackSimulatorGUI

class StatsFrame(BaseFrame):
    def _setup_ui(self):
        header = ttk.Frame(self)
        header.pack(fill="x")
        
        self.summary_var = tk.StringVar(value="Games: 0 | Win rate: 0.0% | Net: $0.00")
        ttk.Label(header, textvariable=self.summary_var).pack(side="left")
        
        ttk.Button(header, text="Reset", command=self.app.reset_stats).pack(side="right", padx=4)
        
        self.fig = Figure(figsize=(6, 3), dpi=100)
        self.fig.patch.set_facecolor(Theme.PANEL_BG)
        self.ax_win = self.fig.add_subplot(211)
        self.ax_net = self.fig.add_subplot(212)
        
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, pady=4)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=container)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.get_tk_widget().configure(bg=Theme.PANEL_BG)
        
        self._style_axes()

    def _style_axes(self):
        for ax, label in [(self.ax_win, "Win %"), (self.ax_net, "Net $")]:
            ax.clear()
            ax.set_facecolor(Theme.DARK_BG)
            ax.set_ylabel(label, color=Theme.TEXT_COLOR)
            ax.tick_params(colors=Theme.TEXT_COLOR)
            ax.grid(color=Theme.AXIS_GRID, linestyle="--", linewidth=0.5, alpha=0.5)
            for spine in ax.spines.values():
                spine.set_color(Theme.TEXT_COLOR)

    def refresh(self):
        s = self.state.stats
        self.summary_var.set(f"Games: {s.total_games} | Wins: {s.wins} | Losses: {s.losses} | "
                             f"Net: ${s.net_profit:,.2f}")
        
        # Plot
        history = s.history
        self._style_axes()
        
        if history:
            games = [h.get("game", i+1) for i, h in enumerate(history)]
            rates = [h.get("win_rate", 0)*100 for h in history]
            profits = [h.get("profit", 0) for h in history]
            
            self.ax_win.plot(games, rates, color=Theme.ACCENT_COLOR)
            self.ax_net.plot(games, profits, color="#66ff99")
            
        self.fig.tight_layout()
        self.canvas.draw_idle()
