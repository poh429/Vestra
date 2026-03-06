"""
Stock Desktop Widget V3 — Entry point.
Each stock card is an independent floating window on the desktop.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from widget.widget_manager import WidgetManager


def main():
    app = WidgetManager()
    app.mainloop()


if __name__ == "__main__":
    main()
