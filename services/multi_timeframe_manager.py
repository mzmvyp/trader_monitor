# services/multi_timeframe_manager.py
from collections import deque
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import sqlite3
import threading
import time

@dataclass
class TimeframeConfig:
    """Configuração para cada timeframe"""
    interval_seconds: int
    max_history: int
    rsi_period: int
    sma_short: int
    sma_long: int
    ema_short: int = 12
    ema_long: int = 26
    min_confidence: float = 50.0
    signal_cooldown_minutes: int = 30
    stop_loss_atr_multiplier: float = 2.0

class MultiTimeframeManager:
    """Gerenciador de múltiplos timeframes para trading"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        
        # Configurações por timeframe
        self.timeframe_configs = {
            '1m': TimeframeConfig(
                interval_seconds=60,
                max_history=1440,  # 24 horas
                rsi_period=7,
                sma_short=3,
                sma_long=8,
                min_confidence=75,
                signal_cooldown_minutes=5,
                stop_loss_atr_multiplier=1.0
            ),
            '5m': TimeframeConfig(
                interval_seconds=300,
                max_history=576,  # 48 horas
                rsi_period=14,
                sma_short=9,
                sma_long=21,
                min_confidence=60,
                signal_cooldown_minutes=30,
                stop_loss_atr_multiplier=2.0
            ),
            '1h': TimeframeConfig(
                interval_seconds=3600,
                max_history=720,  # 30 dias
                rsi_period=14,
                sma_short=20,
                sma_long=50,
                min_confidence=50,
                signal_cooldown_minutes=240,
                stop_loss_atr_multiplier=3.0
            ),
            '1d': TimeframeConfig(
                interval_seconds=86400,
                max_history=365,  # 1 ano
                rsi_period=14,
                sma_short=50,
                sma_long=200,
                min_confidence=45,
                signal_cooldown_minutes=1440,
                stop_loss_atr_multiplier=4.0
            )
        }
        
        # Armazenamento de dados por timeframe e asset
        self.data_storage = {}
        self.last_aggregation = {}
        
        self._setup_database()
        self._initialize_data_storage()
    
    def _setup_database(self):
        """Configura tabelas do banco de dados"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela para dados OHLC por timeframe
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ohlc_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                close_price REAL NOT NULL,
                volume REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(asset_symbol, timeframe, timestamp)
            )
        ''')
        
        # Índices para performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ohlc_lookup 
            ON ohlc_data(asset_symbol, timeframe, timestamp DESC)
        ''')
        
        conn.commit()
        conn.close()
    
    def _initialize_data_storage(self):
        """Inicializa estruturas de dados em memória"""
        assets = ['BTC', 'ETH', 'SOL']  # Expandir conforme necessário
        
        for asset in assets:
            self.data_storage[asset] = {}
            self.last_aggregation[asset] = {}
            
            for timeframe in self.timeframe_configs:
                max_len = self.timeframe_configs[timeframe].max_history
                self.data_storage[asset][timeframe] = deque(maxlen=max_len)
                self.last_aggregation[asset][timeframe] = 0
    
    def add_tick_data(self, asset: str, price: float, volume: float = 0, timestamp: Optional[datetime] = None):
        """Adiciona dados de tick e agrega para todos os timeframes"""
        if timestamp is None:
            timestamp = datetime.now()
        
        timestamp_unix = int(timestamp.timestamp())
        
        with self.lock:
            for timeframe, config in self.timeframe_configs.items():
                self._aggregate_to_timeframe(asset, timeframe, price, volume, timestamp_unix)
    
    def _aggregate_to_timeframe(self, asset: str, timeframe: str, price: float, volume: float, timestamp_unix: int):
        """Agrega dados para um timeframe específico"""
        config = self.timeframe_configs[timeframe]
        interval = config.interval_seconds
        
        # Calcula o timestamp do período (início do candle)
        period_start = (timestamp_unix // interval) * interval
        
        # Verifica se é um novo período
        last_period = self.last_aggregation[asset][timeframe]
        
        if period_start != last_period:
            # Novo período - criar novo candle
            if last_period > 0:  # Se não é o primeiro candle
                self._finalize_previous_candle(asset, timeframe, last_period)
            
            # Iniciar novo candle
            ohlc_data = {
                'timestamp': period_start,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume,
                'period_start': datetime.fromtimestamp(period_start)
            }
            
            self.data_storage[asset][timeframe].append(ohlc_data)
            self.last_aggregation[asset][timeframe] = period_start
        else:
            # Mesmo período - atualizar candle atual
            if self.data_storage[asset][timeframe]:
                current_candle = self.data_storage[asset][timeframe][-1]
                current_candle['high'] = max(current_candle['high'], price)
                current_candle['low'] = min(current_candle['low'], price)
                current_candle['close'] = price
                current_candle['volume'] += volume
    
    def _finalize_previous_candle(self, asset: str, timeframe: str, timestamp: int):
        """Finaliza o candle anterior salvando no banco"""
        if not self.data_storage[asset][timeframe]:
            return
        
        candle = self.data_storage[asset][timeframe][-1]
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO ohlc_data 
                (asset_symbol, timeframe, timestamp, open_price, high_price, low_price, close_price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                asset, timeframe, timestamp,
                candle['open'], candle['high'], candle['low'], candle['close'], candle['volume']
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erro ao salvar candle: {e}")
    
    def get_data(self, asset: str, timeframe: str, limit: Optional[int] = None) -> List[Dict]:
        """Retorna dados para um asset e timeframe específicos"""
        with self.lock:
            if asset not in self.data_storage or timeframe not in self.data_storage[asset]:
                return []
            
            data = list(self.data_storage[asset][timeframe])
            
            if limit:
                return data[-limit:]
            return data
    
    def calculate_indicators(self, asset: str, timeframe: str) -> Dict:
        """Calcula indicadores técnicos para um timeframe específico"""
        data = self.get_data(asset, timeframe)
        
        if len(data) < 50:  # Mínimo de dados necessários
            return {'error': 'Dados insuficientes para cálculo de indicadores'}
        
        config = self.timeframe_configs[timeframe]
        prices = np.array([d['close'] for d in data])
        highs = np.array([d['high'] for d in data])
        lows = np.array([d['low'] for d in data])
        volumes = np.array([d['volume'] for d in data])
        
        indicators = {
            'current_price': prices[-1],
            'sma_short': self._calculate_sma(prices, config.sma_short),
            'sma_long': self._calculate_sma(prices, config.sma_long),
            'ema_short': self._calculate_ema(prices, config.ema_short),
            'ema_long': self._calculate_ema(prices, config.ema_long),
            'rsi': self._calculate_rsi(prices, config.rsi_period),
            'atr': self._calculate_atr(highs, lows, prices, 14),
            'volume_sma': self._calculate_sma(volumes, 20),
            'support_resistance': self._find_support_resistance(highs, lows),
            'trend_direction': self._determine_trend(prices, config.sma_short, config.sma_long),
            'timeframe': timeframe,
            'data_points': len(data)
        }
        
        return indicators
    
    def _calculate_sma(self, prices: np.ndarray, period: int) -> float:
        """Calcula média móvel simples"""
        if len(prices) < period:
            return 0.0
        return float(np.mean(prices[-period:]))
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calcula média móvel exponencial"""
        if len(prices) < period:
            return 0.0
        
        alpha = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return float(ema)
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calcula RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """Calcula Average True Range"""
        if len(highs) < period + 1:
            return 0.0
        
        tr_list = []
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        
        if len(tr_list) < period:
            return 0.0
        
        return float(np.mean(tr_list[-period:]))
    
    def _find_support_resistance(self, highs: np.ndarray, lows: np.ndarray) -> Dict:
        """Identifica níveis de suporte e resistência"""
        if len(highs) < 20:
            return {'support': 0, 'resistance': 0}
        
        # Simplificado - usar máximos e mínimos recentes
        recent_high = np.max(highs[-20:])
        recent_low = np.min(lows[-20:])
        
        return {
            'resistance': float(recent_high),
            'support': float(recent_low)
        }
    
    def _determine_trend(self, prices: np.ndarray, short_period: int, long_period: int) -> str:
        """Determina direção da tendência"""
        if len(prices) < long_period:
            return 'NEUTRO'
        
        sma_short = self._calculate_sma(prices, short_period)
        sma_long = self._calculate_sma(prices, long_period)
        
        if sma_short > sma_long * 1.005:  # 0.5% de margem
            return 'ALTISTA'
        elif sma_short < sma_long * 0.995:
            return 'BAIXISTA'
        else:
            return 'NEUTRO'
    
    def generate_multi_timeframe_signal(self, asset: str) -> Dict:
        """Gera sinal baseado em análise multi-timeframe"""
        signals = {}
        
        # Analisa cada timeframe
        for timeframe in ['5m', '1h', '1d']:  # Timeframes principais
            indicators = self.calculate_indicators(asset, timeframe)
            
            if 'error' not in indicators:
                signal = self._generate_timeframe_signal(indicators, timeframe)
                signals[timeframe] = signal
        
        # Consolida sinais
        consolidated_signal = self._consolidate_signals(signals)
        
        return {
            'asset': asset,
            'timestamp': datetime.now().isoformat(),
            'individual_signals': signals,
            'consolidated_signal': consolidated_signal,
            'multi_timeframe_analysis': True
        }
    
    def _generate_timeframe_signal(self, indicators: Dict, timeframe: str) -> Dict:
        """Gera sinal para um timeframe específico"""
        config = self.timeframe_configs[timeframe]
        
        signal = {
            'action': 'HOLD',
            'confidence': 0,
            'reasons': [],
            'timeframe': timeframe
        }
        
        # Lógica de sinal baseada nos indicadores
        price = indicators['current_price']
        sma_short = indicators['sma_short']
        sma_long = indicators['sma_long']
        rsi = indicators['rsi']
        trend = indicators['trend_direction']
        
        confidence = 0
        reasons = []
        
        # Análise de tendência
        if trend == 'ALTISTA':
            confidence += 20
            reasons.append(f'Tendência altista ({timeframe})')
        elif trend == 'BAIXISTA':
            confidence -= 20
            reasons.append(f'Tendência baixista ({timeframe})')
        
        # Análise RSI
        if timeframe == '5m':  # Day trading
            if rsi < 30:
                confidence += 25
                reasons.append('RSI oversold')
            elif rsi > 70:
                confidence -= 25
                reasons.append('RSI overbought')
        else:  # Swing trading
            if rsi < 35:
                confidence += 20
                reasons.append('RSI oversold (swing)')
            elif rsi > 65:
                confidence -= 20
                reasons.append('RSI overbought (swing)')
        
        # Análise de médias móveis
        if price > sma_short > sma_long:
            confidence += 15
            reasons.append('Médias alinhadas altista')
        elif price < sma_short < sma_long:
            confidence -= 15
            reasons.append('Médias alinhadas baixista')
        
        # Determina ação
        if confidence >= config.min_confidence:
            signal['action'] = 'BUY'
        elif confidence <= -config.min_confidence:
            signal['action'] = 'SELL'
        
        signal['confidence'] = abs(confidence)
        signal['reasons'] = reasons
        
        return signal
    
    def _consolidate_signals(self, signals: Dict) -> Dict:
        """Consolida sinais de múltiplos timeframes"""
        if not signals:
            return {'action': 'HOLD', 'confidence': 0, 'reasons': ['Sem dados suficientes']}
        
        # Pesos por timeframe
        weights = {
            '5m': 0.3,   # Entrada/timing
            '1h': 0.4,   # Tendência principal
            '1d': 0.3    # Contexto geral
        }
        
        total_confidence = 0
        total_weight = 0
        buy_signals = 0
        sell_signals = 0
        all_reasons = []
        
        for timeframe, signal in signals.items():
            weight = weights.get(timeframe, 0.2)
            
            if signal['action'] == 'BUY':
                total_confidence += signal['confidence'] * weight
                buy_signals += 1
            elif signal['action'] == 'SELL':
                total_confidence -= signal['confidence'] * weight
                sell_signals += 1
            
            total_weight += weight
            all_reasons.extend(signal['reasons'])
        
        # Normaliza confiança
        if total_weight > 0:
            normalized_confidence = total_confidence / total_weight
        else:
            normalized_confidence = 0
        
        # Determina ação final
        if normalized_confidence >= 50:
            action = 'BUY'
        elif normalized_confidence <= -50:
            action = 'SELL'
        else:
            action = 'HOLD'
        
        return {
            'action': action,
            'confidence': abs(normalized_confidence),
            'reasons': all_reasons,
            'timeframes_analyzed': len(signals),
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'consensus': buy_signals > sell_signals * 1.5 or sell_signals > buy_signals * 1.5
        }
    
    def get_timeframe_data_summary(self, asset: str) -> Dict:
        """Retorna resumo dos dados disponíveis por timeframe"""
        summary = {}
        
        for timeframe in self.timeframe_configs:
            data = self.get_data(asset, timeframe)
            config = self.timeframe_configs[timeframe]
            
            if data:
                first_timestamp = data[0]['period_start']
                last_timestamp = data[-1]['period_start']
                duration = last_timestamp - first_timestamp
            else:
                first_timestamp = None
                last_timestamp = None
                duration = timedelta(0)
            
            summary[timeframe] = {
                'data_points': len(data),
                'max_capacity': config.max_history,
                'usage_percentage': (len(data) / config.max_history) * 100,
                'first_data': first_timestamp.isoformat() if first_timestamp else None,
                'last_data': last_timestamp.isoformat() if last_timestamp else None,
                'coverage_duration': str(duration),
                'interval_seconds': config.interval_seconds
            }
        
        return summary

# Uso do sistema
if __name__ == "__main__":
    # Exemplo de uso
    manager = MultiTimeframeManager()
    
    # Simular alguns ticks de dados
    import random
    base_price = 50000  # BTC
    
    for i in range(1000):
        # Simular variação de preço
        price_change = random.uniform(-100, 100)
        price = base_price + price_change
        volume = random.uniform(0.1, 2.0)
        
        manager.add_tick_data('BTC', price, volume)
        
        # Simular tempo passando
        time.sleep(0.01)  # 10ms por tick
    
    # Testar análise multi-timeframe
    signal = manager.generate_multi_timeframe_signal('BTC')
    print("Sinal Multi-Timeframe:")
    print(f"Ação: {signal['consolidated_signal']['action']}")
    print(f"Confiança: {signal['consolidated_signal']['confidence']:.1f}%")
    print(f"Razões: {signal['consolidated_signal']['reasons']}")
    
    # Verificar dados disponíveis
    summary = manager.get_timeframe_data_summary('BTC')
    print("\nResumo dos Dados:")
    for tf, info in summary.items():
        print(f"{tf}: {info['data_points']} pontos ({info['usage_percentage']:.1f}% do limite)")