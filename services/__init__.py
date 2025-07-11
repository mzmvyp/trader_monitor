# services/__init__.py - CORREÇÃO
"""
Services package for Multi-Timeframe Trading System
APENAS importar o que está na pasta services/
"""

try:
    from .multi_timeframe_manager import MultiTimeframeManager
    from .websocket_multi_adapter import WebSocketMultiAdapter
    from .websocket_integration import ExistingSystemIntegration
    
    __all__ = [
        'MultiTimeframeManager',
        'WebSocketMultiAdapter', 
        'ExistingSystemIntegration'
    ]
    
    print("[SERVICES] Multi-Timeframe services carregados ✅")
    
except ImportError as e:
    print(f"[SERVICES] Aviso: Alguns componentes multi-timeframe não disponíveis: {e}")
    __all__ = []

# strategies/__init__.py - CORREÇÃO
"""
Trading Strategies package - APENAS estratégias
"""

try:
    from strategies.scalp_strategy import ScalpStrategy
    from strategies.day_trade_strategy import DayTradeStrategy
    from strategies.swing_strategy import SwingStrategy
    
    __all__ = [
        'ScalpStrategy',
        'DayTradeStrategy',
        'SwingStrategy'
    ]
    
    print("[STRATEGIES] Estratégias multi-timeframe carregadas ✅")
    
except ImportError as e:
    print(f"[STRATEGIES] Aviso: Algumas estratégias não disponíveis: {e}")
    __all__ = []

# routes/__init__.py - CORREÇÃO
"""
Routes package - APENAS rotas
"""

try:
    from routes.multi_strategy_routes import setup_multi_strategy_routes
    
    __all__ = [
        'setup_multi_strategy_routes'
    ]
    
    print("[ROUTES] Rotas multi-timeframe carregadas ✅")
    
except ImportError as e:
    print(f"[ROUTES] Aviso: Rotas multi-timeframe não disponíveis: {e}")
    __all__ = []