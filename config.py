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
    AUTO_START_STREAM = True # Adicionado para controlar o início automático do streamer
    
    # Bitcoin Stream Processor settings
    BITCOIN_PROCESSOR_BATCH_SIZE = 20
    
    # Trading Analyzer settings
    TRADING_ANALYZER_UPDATE_INTERVAL_SECONDS = 60 # How often to feed data to analyzer
    ANALYZER_PROCESS_INTERVAL_SECONDS = 5 # Intervalo para a thread de processamento/análise
    
    # Flask app settings
    FLASK_DEBUG_MODE = os.getenv('DEBUG', 'false').lower() == 'true'
    FLASK_PORT = int(os.getenv('PORT', 5000))
    FLASK_HOST = os.getenv('HOST', '0.0.0.0')

    # Data cleanup settings
    DEFAULT_DAYS_TO_KEEP_DATA = 7
    DATA_RETENTION_DAYS = 30 # Para o BitcoinAnalyticsEngine

    # API Endpoints (if external APIs were used directly, but here they are internal)
    BINANCE_API_URL = "https://api.binance.com/api/v3/ticker/24hr"
    BINANCE_SYMBOL = 'BTCUSDT'

    # >>> ADICIONADO: Chaves de API da Binance (MUITO IMPORTANTE) <<< [!code addition]
    # Substitua 'SUA_CHAVE_API_AQUI' e 'SEU_SECRETO_API_AQUI' pelas suas credenciais reais. [!code addition]
    # Você pode obter essas chaves na sua conta Binance, na seção de Gerenciamento de API. [!code addition]
    BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', 'SUA_CHAVE_API_AQUI') # [!code addition]
    BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', 'SEU_SECRETO_API_AQUI') # [!code addition]

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
