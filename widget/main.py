"""
Stock Desktop Widget V3 — Entry point.
Each stock card is an independent floating window on the desktop.
"""

import sys
import os
import logging

# Configure basic logging for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), '..', 'widget.log'), mode='a')
    ]
)

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from widget.widget_manager import WidgetManager


def main():
    logger.info("Starting Vestra Widget Manager...")
    app = WidgetManager()
    app.mainloop()


if __name__ == "__main__":
    main()
