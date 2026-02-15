# -*- coding: utf-8 -*-
"""
Interactive GUI for blackjack simulations.
Entry point for the application.
"""

import tkinter as tk
from gui import BlackjackSimulatorGUI

def main():
    root = tk.Tk()
    app = BlackjackSimulatorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
