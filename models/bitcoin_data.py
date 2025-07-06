# your_project/models/bitcoin_data.py

from datetime import datetime

class BitcoinData:
    """
    Represents a single data point for Bitcoin, including price, volume,
    market cap, price change, and source.
    """
    def __init__(self, timestamp: datetime, price: float, volume_24h: float, 
                 market_cap: float, price_change_24h: float, source: str):
        """
        Initializes a BitcoinData object.

        Args:
            timestamp (datetime): The timestamp of the data point.
            price (float): The current price of Bitcoin.
            volume_24h (float): The 24-hour trading volume.
            market_cap (float): The market capitalization.
            price_change_24h (float): The 24-hour price change percentage.
            source (str): The source of the data (e.g., 'binance').
        """
        self.timestamp = timestamp
        self.price = price
        self.volume_24h = volume_24h
        self.market_cap = market_cap
        self.price_change_24h = price_change_24h
        self.source = source
    
    def to_dict(self) -> dict:
        """
        Converts the BitcoinData object to a dictionary, suitable for JSON serialization.

        Returns:
            dict: A dictionary representation of the BitcoinData.
        """
        return {
            'timestamp': self.timestamp.isoformat(), # Convert datetime to ISO format string
            'price': self.price,
            'volume_24h': self.volume_24h,
            'market_cap': self.market_cap,
            'price_change_24h': self.price_change_24h,
            'source': self.source
        }

    def __repr__(self) -> str:
        """
        Returns a string representation of the BitcoinData object for debugging.
        """
        return (f"BitcoinData(timestamp={self.timestamp.isoformat()}, price={self.price:.2f}, "
                f"volume_24h={self.volume_24h:.2f}, source='{self.source}')")

