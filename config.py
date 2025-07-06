# your_project/config.py

import os

class Config:
    """
    Configuration class for the Bitcoin Trading System.
    Manages various settings for the application.
    """
    
    # Database paths
    DATA_DIR = 'data'
    TRADING_ANALYZER_DB = os.path.join(DATA_DIR, 'trading_analyzer.db')
    BITCOIN_STREAM_DB = os.path.join(DATA_DIR, 'bitcoin_stream.db')
    
    # Logging configuration
    LOG_FILE = os.path.join(DATA_DIR, 'trading_system.log')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper() # Default to INFO, can be overridden by env var
    
    # Bitcoin Streamer settings
    BITCOIN_STREAM_MAX_QUEUE_SIZE = 1000
    BITCOIN_STREAM_FETCH_INTERVAL_SECONDS = 300  # 5 minutes
    BITCOIN_STREAM_MAX_CONSECUTIVE_ERRORS = 5
    
    # Bitcoin Stream Processor settings
    BITCOIN_PROCESSOR_BATCH_SIZE = 20
    
    # Trading Analyzer settings
    TRADING_ANALYZER_UPDATE_INTERVAL_SECONDS = 60 # How often to feed data to analyzer
    
    # Flask app settings
    FLASK_DEBUG_MODE = os.getenv('DEBUG', 'false').lower() == 'true'
    FLASK_PORT = int(os.getenv('PORT', 5000))
    FLASK_HOST = os.getenv('HOST', '0.0.0.0')

    # Data cleanup settings
    DEFAULT_DAYS_TO_KEEP_DATA = 7

    # API Endpoints (if external APIs were used directly, but here they are internal)
    BINANCE_API_URL = "https://api.binance.com/api/v3/ticker/24hr"
    BINANCE_SYMBOL = 'BTCUSDT'

    # Price validation thresholds
    PRICE_CHANGE_THRESHOLD_PCT = 0.10 # 10%
    MIN_EXPECTED_PRICE = 20000
    MAX_EXPECTED_PRICE = 200000

    # Frontend paths (for static files and templates)
    STATIC_DIR_CSS = os.path.join('static', 'css')
    STATIC_DIR_JS = os.path.join('static', 'js')
    TEMPLATES_DIR = 'templates'

    def __init__(self):
        """
        Initializes the Config class and ensures necessary directories exist.
        """
        os.makedirs(self.DATA_DIR, exist_ok=True)
        os.makedirs(self.STATIC_DIR_CSS, exist_ok=True)
        os.makedirs(self.STATIC_DIR_JS, exist_ok=True)
        os.makedirs(self.TEMPLATES_DIR, exist_ok=True)

# Instantiate the config for easy import
app_config = Config()
