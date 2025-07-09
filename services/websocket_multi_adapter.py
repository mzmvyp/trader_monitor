# services/websocket_multi_adapter.py
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class StrategySignal:
    """Estrutura padronizada para sinais de estratégia"""
    strategy: str
    timeframe: str
    action: str  # BUY, SELL, HOLD
    confidence: float
    reasons: list
    hold_time_expected: str
    stop_loss: float
    targets: list
    timestamp: datetime
    asset: str

class WebSocketMultiAdapter:
    """Adaptador para integrar WebSocket atual com sistema Multi-Timeframe"""
    
    def __init__(self, multi_manager, current_app=None):
        self.multi_manager = multi_manager
        self.current_app = current_app
        self.lock = threading.Lock()
        
        # Cache de sinais para evitar spam
        self.last_signals = {}
        self.signal_cooldowns = {
            'scalp': 300,      # 5 minutos
            'day_trade': 1800, # 30 minutos
            'swing_trade': 14400  # 4 horas
        }
        
        # Importar estratégias
        from strategies.scalp_strategy import ScalpStrategy
        from strategies.day_trade_strategy import DayTradeStrategy
        from strategies.swing_strategy import SwingStrategy
        
        self.strategies = {
            'scalp': ScalpStrategy(),
            'day_trade': DayTradeStrategy(),
            'swing_trade': SwingStrategy()
        }
        
        # WebSocket callbacks
        self.signal_callbacks = []
        
    def register_signal_callback(self, callback):
        """Registra callback para receber sinais"""
        self.signal_callbacks.append(callback)
    
    def on_price_update(self, asset: str, price_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intercepta dados do WebSocket atual e processa multi-timeframe
        
        Args:
            asset: BTC, ETH, SOL, etc.
            price_data: {
                'price': float,
                'volume': float (opcional),
                'timestamp': datetime (opcional),
                'bid': float (opcional),
                'ask': float (opcional)
            }
        
        Returns:
            Dict com sinais de todas as estratégias
        """
        
        try:
            # 1. Alimentar sistema multi-timeframe
            timestamp = price_data.get('timestamp', datetime.now())
            price = float(price_data['price'])
            volume = float(price_data.get('volume', 0))
            
            self.multi_manager.add_tick_data(
                asset=asset,
                price=price,
                volume=volume,
                timestamp=timestamp
            )
            
            # 2. Gerar sinais para as 3 estratégias
            all_signals = self._generate_all_strategy_signals(asset, price, timestamp)
            
            # 3. Filtrar sinais por cooldown
            filtered_signals = self._filter_signals_by_cooldown(asset, all_signals)
            
            # 4. Broadcast para interface web
            if filtered_signals:
                self._broadcast_signals_to_web(asset, filtered_signals, price_data)
            
            # 5. Retornar resultado completo
            return {
                'asset': asset,
                'current_price': price,
                'timestamp': timestamp.isoformat(),
                'signals': all_signals,
                'new_signals': filtered_signals,
                'timeframes_analyzed': len(all_signals)
            }
            
        except Exception as e:
            return {
                'error': f"Erro no processamento multi-timeframe: {str(e)}",
                'asset': asset,
                'timestamp': datetime.now().isoformat()
            }
    
    def _generate_all_strategy_signals(self, asset: str, current_price: float, timestamp: datetime) -> Dict[str, Any]:
        """Gera sinais para todas as estratégias simultaneamente"""
        results = {}
        
        try:
            # SCALPING (1m)
            scalp_indicators = self.multi_manager.calculate_indicators(asset, '1m')
            if 'error' not in scalp_indicators and scalp_indicators.get('data_points', 0) >= 10:
                scalp_signal = self.strategies['scalp'].analyze(scalp_indicators, current_price)
                if scalp_signal:
                    results['scalp'] = scalp_signal
            
            # DAY TRADING (5m) - SUA LÓGICA ATUAL
            day_indicators = self.multi_manager.calculate_indicators(asset, '5m')
            if 'error' not in day_indicators and day_indicators.get('data_points', 0) >= 20:
                day_signal = self.strategies['day_trade'].analyze(day_indicators, current_price)
                if day_signal:
                    results['day_trade'] = day_signal
            
            # SWING TRADING (1h)
            swing_indicators = self.multi_manager.calculate_indicators(asset, '1h')
            if 'error' not in swing_indicators and swing_indicators.get('data_points', 0) >= 50:
                swing_signal = self.strategies['swing_trade'].analyze(swing_indicators, current_price)
                if swing_signal:
                    results['swing_trade'] = swing_signal
                    
        except Exception as e:
            results['error'] = f"Erro na geração de sinais: {str(e)}"
        
        return results
    
    def _filter_signals_by_cooldown(self, asset: str, all_signals: Dict[str, Any]) -> Dict[str, Any]:
        """Filtra sinais baseado no cooldown para evitar spam"""
        filtered = {}
        current_time = datetime.now()
        
        for strategy_name, signal in all_signals.items():
            if strategy_name == 'error':
                continue
                
            # Verificar se o sinal é actionable (não HOLD)
            if signal.get('action') == 'HOLD':
                continue
            
            # Verificar cooldown
            last_signal_key = f"{asset}_{strategy_name}"
            last_signal_time = self.last_signals.get(last_signal_key, datetime.min)
            cooldown_seconds = self.signal_cooldowns.get(strategy_name, 1800)
            
            if (current_time - last_signal_time).total_seconds() >= cooldown_seconds:
                filtered[strategy_name] = signal
                self.last_signals[last_signal_key] = current_time
        
        return filtered
    
    def _broadcast_signals_to_web(self, asset: str, signals: Dict[str, Any], price_data: Dict[str, Any]):
        """Envia sinais para interface web via WebSocket/SocketIO"""
        
        if not signals:
            return
        
        web_data = {
            'type': 'multi_strategy_signals',
            'asset': asset,
            'current_price': price_data['price'],
            'timestamp': datetime.now().isoformat(),
            'signals': signals,
            'market_data': {
                'volume': price_data.get('volume', 0),
                'bid': price_data.get('bid', 0),
                'ask': price_data.get('ask', 0)
            }
        }
        
        # Chamar callbacks registrados
        for callback in self.signal_callbacks:
            try:
                callback(web_data)
            except Exception as e:
                print(f"Erro no callback: {e}")
        
        # Se tiver Flask-SocketIO integrado
        if self.current_app and hasattr(self.current_app, 'socketio'):
            self.current_app.socketio.emit('multi_strategy_update', web_data)
    
    def get_current_signals_summary(self, asset: str) -> Dict[str, Any]:
        """Retorna resumo dos sinais atuais para um asset"""
        summary = {
            'asset': asset,
            'timestamp': datetime.now().isoformat(),
            'strategies': {}
        }
        
        for strategy_name in ['scalp', 'day_trade', 'swing_trade']:
            timeframe = {'scalp': '1m', 'day_trade': '5m', 'swing_trade': '1h'}[strategy_name]
            
            indicators = self.multi_manager.calculate_indicators(asset, timeframe)
            if 'error' not in indicators:
                signal = self.strategies[strategy_name].analyze(indicators, indicators.get('current_price', 0))
                summary['strategies'][strategy_name] = {
                    'signal': signal,
                    'indicators': {
                        'rsi': indicators.get('rsi', 0),
                        'trend': indicators.get('trend_direction', 'NEUTRO'),
                        'sma_short': indicators.get('sma_short', 0),
                        'sma_long': indicators.get('sma_long', 0),
                        'data_points': indicators.get('data_points', 0)
                    }
                }
        
        return summary
    
    def force_signal_generation(self, asset: str, strategy: str = None) -> Dict[str, Any]:
        """Força geração de sinal para debug/teste"""
        
        if strategy and strategy in self.strategies:
            # Gerar sinal específico
            timeframe = {'scalp': '1m', 'day_trade': '5m', 'swing_trade': '1h'}[strategy]
            indicators = self.multi_manager.calculate_indicators(asset, timeframe)
            
            if 'error' not in indicators:
                signal = self.strategies[strategy].analyze(indicators, indicators.get('current_price', 0))
                return {strategy: signal}
            else:
                return {'error': f'Dados insuficientes para {strategy}'}
        else:
            # Gerar todos os sinais
            current_price = 0
            indicators_5m = self.multi_manager.calculate_indicators(asset, '5m')
            if 'error' not in indicators_5m:
                current_price = indicators_5m.get('current_price', 0)
            
            return self._generate_all_strategy_signals(asset, current_price, datetime.now())

# EXEMPLO DE INTEGRAÇÃO COM SEU WEBSOCKET ATUAL
class ExampleIntegration:
    """Exemplo de como integrar com seu WebSocket existente"""
    
    def __init__(self):
        # Seus objetos atuais
        self.multi_manager = None  # Seu MultiTimeframeManager
        self.adapter = None        # WebSocketMultiAdapter
        
    def setup_integration(self):
        """Configuração inicial"""
        from services.multi_timeframe_manager import MultiTimeframeManager
        
        # Inicializar sistemas
        self.multi_manager = MultiTimeframeManager()
        self.adapter = WebSocketMultiAdapter(self.multi_manager)
        
        # Registrar callback para sinais
        self.adapter.register_signal_callback(self.on_new_signal)
    
    def on_binance_websocket_message(self, message):
        """Seu método atual de WebSocket - ADAPTAR AQUI"""
        
        # Extrair dados da mensagem Binance
        symbol = message.get('s', '').replace('USDT', '')  # BTCUSDT -> BTC
        price = float(message.get('p', 0))
        volume = float(message.get('q', 0))
        
        # Converter para formato padrão
        price_data = {
            'price': price,
            'volume': volume,
            'timestamp': datetime.now()
        }
        
        # NOVA LINHA: Processar com multi-timeframe
        result = self.adapter.on_price_update(symbol, price_data)
        
        # Continuar com sua lógica atual...
        # self.process_day_trading_signal(symbol, price_data)  # Sua lógica atual
        
        return result
    
    def on_new_signal(self, signal_data):
        """Callback para novos sinais multi-timeframe"""
        
        # Aqui você pode:
        # 1. Salvar no banco
        # 2. Enviar para interface web
        # 3. Executar ordens automáticas
        # 4. Enviar alertas
        
        print(f"Novo sinal multi-timeframe: {signal_data['asset']}")
        for strategy, signal in signal_data['signals'].items():
            if signal.get('action') != 'HOLD':
                print(f"{strategy.upper()}: {signal['action']} - {signal['confidence']}%")

# PONTO DE INTEGRAÇÃO PRINCIPAL
def integrate_with_existing_websocket(your_websocket_manager, your_app):
    """
    Função principal para integrar com seu sistema atual
    
    Args:
        your_websocket_manager: Seu manager de WebSocket atual
        your_app: Sua aplicação Flask/FastAPI
    """
    
    # 1. Inicializar sistema multi-timeframe
    from services.multi_timeframe_manager import MultiTimeframeManager
    multi_manager = MultiTimeframeManager()
    
    # 2. Criar adaptador
    adapter = WebSocketMultiAdapter(multi_manager, your_app)
    
    # 3. Modificar seu WebSocket atual para chamar o adaptador
    # EXEMPLO:
    # your_websocket_manager.add_callback(adapter.on_price_update)
    
    return adapter, multi_manager