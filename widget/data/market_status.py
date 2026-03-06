"""
Market hours logic for determining if a market is currently open.
"""

from datetime import datetime
import pytz

def is_market_open(category: str) -> bool:
    """Check if the given market category is currently open."""
    if category == "Crypto":
        return True  # 24/7
        
    now = datetime.now()
    
    if category in ("美股", "ETF"):
        # US Market: 9:30 AM to 4:00 PM EST, Mon-Fri
        us_tz = pytz.timezone("America/New_York")
        us_now = now.astimezone(us_tz)
        if us_now.weekday() >= 5: # Sat or Sun
            return False
            
        market_open = us_now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = us_now.replace(hour=16, minute=0, second=0, microsecond=0)
        return market_open <= us_now <= market_close
        
    elif category == "台股":
        # TW Market: 9:00 AM to 1:30 PM Taipei Time, Mon-Fri
        tw_tz = pytz.timezone("Asia/Taipei")
        tw_now = now.astimezone(tw_tz)
        if tw_now.weekday() >= 5: # Sat or Sun
            return False
            
        market_open = tw_now.replace(hour=9, minute=0, second=0, microsecond=0)
        market_close = tw_now.replace(hour=13, minute=30, second=0, microsecond=0)
        return market_open <= tw_now <= market_close
        
    return False
