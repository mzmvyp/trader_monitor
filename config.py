# your_project/config.py - ATUALIZADO com Multi-Timeframe

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
    
    # === ADICIONAR: Variáveis que estão faltando (causando erros críticos) ===
    MIN_EXPECTED_PRICE = 0.01  # Preço mínimo geral
    MAX_EXPECTED_PRICE = 1000000  # Preço máximo geral  
    PRICE_CHANGE_THRESHOLD_PCT = 0.10  # 10% threshold para mudanças de preço
    
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
    
    # === NOVO: CONFIGURAÇÕES MULTI-TIMEFRAME ===
    
    # Timeframes Configuration
    MULTI_TIMEFRAME_CONFIG = {
        'timeframes': {
            '1m': {
                'interval_seconds': 60,
                'max_history': 1440,  # 24 horas
                'strategy': 'scalp',
                'description': 'Scalping - 1 minuto'
            },
            '5m': {
                'interval_seconds': 300,
                'max_history': 576,   # 48 horas  
                'strategy': 'day_trade',
                'description': 'Day Trading - 5 minutos (ATUAL)',
                'is_primary': True     # Marca como timeframe principal atual
            },
            '1h': {
                'interval_seconds': 3600,
                'max_history': 720,   # 30 dias
                'strategy': 'swing_trade',
                'description': 'Swing Trading - 1 hora'
            }
        },
        
        # Configurações por estratégia
        'strategies': {
            'scalp': {
                'timeframe': '1m',
                'rsi_period': 7,
                'rsi_overbought': 75,
                'rsi_oversold': 25,
                'sma_short': 3,
                'sma_long': 8,
                'min_confidence': 75,
                'signal_cooldown_minutes': 5,
                'stop_loss_atr_multiplier': 1.0,
                'target_multipliers': [0.5, 1.0, 1.5],
                'hold_time': '1-5 minutos'
            },
            
            'day_trade': {
                # === SUAS CONFIGURAÇÕES ATUAIS PRESERVADAS ===
                'timeframe': '5m',
                'rsi_period': 14,
                'rsi_overbought': 70,
                'rsi_oversold': 30,
                'sma_short': 9,
                'sma_long': 21,
                'min_confidence': 60,
                'signal_cooldown_minutes': 30,  # Melhorado dos 60 min atuais
                'stop_loss_atr_multiplier': 2.0,
                'target_multipliers': [1.0, 2.0, 3.0],
                'hold_time': '30min - 4h',
                
                # Manter compatibilidade com seus padrões
                'elliott_waves_enabled': True,
                'double_bottom_enabled': True,
                'oco_patterns_enabled': True,
                'ocoi_patterns_enabled': True
            },
            
            'swing_trade': {
                'timeframe': '1h',
                'rsi_period': 14,
                'rsi_overbought': 65,
                'rsi_oversold': 35,
                'sma_short': 20,
                'sma_long': 50,
                'min_confidence': 50,
                'signal_cooldown_minutes': 240,  # 4 horas
                'stop_loss_atr_multiplier': 3.5,
                'target_multipliers': [1.5, 2.5, 4.0],
                'hold_time': '3-7 dias'
            }
        }
    }
    
    # Configurações de integração
    INTEGRATION_CONFIG = {
        'maintain_current_system': True,
        'primary_timeframe': '5m',  # Seu timeframe atual
        'fallback_to_current': True,
        'extend_price_history': True,
        'current_history_limit': 200,  # Seu limite atual
        'new_history_limits': {
            '1m': 1440,  # 24h
            '5m': 576,   # 48h  
            '1h': 720    # 30 dias
        },
        'enhance_websocket': True,
        'preserve_original_flow': True,
        'expose_multi_endpoints': True,
        'maintain_current_endpoints': True
    }
    
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

    # === NOVO: Métodos Helper para Multi-Timeframe ===
    def get_strategy_config(self, strategy_name):
        """Retorna configuração de uma estratégia específica"""
        return self.MULTI_TIMEFRAME_CONFIG['strategies'].get(strategy_name, {})
    
    def get_timeframe_config(self, timeframe):
        """Retorna configuração de um timeframe específico"""
        return self.MULTI_TIMEFRAME_CONFIG['timeframes'].get(timeframe, {})
    
    def get_current_day_trade_config(self):
        """Retorna configurações atuais de day trading (compatibilidade)"""
        return self.get_strategy_config('day_trade')
    
    def is_multi_timeframe_enabled(self):
        """Verifica se o sistema multi-timeframe está habilitado"""
        return True  # Sempre habilitado agora
    
    def get_primary_timeframe(self):
        """Retorna o timeframe primário (atual)"""
        return self.INTEGRATION_CONFIG['primary_timeframe']
    
    def get_all_timeframes(self):
        """Retorna todos os timeframes suportados"""
        return list(self.MULTI_TIMEFRAME_CONFIG['timeframes'].keys())
    
    def get_all_strategies(self):
        """Retorna todas as estratégias suportadas"""
        return list(self.MULTI_TIMEFRAME_CONFIG['strategies'].keys())

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

# === NOVO: Configurações específicas para compatibilidade ===

# Configurações atuais do day trading (para fácil acesso)
CURRENT_DAY_TRADE_CONFIG = app_config.get_strategy_config('day_trade')

# Mapeamento de compatibilidade
RSI_PERIOD = CURRENT_DAY_TRADE_CONFIG['rsi_period']  # 14
RSI_OVERBOUGHT = CURRENT_DAY_TRADE_CONFIG['rsi_overbought']  # 70
RSI_OVERSOLD = CURRENT_DAY_TRADE_CONFIG['rsi_oversold']  # 30
SMA_SHORT = CURRENT_DAY_TRADE_CONFIG['sma_short']  # 9
SMA_LONG = CURRENT_DAY_TRADE_CONFIG['sma_long']  # 21
MIN_CONFIDENCE = CURRENT_DAY_TRADE_CONFIG['min_confidence']  # 60
SIGNAL_COOLDOWN_MINUTES = CURRENT_DAY_TRADE_CONFIG['signal_cooldown_minutes']  # 30

# === NOVO: Helper functions ===

def get_current_config():
    """Retorna configuração atual para compatibilidade"""
    return {
        'rsi_period': RSI_PERIOD,
        'rsi_overbought': RSI_OVERBOUGHT,
        'rsi_oversold': RSI_OVERSOLD,
        'sma_short': SMA_SHORT,
        'sma_long': SMA_LONG,
        'min_confidence': MIN_CONFIDENCE,
        'signal_cooldown_minutes': SIGNAL_COOLDOWN_MINUTES,
        'timeframe': '5m',
        'strategy': 'day_trade'
    }

def get_multi_timeframe_summary():
    """Retorna resumo do sistema multi-timeframe"""
    return {
        'enabled': True,
        'timeframes': app_config.get_all_timeframes(),
        'strategies': app_config.get_all_strategies(),
        'primary_timeframe': app_config.get_primary_timeframe(),
        'assets_supported': app_config.get_supported_asset_symbols()
    }

def get_integration_status():
    """Retorna status da integração"""
    return {
        'multi_timeframe_enabled': True,
        'current_system_preserved': True,
        'primary_timeframe': '5m',
        'day_trading_config_maintained': True,
        'elliott_waves_compatible': True,
        'double_bottom_compatible': True,
        'websocket_enhanced': True,
        'fallback_available': True
    }
