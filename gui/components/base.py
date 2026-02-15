from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..app import BlackjackSimulatorGUI
    from ..state import GameState

class BaseFrame(ttk.Frame):
    def __init__(self, master: tk.Widget, app: 'BlackjackSimulatorGUI', **kwargs: Any):
        super().__init__(master, **kwargs)
        self.app = app
        self.state: 'GameState' = app.state
        self._setup_ui()

    def _setup_ui(self) -> None:
        raise NotImplementedError

    def refresh(self) -> None:
        """Called when state changes to update UI."""
        pass
