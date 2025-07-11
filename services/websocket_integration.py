# services/websocket_integration.py - INTEGRAÇÃO COM SEU SISTEMA ATUAL

import json
from datetime import datetime
from typing import Dict, Any, Optional

class ExistingSystemIntegration:
    """
    Integração com seu sistema atual de WebSocket
    Mantém 100% compatibilidade + adiciona multi-timeframe
    """
    
    def __init__(self, multi_manager, multi_adapter):
        self.multi_manager = multi_manager
        self.multi_adapter = multi_adapter
        
        # Configurações baseadas no seu paste.txt
        self.current_config = {
            'rsi_period': 14,
            'sma_short': 9,
            'sma_long': 21,
            'fetch_interval': 300,  # 5 minutos
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'min_confidence': 60,
            'signal_cooldown_minutes': 60
        }
        
        # Assets do seu sistema atual
        self.supported_assets = ['BTC', 'ETH', 'SOL']
    
    def enhance_websocket_handler(self, original_handler):
        """
        Wrapper para seu método WebSocket atual
        Adiciona funcionalidade multi-timeframe SEM quebrar nada
        """
        
        def enhanced_handler(message):
            try:
                # === 1. EXECUTAR SEU CÓDIGO ATUAL (não mexer) ===
                original_result = original_handler(message)
                
                # === 2. ADICIONAR MULTI-TIMEFRAME ===
                symbol = self._extract_symbol(message)
                price_data = self._extract_price_data(message)
                
                if symbol and price_data:
                    # Processar multi-timeframe
                    multi_result = self.multi_adapter.on_price_update(symbol, price_data)
                    
                    # Combinar resultados
                    enhanced_result = self._combine_results(original_result, multi_result)
                    
                    return enhanced_result
                
                return original_result
                
            except Exception as e:
                print(f"❌ Erro na integração multi-timeframe: {e}")
                return original_result  # Fallback para seu sistema atual
        
        return enhanced_handler
    
    def _extract_symbol(self, message: Dict) -> Optional[str]:
        """Extrai símbolo da mensagem Binance"""
        try:
            # Formato Binance: BTCUSDT -> BTC
            raw_symbol = message.get('s', '').replace('USDT', '')
            
            if raw_symbol in self.supported_assets:
                return raw_symbol
                
        except Exception as e:
            print(f"Erro ao extrair símbolo: {e}")
        
        return None
    
    def _extract_price_data(self, message: Dict) -> Optional[Dict]:
        """Extrai dados de preço da mensagem Binance"""
        try:
            price = float(message.get('p', 0))
            volume = float(message.get('q', 0))
            
            if price > 0:
                return {
                    'price': price,
                    'volume': volume,
                    'timestamp': datetime.now(),
                    'bid': float(message.get('b', 0)),
                    'ask': float(message.get('a', 0)),
                    'high': float(message.get('h', 0)),
                    'low': float(message.get('l', 0))
                }
                
        except Exception as e:
            print(f"Erro ao extrair dados de preço: {e}")
        
        return None
    
    def _combine_results(self, original_result, multi_result):
        """Combina resultados do seu sistema + multi-timeframe"""
        
        if not multi_result:
            return original_result
        
        # Estrutura combinada
        combined = {
            'timestamp': datetime.now().isoformat(),
            'original_system': original_result,
            'multi_timeframe': {
                'asset': multi_result.get('asset'),
                'current_price': multi_result.get('current_price'),
                'timeframes_analyzed': multi_result.get('timeframes_analyzed', 0),
                'new_signals': multi_result.get('new_signals', {}),
                'all_signals': multi_result.get('signals', {})
            }
        }
        
        # Log para debug
        if multi_result.get('new_signals'):
            asset = multi_result.get('asset', 'UNKNOWN')
            signals = multi_result['new_signals']
            
            print(f"📊 {asset} - Novos sinais multi-timeframe:")
            for strategy, signal in signals.items():
                action = signal.get('action', 'HOLD')
                confidence = signal.get('confidence', 0)
                print(f"   {strategy.upper()}: {action} ({confidence:.0f}%)")
        
        return combined

# === EXEMPLO DE INTEGRAÇÃO COM SEU CÓDIGO ATUAL ===

def integrate_with_your_websocket():
    """
    Exemplo de como integrar com seu código WebSocket atual
    """
    
    # Seus imports atuais
    from services.multi_timeframe_manager import MultiTimeframeManager
    from services.websocket_multi_adapter import WebSocketMultiAdapter
    
    # === INICIALIZAÇÃO (adicionar no seu app.py) ===
    def setup_multi_timeframe_integration(app):
        """Adicionar esta função no seu app.py"""
        
        print("🚀 Configurando integração multi-timeframe...")
        
        # 1. Inicializar componentes
        multi_manager = MultiTimeframeManager()
        multi_adapter = WebSocketMultiAdapter(multi_manager, app)
        
        # 2. Criar integração
        integration = ExistingSystemIntegration(multi_manager, multi_adapter)
        
        # 3. Armazenar globalmente
        app.multi_manager = multi_manager
        app.multi_adapter = multi_adapter
        app.multi_integration = integration
        
        print("✅ Integração multi-timeframe configurada!")
        
        return integration
    
    # === MODIFICAÇÃO DO SEU WEBSOCKET (exemplo) ===
    """
    No seu arquivo de WebSocket atual, fazer assim:
    
    # ANTES (seu código atual):
    def on_message(self, ws, message):
        data = json.loads(message)
        self.process_ticker_data(data)  # Seu método atual
    
    # DEPOIS (com integração):
    def on_message(self, ws, message):
        data = json.loads(message)
        
        # Seu código atual (manter)
        original_result = self.process_ticker_data(data)
        
        # NOVA LINHA: Adicionar multi-timeframe
        if hasattr(app, 'multi_integration'):
            enhanced_result = app.multi_integration.enhance_websocket_handler(
                lambda msg: original_result
            )(data)
        
        return enhanced_result or original_result
    """

# === ADAPTADOR PARA SEUS INDICADORES ATUAIS ===

class IndicatorAdapter:
    """Adapta seus indicadores atuais para formato multi-timeframe"""
    
    @staticmethod
    def convert_your_data_to_multi_format(your_data):
        """
        Converte dados do seu formato atual para multi-timeframe
        
        Args:
            your_data: Seus dados atuais (formato atual do seu sistema)
            
        Returns:
            Dict no formato esperado pelo sistema multi-timeframe
        """
        
        return {
            'current_price': your_data.get('price', 0),
            'rsi': your_data.get('rsi', 50),
            'sma_short': your_data.get('sma_9', 0),      # SMA9
            'sma_long': your_data.get('sma_21', 0),      # SMA21
            'ema_short': your_data.get('ema_12', 0),
            'ema_long': your_data.get('ema_26', 0),
            'atr': your_data.get('atr', 0),
            'trend_direction': your_data.get('trend', 'NEUTRO'),
            'data_points': len(your_data.get('price_history', [])),
            'support_resistance': {
                'support': your_data.get('support_level', 0),
                'resistance': your_data.get('resistance_level', 0)
            },
            'volume_sma': your_data.get('volume_avg', 0),
            'current_volume': your_data.get('volume', 0),
            
            # Seus padrões específicos
            'elliott_wave_data': your_data.get('elliott_waves', {}),
            'double_bottom_data': your_data.get('double_bottom', {}),
            'oco_data': your_data.get('oco_patterns', {}),
            'ocoi_data': your_data.get('ocoi_patterns', {})
        }
    
    @staticmethod
    def convert_multi_signal_to_your_format(multi_signal):
        """
        Converte sinal multi-timeframe para seu formato atual
        """
        
        if not multi_signal:
            return None
        
        return {
            'action': multi_signal.get('action', 'HOLD'),
            'confidence': multi_signal.get('confidence', 0),
            'reasons': multi_signal.get('reasons', []),
            'entry_price': multi_signal.get('entry_price', 0),
            'stop_loss': multi_signal.get('stop_loss', 0),
            'targets': multi_signal.get('targets', []),
            'timeframe': multi_signal.get('timeframe', '5m'),
            'strategy': multi_signal.get('strategy', 'DAY_TRADE'),
            'hold_time': multi_signal.get('hold_time_expected', ''),
            'risk_reward': multi_signal.get('risk_reward', 0),
            
            # Metadados para seu sistema
            'multi_timeframe_enhanced': True,
            'original_system_compatible': True
        }

# === EXEMPLO COMPLETO DE INTEGRAÇÃO ===

"""
EXEMPLO: Como modificar seu arquivo principal

# === NO SEU APP.PY ===

# Importações existentes + novas
from services.websocket_integration import setup_multi_timeframe_integration

# Após criar app Flask
app = Flask(__name__)
# ...suas configurações atuais...

# NOVA SEÇÃO: Multi-timeframe
integration = setup_multi_timeframe_integration(app)

# === NO SEU WEBSOCKET ===

# Modificar método que processa dados Binance
def process_binance_message(self, message):
    # Seu código atual (MANTER TUDO)
    current_result = self.your_current_processing(message)
    
    # ADICIONAR: Multi-timeframe (1 linha)
    if hasattr(app, 'multi_integration'):
        enhanced = app.multi_integration._combine_results(
            current_result,
            app.multi_adapter.on_price_update(
                symbol=self.extract_symbol(message),
                price_data=self.extract_price_data(message)
            )
        )
        return enhanced
    
    return current_result
"""