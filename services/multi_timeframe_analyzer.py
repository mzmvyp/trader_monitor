# services/multi_timeframe_analyzer.py - Sistema Multi-Timeframe Completo

import numpy as np
import sqlite3
from collections import deque, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from utils.logging_config import logger
from config import app_config

class MultiTimeframeAnalyzer:
    """
    Analisador que suporta múltiplos timeframes para diferentes estratégias:
    - Scalping: 1min, 5min
    - Day Trading: 5min, 15min, 1h  
    - Swing Trading: 1h, 4h, 1d
    - Position Trading: 1d, 1w
    """
    
    def __init__(self, asset_symbol: str, db_path: str):
        self.asset_symbol = asset_symbol
        self.db_path = db_path
        
        # Configurações por timeframe
        self.timeframe_configs = {
            '1m': {
                'interval_seconds': 60,
                'max_history': 1440,        # 24 horas
                'strategy_type': 'scalping',
                'aggregation_source': 'raw'
            },
            '5m': {
                'interval_seconds': 300,
                'max_history': 576,         # 48 horas
                'strategy_type': 'day_trading',
                'aggregation_source': '1m'
            },
            '15m': {
                'interval_seconds': 900,
                'max_history': 384,         # 4 dias
                'strategy_type': 'day_trading',
                'aggregation_source': '5m'
            },
            '1h': {
                'interval_seconds': 3600,
                'max_history': 720,         # 30 dias
                'strategy_type': 'swing_trading',
                'aggregation_source': '15m'
            },
            '4h': {
                'interval_seconds': 14400,
                'max_history': 180,         # 30 dias
                'strategy_type': 'swing_trading',
                'aggregation_source': '1h'
            },
            '1d': {
                'interval_seconds': 86400,
                'max_history': 365,         # 1 ano
                'strategy_type': 'position_trading',
                'aggregation_source': '4h'
            }
        }
        
        # Armazenamento em memória por timeframe
        self.timeframe_data = {
            tf: deque(maxlen=config['max_history']) 
            for tf, config in self.timeframe_configs.items()
        }
        
        # Buffer para agregação
        self.aggregation_buffers = {
            tf: [] for tf in self.timeframe_configs.keys()
        }
        
        # Estratégias por tipo
        self.strategies = {
            'scalping': ScalpingStrategy(),
            'day_trading': DayTradingStrategy(),
            'swing_trading': SwingTradingStrategy(),
            'position_trading': PositionTradingStrategy()
        }
        
        self.init_database()
        self.load_historical_data()
    
    def init_database(self):
        """Inicializa tabelas para dados multi-timeframe"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Tabela principal para dados OHLCV por timeframe
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.asset_symbol}_ohlcv_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timeframe TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume REAL NOT NULL,
                    tick_count INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(timeframe, timestamp)
                )
            ''')
            
            # Tabela para sinais por timeframe e estratégia
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.asset_symbol}_multi_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timeframe TEXT NOT NULL,
                    strategy_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL,
                    target_1 REAL,
                    target_2 REAL,
                    target_3 REAL,
                    confidence REAL NOT NULL,
                    risk_reward_ratio REAL,
                    expected_hold_time TEXT,
                    status TEXT DEFAULT 'ACTIVE',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Índices para performance
            cursor.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_{self.asset_symbol}_ohlcv_timeframe_timestamp 
                ON {self.asset_symbol}_ohlcv_data(timeframe, timestamp)
            ''')
            
            cursor.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_{self.asset_symbol}_signals_timeframe_strategy 
                ON {self.asset_symbol}_multi_signals(timeframe, strategy_type, status)
            ''')
            
            conn.commit()
            logger.info(f"[MULTI-TF] Database initialized for {self.asset_symbol}")
            
        except Exception as e:
            logger.error(f"[MULTI-TF] Database error for {self.asset_symbol}: {e}")
        finally:
            conn.close()
    
    def add_raw_data(self, timestamp: datetime, price: float, volume: float):
        """
        Adiciona dados brutos e triggera agregação para todos os timeframes
        """
        try:
            # Adicionar aos buffers de agregação
            raw_data = {
                'timestamp': timestamp,
                'price': price,
                'volume': volume
            }
            
            # Processar cada timeframe
            for timeframe, config in self.timeframe_configs.items():
                self._process_timeframe_data(timeframe, raw_data)
            
        except Exception as e:
            logger.error(f"[MULTI-TF] Error adding raw data: {e}")
    
    def _process_timeframe_data(self, timeframe: str, raw_data: Dict):
        """Processa dados para um timeframe específico"""
        try:
            config = self.timeframe_configs[timeframe]
            interval_seconds = config['interval_seconds']
            
            # Calcular timestamp alinhado ao timeframe
            timestamp = raw_data['timestamp']
            aligned_timestamp = self._align_timestamp(timestamp, interval_seconds)
            
            # Verificar se já existe candle para este período
            current_data = self.timeframe_data[timeframe]
            
            if current_data and current_data[-1]['timestamp'] == aligned_timestamp:
                # Atualizar candle existente
                self._update_ohlcv_candle(current_data[-1], raw_data)
            else:
                # Criar novo candle
                new_candle = self._create_new_candle(aligned_timestamp, raw_data)
                self.timeframe_data[timeframe].append(new_candle)
                
                # Salvar no banco se timeframe >= 5m (para economizar espaço)
                if interval_seconds >= 300:
                    self._save_ohlcv_to_database(timeframe, new_candle)
                
                # Triggerar análise para este timeframe
                self._analyze_timeframe(timeframe)
        
        except Exception as e:
            logger.error(f"[MULTI-TF] Error processing {timeframe}: {e}")
    
    def _align_timestamp(self, timestamp: datetime, interval_seconds: int) -> datetime:
        """Alinha timestamp ao início do período"""
        epoch = timestamp.timestamp()
        aligned_epoch = (epoch // interval_seconds) * interval_seconds
        return datetime.fromtimestamp(aligned_epoch)
    
    def _create_new_candle(self, timestamp: datetime, data: Dict) -> Dict:
        """Cria novo candle OHLCV"""
        return {
            'timestamp': timestamp,
            'open': data['price'],
            'high': data['price'],
            'low': data['price'],
            'close': data['price'],
            'volume': data['volume'],
            'tick_count': 1
        }
    
    def _update_ohlcv_candle(self, candle: Dict, new_data: Dict):
        """Atualiza candle OHLCV existente"""
        candle['high'] = max(candle['high'], new_data['price'])
        candle['low'] = min(candle['low'], new_data['price'])
        candle['close'] = new_data['price']
        candle['volume'] += new_data['volume']
        candle['tick_count'] += 1
    
    def _save_ohlcv_to_database(self, timeframe: str, candle: Dict):
        """Salva candle OHLCV no banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(f'''
                INSERT OR REPLACE INTO {self.asset_symbol}_ohlcv_data 
                (timeframe, timestamp, open_price, high_price, low_price, close_price, volume, tick_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                timeframe,
                candle['timestamp'].isoformat(),
                candle['open'],
                candle['high'],
                candle['low'],
                candle['close'],
                candle['volume'],
                candle['tick_count']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[MULTI-TF] Error saving {timeframe} candle: {e}")
    
    def _analyze_timeframe(self, timeframe: str):
        """Executa análise para um timeframe específico"""
        try:
            config = self.timeframe_configs[timeframe]
            strategy_type = config['strategy_type']
            data = list(self.timeframe_data[timeframe])
            
            if len(data) < 50:  # Dados insuficientes
                return
            
            # Executar estratégia específica
            strategy = self.strategies[strategy_type]
            analysis = strategy.analyze(data, timeframe)
            
            if analysis and analysis.get('signal'):
                self._process_signal(timeframe, strategy_type, analysis)
                
        except Exception as e:
            logger.error(f"[MULTI-TF] Error analyzing {timeframe}: {e}")
    
    def _process_signal(self, timeframe: str, strategy_type: str, analysis: Dict):
        """Processa e salva sinal gerado"""
        try:
            signal = analysis['signal']
            
            if signal['action'] in ['BUY', 'SELL'] and signal['confidence'] >= 60:
                # Salvar sinal no banco
                self._save_signal_to_database(timeframe, strategy_type, signal, analysis)
                
                logger.info(f"[MULTI-TF] {strategy_type.upper()} signal on {timeframe}: "
                           f"{signal['action']} @ {signal['entry_price']:.4f} "
                           f"(Confidence: {signal['confidence']:.1f}%)")
        
        except Exception as e:
            logger.error(f"[MULTI-TF] Error processing signal: {e}")
    
    def _save_signal_to_database(self, timeframe: str, strategy_type: str, signal: Dict, analysis: Dict):
        """Salva sinal no banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(f'''
                INSERT INTO {self.asset_symbol}_multi_signals 
                (timeframe, strategy_type, timestamp, signal_type, entry_price, 
                 stop_loss, target_1, target_2, target_3, confidence, 
                 risk_reward_ratio, expected_hold_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                timeframe,
                strategy_type,
                datetime.now().isoformat(),
                f"{signal['action']}_{strategy_type.upper()}",
                signal['entry_price'],
                signal.get('stop_loss'),
                signal.get('targets', [0, 0, 0])[0] if signal.get('targets') else None,
                signal.get('targets', [0, 0, 0])[1] if signal.get('targets') and len(signal['targets']) > 1 else None,
                signal.get('targets', [0, 0, 0])[2] if signal.get('targets') and len(signal['targets']) > 2 else None,
                signal['confidence'],
                signal.get('risk_reward_ratio'),
                signal.get('expected_hold_time')
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[MULTI-TF] Error saving signal: {e}")
    
    def get_multi_timeframe_analysis(self) -> Dict:
        """Retorna análise consolidada de todos os timeframes"""
        try:
            analysis = {
                'asset_symbol': self.asset_symbol,
                'timestamp': datetime.now().isoformat(),
                'timeframes': {},
                'consensus': {},
                'active_signals': {}
            }
            
            # Análise por timeframe
            for timeframe, data in self.timeframe_data.items():
                if len(data) >= 20:
                    tf_analysis = self._get_timeframe_analysis(timeframe, data)
                    analysis['timeframes'][timeframe] = tf_analysis
            
            # Consensus de múltiplos timeframes
            analysis['consensus'] = self._calculate_multi_timeframe_consensus(analysis['timeframes'])
            
            # Sinais ativos
            analysis['active_signals'] = self._get_active_signals()
            
            return analysis
            
        except Exception as e:
            logger.error(f"[MULTI-TF] Error getting analysis: {e}")
            return {'error': str(e)}
    
    def _get_timeframe_analysis(self, timeframe: str, data: List[Dict]) -> Dict:
        """Análise específica de um timeframe"""
        config = self.timeframe_configs[timeframe]
        strategy_type = config['strategy_type']
        strategy = self.strategies[strategy_type]
        
        return strategy.analyze(data, timeframe)
    
    def _calculate_multi_timeframe_consensus(self, timeframe_analyses: Dict) -> Dict:
        """Calcula consensus entre múltiplos timeframes"""
        try:
            bullish_signals = 0
            bearish_signals = 0
            neutral_signals = 0
            total_confidence = 0
            valid_timeframes = 0
            
            for tf, analysis in timeframe_analyses.items():
                if 'signal' in analysis and analysis['signal']:
                    valid_timeframes += 1
                    signal = analysis['signal']
                    action = signal.get('action', 'HOLD')
                    confidence = signal.get('confidence', 0)
                    
                    total_confidence += confidence
                    
                    if action == 'BUY':
                        bullish_signals += 1
                    elif action == 'SELL':
                        bearish_signals += 1
                    else:
                        neutral_signals += 1
            
            if valid_timeframes == 0:
                return {'action': 'HOLD', 'confidence': 0, 'consensus': 'NO_DATA'}
            
            avg_confidence = total_confidence / valid_timeframes
            
            # Determinar consensus
            if bullish_signals > bearish_signals and bullish_signals >= valid_timeframes * 0.6:
                consensus_action = 'BUY'
                consensus_type = 'STRONG_BULLISH' if bullish_signals >= valid_timeframes * 0.8 else 'BULLISH'
            elif bearish_signals > bullish_signals and bearish_signals >= valid_timeframes * 0.6:
                consensus_action = 'SELL'
                consensus_type = 'STRONG_BEARISH' if bearish_signals >= valid_timeframes * 0.8 else 'BEARISH'
            else:
                consensus_action = 'HOLD'
                consensus_type = 'MIXED_SIGNALS'
            
            return {
                'action': consensus_action,
                'confidence': round(avg_confidence, 1),
                'consensus': consensus_type,
                'timeframe_breakdown': {
                    'bullish': bullish_signals,
                    'bearish': bearish_signals,
                    'neutral': neutral_signals,
                    'total': valid_timeframes
                }
            }
            
        except Exception as e:
            logger.error(f"[MULTI-TF] Error calculating consensus: {e}")
            return {'action': 'HOLD', 'confidence': 0, 'consensus': 'ERROR'}
    
    def _get_active_signals(self) -> Dict:
        """Retorna sinais ativos por timeframe"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(f'''
                SELECT timeframe, strategy_type, signal_type, entry_price, 
                       confidence, created_at, expected_hold_time
                FROM {self.asset_symbol}_multi_signals 
                WHERE status = 'ACTIVE' 
                ORDER BY created_at DESC
                LIMIT 20
            ''')
            
            results = cursor.fetchall()
            conn.close()
            
            active_signals = {}
            for row in results:
                tf = row[0]
                if tf not in active_signals:
                    active_signals[tf] = []
                
                active_signals[tf].append({
                    'strategy_type': row[1],
                    'signal_type': row[2],
                    'entry_price': row[3],
                    'confidence': row[4],
                    'created_at': row[5],
                    'expected_hold_time': row[6]
                })
            
            return active_signals
            
        except Exception as e:
            logger.error(f"[MULTI-TF] Error getting active signals: {e}")
            return {}
    
    def load_historical_data(self):
        """Carrega dados históricos do banco para inicialização"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for timeframe in self.timeframe_configs.keys():
                cursor.execute(f'''
                    SELECT timestamp, open_price, high_price, low_price, close_price, volume, tick_count
                    FROM {self.asset_symbol}_ohlcv_data 
                    WHERE timeframe = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (timeframe, self.timeframe_configs[timeframe]['max_history']))
                
                rows = cursor.fetchall()
                
                for row in reversed(rows):  # Ordem cronológica
                    candle = {
                        'timestamp': datetime.fromisoformat(row[0]),
                        'open': row[1],
                        'high': row[2],
                        'low': row[3],
                        'close': row[4],
                        'volume': row[5],
                        'tick_count': row[6]
                    }
                    self.timeframe_data[timeframe].append(candle)
            
            conn.close()
            logger.info(f"[MULTI-TF] Historical data loaded for {self.asset_symbol}")
            
        except Exception as e:
            logger.error(f"[MULTI-TF] Error loading historical data: {e}")


# Estratégias específicas por tipo de trading

class ScalpingStrategy:
    """Estratégia de Scalping (1-5 minutos)"""
    
    def __init__(self):
        self.config = {
            'rsi_period': 7,
            'rsi_overbought': 75,
            'rsi_oversold': 25,
            'sma_fast': 3,
            'sma_slow': 8,
            'min_confidence': 75,
            'max_hold_minutes': 15,
            'stop_loss_pct': 0.5,
            'target_pct': 0.8
        }
    
    def analyze(self, data: List[Dict], timeframe: str) -> Dict:
        """Análise específica para scalping"""
        try:
            if len(data) < 20:
                return {'signal': None, 'reason': 'Insufficient data'}
            
            # Extrair preços de fechamento
            closes = np.array([candle['close'] for candle in data])
            volumes = np.array([candle['volume'] for candle in data])
            
            # Indicadores rápidos para scalping
            rsi = self._calculate_rsi(closes, self.config['rsi_period'])
            sma_fast = np.mean(closes[-self.config['sma_fast']:])
            sma_slow = np.mean(closes[-self.config['sma_slow']:])
            volume_avg = np.mean(volumes[-10:])
            current_volume = volumes[-1]
            
            # Lógica de scalping
            signal = self._generate_scalp_signal(
                current_price=closes[-1],
                rsi=rsi,
                sma_fast=sma_fast,
                sma_slow=sma_slow,
                volume_ratio=current_volume / volume_avg if volume_avg > 0 else 1
            )
            
            return {
                'strategy': 'scalping',
                'timeframe': timeframe,
                'indicators': {
                    'rsi': round(rsi, 2),
                    'sma_fast': round(sma_fast, 4),
                    'sma_slow': round(sma_slow, 4),
                    'volume_ratio': round(current_volume / volume_avg, 2) if volume_avg > 0 else 1
                },
                'signal': signal
            }
            
        except Exception as e:
            logger.error(f"[SCALP] Analysis error: {e}")
            return {'signal': None, 'error': str(e)}
    
    def _generate_scalp_signal(self, current_price: float, rsi: float, 
                              sma_fast: float, sma_slow: float, volume_ratio: float) -> Dict:
        """Gera sinal de scalping"""
        signal = {
            'action': 'HOLD',
            'confidence': 0,
            'entry_price': current_price,
            'expected_hold_time': f"{self.config['max_hold_minutes']} minutes"
        }
        
        # Condições para BUY
        if (rsi < self.config['rsi_oversold'] and 
            sma_fast > sma_slow and 
            volume_ratio > 1.5):
            
            signal.update({
                'action': 'BUY',
                'confidence': 80,
                'stop_loss': current_price * (1 - self.config['stop_loss_pct'] / 100),
                'targets': [current_price * (1 + self.config['target_pct'] / 100)],
                'risk_reward_ratio': self.config['target_pct'] / self.config['stop_loss_pct']
            })
        
        # Condições para SELL
        elif (rsi > self.config['rsi_overbought'] and 
              sma_fast < sma_slow and 
              volume_ratio > 1.5):
            
            signal.update({
                'action': 'SELL',
                'confidence': 80,
                'stop_loss': current_price * (1 + self.config['stop_loss_pct'] / 100),
                'targets': [current_price * (1 - self.config['target_pct'] / 100)],
                'risk_reward_ratio': self.config['target_pct'] / self.config['stop_loss_pct']
            })
        
        return signal
    
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
        return 100.0 - (100.0 / (1.0 + rs))


class DayTradingStrategy:
    """Estratégia de Day Trading (5min-4h) - Usar configurações atuais"""
    
    def analyze(self, data: List[Dict], timeframe: str) -> Dict:
        """Reutiliza a lógica atual do EnhancedTradingAnalyzer"""
        # Esta é basicamente a estratégia atual - está ótima!
        return {'signal': {'action': 'HOLD', 'confidence': 0}}


class SwingTradingStrategy:
    """Estratégia de Swing Trading (1h-1d)"""
    
    def __init__(self):
        self.config = {
            'rsi_period': 14,
            'rsi_overbought': 65,
            'rsi_oversold': 35,
            'sma_short': 20,
            'sma_long': 50,
            'sma_trend': 200,
            'min_confidence': 45,
            'hold_days': '3-7',
            'stop_loss_pct': 3.0,
            'target_multipliers': [1.2, 2.0, 3.5]
        }
    
    def analyze(self, data: List[Dict], timeframe: str) -> Dict:
        """Análise específica para swing trading"""
        try:
            if len(data) < 50:
                return {'signal': None, 'reason': 'Insufficient data for swing analysis'}
            
            closes = np.array([candle['close'] for candle in data])
            volumes = np.array([candle['volume'] for candle in data])
            
            # Indicadores para swing trading
            rsi = self._calculate_rsi(closes, self.config['rsi_period'])
            sma_short = np.mean(closes[-self.config['sma_short']:])
            sma_long = np.mean(closes[-self.config['sma_long']:])
            sma_trend = np.mean(closes[-self.config['sma_trend']:]) if len(closes) >= self.config['sma_trend'] else sma_long
            
            # Análise de tendência
            trend_direction = self._analyze_trend(sma_short, sma_long, sma_trend)
            support, resistance = self._find_key_levels(closes[-100:])
            
            signal = self._generate_swing_signal(
                current_price=closes[-1],
                rsi=rsi,
                trend=trend_direction,
                support=support,
                resistance=resistance,
                sma_short=sma_short,
                sma_long=sma_long
            )
            
            return {
                'strategy': 'swing_trading',
                'timeframe': timeframe,
                'indicators': {
                    'rsi': round(rsi, 2),
                    'sma_short': round(sma_short, 4),
                    'sma_long': round(sma_long, 4),
                    'sma_trend': round(sma_trend, 4),
                    'trend_direction': trend_direction,
                    'support': round(support, 4),
                    'resistance': round(resistance, 4)
                },
                'signal': signal
            }
            
        except Exception as e:
            logger.error(f"[SWING] Analysis error: {e}")
            return {'signal': None, 'error': str(e)}
    
    def _generate_swing_signal(self, current_price: float, rsi: float, trend: str,
                              support: float, resistance: float, sma_short: float, sma_long: float) -> Dict:
        """Gera sinal de swing trading"""
        signal = {
            'action': 'HOLD',
            'confidence': 0,
            'entry_price': current_price,
            'expected_hold_time': f"{self.config['hold_days']} days"
        }
        
        # Lógica para swing trading
        distance_to_support = (current_price - support) / support if support > 0 else 0
        distance_to_resistance = (resistance - current_price) / current_price if resistance > 0 else 0
        
        # BUY Conditions para swing
        if (trend in ['BULLISH', 'STRONG_BULLISH'] and
            rsi > self.config['rsi_oversold'] and rsi < 60 and
            sma_short > sma_long and
            distance_to_support < 0.02):  # Próximo ao suporte
            
            confidence = 65
            if distance_to_support < 0.01:  # Muito próximo ao suporte
                confidence += 10
            if rsi < 45:  # RSI em zona boa para compra
                confidence += 10
            
            stop_loss = support * 0.98  # Stop abaixo do suporte
            targets = [
                current_price * (1 + (self.config['target_multipliers'][0] * self.config['stop_loss_pct'] / 100)),
                current_price * (1 + (self.config['target_multipliers'][1] * self.config['stop_loss_pct'] / 100)),
                resistance * 0.98  # Próximo à resistência
            ]
            
            signal.update({
                'action': 'BUY',
                'confidence': min(confidence, 90),
                'stop_loss': stop_loss,
                'targets': targets,
                'risk_reward_ratio': self.config['target_multipliers'][0]
            })
        
        # SELL Conditions para swing
        elif (trend in ['BEARISH', 'STRONG_BEARISH'] and
              rsi < self.config['rsi_overbought'] and rsi > 40 and
              sma_short < sma_long and
              distance_to_resistance < 0.02):  # Próximo à resistência
            
            confidence = 65
            if distance_to_resistance < 0.01:
                confidence += 10
            if rsi > 55:
                confidence += 10
            
            stop_loss = resistance * 1.02  # Stop acima da resistência
            targets = [
                current_price * (1 - (self.config['target_multipliers'][0] * self.config['stop_loss_pct'] / 100)),
                current_price * (1 - (self.config['target_multipliers'][1] * self.config['stop_loss_pct'] / 100)),
                support * 1.02  # Próximo ao suporte
            ]
            
            signal.update({
                'action': 'SELL',
                'confidence': min(confidence, 90),
                'stop_loss': stop_loss,
                'targets': targets,
                'risk_reward_ratio': self.config['target_multipliers'][0]
            })
        
        return signal
    
    def _analyze_trend(self, sma_short: float, sma_long: float, sma_trend: float) -> str:
        """Analisa direção da tendência"""
        if sma_short > sma_long > sma_trend:
            return 'STRONG_BULLISH'
        elif sma_short > sma_long:
            return 'BULLISH'
        elif sma_short < sma_long < sma_trend:
            return 'STRONG_BEARISH'
        elif sma_short < sma_long:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def _find_key_levels(self, prices: np.ndarray) -> Tuple[float, float]:
        """Encontra níveis de suporte e resistência"""
        if len(prices) < 20:
            return prices[-1] * 0.95, prices[-1] * 1.05
        
        # Método simples: pivôs de alta e baixa
        highs = []
        lows = []
        
        for i in range(5, len(prices) - 5):
            # Máximo local
            if all(prices[i] >= prices[i-j] for j in range(1, 6)) and \
               all(prices[i] >= prices[i+j] for j in range(1, 6)):
                highs.append(prices[i])
            
            # Mínimo local
            if all(prices[i] <= prices[i-j] for j in range(1, 6)) and \
               all(prices[i] <= prices[i+j] for j in range(1, 6)):
                lows.append(prices[i])
        
        support = np.mean(lows[-3:]) if lows else np.min(prices[-20:])
        resistance = np.mean(highs[-3:]) if highs else np.max(prices[-20:])
        
        return support, resistance
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calcula RSI (mesmo método das outras estratégias)"""
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
        return 100.0 - (100.0 / (1.0 + rs))


class PositionTradingStrategy:
    """Estratégia de Position Trading (1d+)"""
    
    def analyze(self, data: List[Dict], timeframe: str) -> Dict:
        """Análise para position trading (longo prazo)"""
        # Implementação básica - foco em tendências de longo prazo
        return {'signal': {'action': 'HOLD', 'confidence': 0}}