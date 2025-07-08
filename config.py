# your_project/config.py - ADICIONAR estas seções ao arquivo existente

import os

class Config:
    """
    Configuration class for the Bitcoin Trading System.
    Manages various settings for the application.
    """
    
    # === EXISTENTE: Database paths ===
    DATA_DIR = 'data'
    TRADING_ANALYZER_DB = os.path.join(DATA_DIR, 'trading_analyzer.db')
    BITCOIN_STREAM_DB = os.path.join(DATA_DIR, 'bitcoin_stream.db')
    
    # === NOVO: Multi-Asset Database Configuration ===
    # Asset-specific databases
    ETH_STREAM_DB = os.path.join(DATA_DIR, 'eth_stream.db')
    SOL_STREAM_DB = os.path.join(DATA_DIR, 'sol_stream.db')
    ETH_TRADING_DB = os.path.join(DATA_DIR, 'eth_trading.db')
    SOL_TRADING_DB = os.path.join(DATA_DIR, 'sol_trading.db')
    
    # Multi-asset consolidated database
    MULTI_ASSET_DB = os.path.join(DATA_DIR, 'multi_asset.db')
    
    # === NOVO: Asset Configuration ===
    SUPPORTED_ASSETS = {
        'BTC': {
            'symbol': 'BTCUSDT',
            'name': 'Bitcoin',
            'precision': 2,
            'min_price': 20000,
            'max_price': 200000,
            'stream_db': 'BITCOIN_STREAM_DB',
            'trading_db': 'TRADING_ANALYZER_DB',
            'color': '#f7931a',
            'icon': 'fab fa-bitcoin'
        },
        'ETH': {
            'symbol': 'ETHUSDT', 
            'name': 'Ethereum',
            'precision': 2,
            'min_price': 1000,
            'max_price': 10000,
            'stream_db': 'ETH_STREAM_DB',
            'trading_db': 'ETH_TRADING_DB',
            'color': '#627eea',
            'icon': 'fab fa-ethereum'
        },
        'SOL': {
            'symbol': 'SOLUSDT',
            'name': 'Solana', 
            'precision': 2,
            'min_price': 10,
            'max_price': 1000,
            'stream_db': 'SOL_STREAM_DB',
            'trading_db': 'SOL_TRADING_DB',
            'color': '#9945ff',
            'icon': 'fas fa-sun'
        }
    }
    
    # Default asset for backwards compatibility
    DEFAULT_ASSET = 'BTC'
    
    # === EXISTENTE: Logging configuration ===
    LOG_FILE = os.path.join(DATA_DIR, 'trading_system.log')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # === NOVO: Multi-Asset Streamer Settings ===
    MULTI_ASSET_FETCH_INTERVAL_SECONDS = 300  # 5 minutes
    MULTI_ASSET_MAX_QUEUE_SIZE = 1000
    
    # Asset-specific intervals (podem ser diferentes)
    ASSET_INTERVALS = {
        'BTC': 300,  # 5 minutes - existing
        'ETH': 300,  # 5 minutes  
        'SOL': 300   # 5 minutes
    }
    
    # === EXISTENTE: Bitcoin Stream settings (manter para compatibilidade) ===
    BITCOIN_STREAM_MAX_QUEUE_SIZE = 1000
    BITCOIN_STREAM_FETCH_INTERVAL_SECONDS = 300
    BITCOIN_STREAM_MAX_CONSECUTIVE_ERRORS = 5
    AUTO_START_STREAM = True
    
    # === EXISTENTE: outros configs... ===
    BITCOIN_PROCESSOR_BATCH_SIZE = 20
    TRADING_ANALYZER_UPDATE_INTERVAL_SECONDS = 60
    ANALYZER_PROCESS_INTERVAL_SECONDS = 5
    
    # === NOVO: Multi-Asset Analytics ===
    MULTI_ASSET_COMPARISON_TIMEFRAMES = ['1h', '24h', '7d', '30d']
    CORRELATION_ANALYSIS_ENABLED = True
    PORTFOLIO_REBALANCING_ENABLED = False  # Future feature
    
    # === EXISTENTE: Flask app settings ===
    FLASK_DEBUG_MODE = os.getenv('DEBUG', 'false').lower() == 'true'
    FLASK_PORT = int(os.getenv('PORT', 5000))
    FLASK_HOST = os.getenv('HOST', '0.0.0.0')

    # === EXISTENTE: API Endpoints ===
    BINANCE_API_URL = "https://api.binance.com/api/v3/ticker/24hr"
    BINANCE_SYMBOL = 'BTCUSDT'  # Keep for backwards compatibility
    
    # === NOVO: Métodos Helper para Multi-Asset ===
    def get_asset_config(self, asset_symbol):
        """Retorna configuração específica do asset"""
        return self.SUPPORTED_ASSETS.get(asset_symbol.upper(), self.SUPPORTED_ASSETS[self.DEFAULT_ASSET])
    
    def get_asset_db_path(self, asset_symbol, db_type='stream'):
        """Retorna caminho do banco para o asset"""
        asset_config = self.get_asset_config(asset_symbol)
        if db_type == 'stream':
            db_attr = asset_config['stream_db']
        elif db_type == 'trading':
            db_attr = asset_config['trading_db']
        else:
            raise ValueError(f"Unknown db_type: {db_type}")
        return getattr(self, db_attr)
    
    def get_supported_asset_symbols(self):
        """Retorna lista de símbolos suportados"""
        return list(self.SUPPORTED_ASSETS.keys())
    
    def is_asset_supported(self, asset_symbol):
        """Verifica se o asset é suportado"""
        return asset_symbol.upper() in self.SUPPORTED_ASSETS

    def __init__(self):
        """
        Initializes the Config class and ensures necessary directories exist.
        """
        os.makedirs(self.DATA_DIR, exist_ok=True)
        # Criar diretórios para assets específicos se necessário
        for asset in self.SUPPORTED_ASSETS.values():
            stream_db_path = getattr(self, asset['stream_db'])
            trading_db_path = getattr(self, asset['trading_db'])
            os.makedirs(os.path.dirname(stream_db_path), exist_ok=True)
            os.makedirs(os.path.dirname(trading_db_path), exist_ok=True)

# Instantiate the config for easy import
app_config = Config()