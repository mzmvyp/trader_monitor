# your_project/services/trading_analyzer.py

import sqlite3
import os
import numpy as np
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from utils.logging_config import logger
from config import app_config
from database.setup import setup_trading_analyzer_db
import numpy as np # Certifique-se de que numpy está importado
import json # Será útil para a função de conversão, embora não seja diretamente usado no retorno
from flask import Blueprint, jsonify, request, current_app, render_template


# Função auxiliar para serializar objetos NumPy
def convert_numpy_types(obj):
    """
    Recursively converts NumPy types within a dictionary or list
    to standard Python types (float, int, bool).
    """
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(elem) for elem in obj]
    elif isinstance(obj, np.floating): # Handles np.float32, np.float64, etc.
        return float(obj)
    elif isinstance(obj, np.integer): # Handles np.int32, np.int64, etc.
        return int(obj)
    elif isinstance(obj, np.bool_): # Handles np.True_, np.False_
        return bool(obj)
    else:
        return obj

class EnhancedTradingAnalyzer:
    """
    Enhanced Trading Analyzer with robust technical analysis and signal generation.
    Uses multiple indicators and confirmation signals for better accuracy.
    """
    
    def __init__(self, db_path: str = app_config.TRADING_ANALYZER_DB):
        self.db_path = db_path
        self.price_history = deque(maxlen=200)
        self.volume_history = deque(maxlen=200)
        self.ohlc_history = deque(maxlen=200)
        self.analysis_count = 0
        self.signals = []
        self.last_analysis = None
        
        # Parâmetros de Análise Técnica
        self.ta_params = {
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'sma_short': 9,
            'sma_long': 21,
            'ema_short': 12,
            'ema_long': 26,
            'macd_signal': 9,
            'bb_period': 20,
            'bb_std': 2.0,
            'stoch_k': 14,
            'stoch_d': 3,
            'stoch_overbought': 80,
            'stoch_oversold': 20,
            'volume_sma': 20,
            'atr_period': 14,
            'min_confidence': 60,
            'min_risk_reward': 1.5,
            'min_volume_ratio': 1.1,
        }
        
        # Configuração de Sinais
        self.signal_config = {
            'max_active_signals': 50,
            'signal_cooldown_minutes': 10,
            'target_multipliers': [2.0, 3.5, 5.0],
            'stop_loss_atr_multiplier': 2.0,
            'partial_take_profit': [0.5, 0.3, 0.2],
            'trailing_stop_distance': 1.5,
        }
        
        # Pesos para confluência de indicadores
        self.indicator_weights = {
            'rsi': 0.20,
            'macd': 0.25,
            'bb': 0.15,
            'stoch': 0.15,
            'sma_cross': 0.15,
            'volume': 0.10
        }
        
        self.init_database()
        self.load_previous_data()
    
    def init_database(self):
        """Initialize database with enhanced schema"""
        setup_trading_analyzer_db(self.db_path)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Additional tables for enhanced features
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS enhanced_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    signal_type TEXT,
                    entry_price REAL,
                    target_1 REAL,
                    target_2 REAL,
                    target_3 REAL,
                    stop_loss REAL,
                    confidence REAL,
                    confluence_score REAL,
                    risk_reward_ratio REAL,
                    atr_value REAL,
                    volume_confirmation BOOLEAN,
                    status TEXT DEFAULT 'ACTIVE',
                    entry_reason TEXT,
                    indicators_snapshot TEXT,
                    profit_loss REAL DEFAULT 0,
                    max_profit REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    exit_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info("[ENHANCED] Database initialized")
            
        except Exception as e:
            logger.error(f"[ENHANCED] Database initialization error: {e}")
        finally:
            conn.close()
    
    def load_previous_data(self):
        """Load previous data from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Load price history
            cursor.execute("""
                SELECT timestamp, price, volume 
                FROM price_history 
                ORDER BY timestamp DESC 
                LIMIT 200
            """)
            
            rows = cursor.fetchall()
            for row in reversed(rows):
                self.price_history.append({
                    'timestamp': datetime.fromisoformat(row[0]),
                    'price': row[1],
                    'volume': row[2] or 0
                })
                self.volume_history.append(row[2] or 0)
            
            # Load analyzer state
            cursor.execute("SELECT analysis_count, last_analysis FROM analyzer_state WHERE id = 1")
            state = cursor.fetchone()
            if state:
                self.analysis_count = state[0]
                self.last_analysis = datetime.fromisoformat(state[1]) if state[1] else None
            
            # Load active signals
            cursor.execute("""
                SELECT * FROM trading_signals 
                WHERE status = 'ACTIVE' 
                ORDER BY created_at DESC
            """)
            
            signal_rows = cursor.fetchall()
            for row in signal_rows:
                signal = {
                    'id': row[0],
                    'timestamp': row[1],
                    'pattern_type': row[2],
                    'entry_price': row[3],
                    'target_price': row[4],
                    'stop_loss': row[5],
                    'confidence': row[6],
                    'status': row[7],
                    'created_at': row[8],
                    'profit_loss': row[9] or 0,
                    'activated': row[10] if len(row) > 10 else False
                }
                self.signals.append(signal)
            
            conn.close()
            logger.info(f"[ENHANCED] Loaded {len(self.price_history)} price points and {len(self.signals)} signals")
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error loading previous data: {e}")
    
    def add_price_data(self, timestamp, price, volume=0):
        """Add new price data for analysis"""
        try:
            # Add to history
            self.price_history.append({
                'timestamp': timestamp,
                'price': price,
                'volume': volume
            })
            self.volume_history.append(volume)
            
            # Simulate OHLC data for compatibility
            self.ohlc_history.append({
                'timestamp': timestamp,
                'open': price,
                'high': price * 1.001,
                'low': price * 0.999,
                'close': price,
                'volume': volume
            })
            
            # Save to database
            self.save_price_data(timestamp, price, volume)
            
            # Increment analysis count
            self.analysis_count += 1
            self.last_analysis = datetime.now()
            
            # Run analysis if we have enough data
            if len(self.price_history) >= 50:
                self._comprehensive_market_analysis()
            
            # Save state
            self.save_analyzer_state()
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error adding price data: {e}")
    
    def _comprehensive_market_analysis(self):
        """Análise completa do mercado"""
        try:
            current_price = self.price_history[-1]['price'] if self.price_history else 0
            
            # Calculate indicators
            indicators = self._calculate_comprehensive_indicators()
            
            # Analyze market state
            market_state = self._analyze_market_state(indicators)
            
            # Calculate signal confluence
            signal_analysis = self._calculate_signal_confluence(indicators, market_state)
            
            # Generate signal if conditions are met
            if self._should_generate_signal(signal_analysis):
                self._generate_high_quality_signal(signal_analysis, current_price, indicators)
            
            # Update active signals
            self._update_active_signals(current_price, indicators)
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error in comprehensive analysis: {e}")

    def update_analyzer(self, new_price_data: Dict, new_volume_data: Dict = None):
        """
        Atualiza o analisador com novos dados de preço e volume.
        Isso deve ser chamado por um processador de dados.
        """
        self.price_history.append(new_price_data)
        if new_volume_data:
            self.volume_history.append(new_volume_data)

        # Mantenha o histórico limitado para evitar uso excessivo de memória
        max_history = 200 # Ajuste conforme necessário para seus indicadores
        if len(self.price_history) > max_history:
            self.price_history.pop(0)
        if len(self.volume_history) > max_history:
            self.volume_history.pop(0)

        # Incrementar a contagem de análises e atualizar o timestamp
        self.analysis_count += 1
        self.last_analysis_time = datetime.now()
    
    def _calculate_comprehensive_indicators(self) -> Dict:
        """Calculate all technical indicators"""
        if len(self.price_history) < 30:
            return {}
        
        try:
            # Extract price data
            prices = np.array([p['price'] for p in self.price_history])
            volumes = np.array([v for v in self.volume_history])
            
            indicators = {}
            
            # Moving Averages
            indicators['sma_9'] = self._calculate_sma(prices, 9)
            indicators['sma_21'] = self._calculate_sma(prices, 21)
            indicators['sma_50'] = self._calculate_sma(prices, 50) if len(prices) >= 50 else prices[-1]
            indicators['ema_12'] = self._calculate_ema(prices, 12)
            indicators['ema_26'] = self._calculate_ema(prices, 26)
            
            # RSI
            indicators['rsi'] = self._calculate_rsi(prices, self.ta_params['rsi_period'])
            
            # MACD
            macd_line, signal_line, histogram = self._calculate_macd(prices)
            indicators['macd_line'] = macd_line
            indicators['macd_signal'] = signal_line
            indicators['macd_histogram'] = histogram
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(prices)
            indicators['bb_upper'] = bb_upper
            indicators['bb_middle'] = bb_middle
            indicators['bb_lower'] = bb_lower
            indicators['bb_position'] = (prices[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
            
            # Stochastic
            stoch_k, stoch_d = self._calculate_stochastic(prices)
            indicators['stoch_k'] = stoch_k
            indicators['stoch_d'] = stoch_d
            
            # Volume analysis
            indicators['volume_sma'] = self._calculate_sma(volumes, 20)
            indicators['volume_ratio'] = volumes[-1] / indicators['volume_sma'] if indicators['volume_sma'] > 0 else 1
            
            # Support/Resistance levels
            indicators['support'], indicators['resistance'] = self._calculate_support_resistance(prices)
            
            # Trend strength
            indicators['trend_strength'] = self._calculate_trend_strength(prices)
            indicators['trend_direction'] = self._determine_trend_direction(indicators)
            
            # ATR (simplified)
            indicators['atr'] = self._calculate_atr(prices)
            
            return indicators
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error calculating indicators: {e}")
            return {}
    
    def _calculate_sma(self, data: np.ndarray, period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(data) < period:
            return float(np.mean(data))
        return float(np.mean(data[-period:]))
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(data) < period:
            return float(np.mean(data))
        
        alpha = 2.0 / (period + 1.0)
        ema = float(data[0])
        
        for price in data[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return ema
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate Relative Strength Index"""
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
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi
    
    def _calculate_macd(self, prices: np.ndarray) -> Tuple[float, float, float]:
        """Calculate MACD"""
        if len(prices) < 26:
            return 0.0, 0.0, 0.0
        
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        
        macd_line = ema_12 - ema_26
        # Simplified signal line calculation
        signal_line = macd_line * 0.9
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def _calculate_bollinger_bands(self, prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            price = float(prices[-1])
            return price, price, price
        
        sma = self._calculate_sma(prices, period)
        std = float(np.std(prices[-period:]))
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        return upper, sma, lower
    
    def _calculate_stochastic(self, prices: np.ndarray, period: int = 14) -> Tuple[float, float]:
        """Calculate Stochastic Oscillator"""
        if len(prices) < period:
            return 50.0, 50.0
        
        recent_prices = prices[-period:]
        lowest = float(np.min(recent_prices))
        highest = float(np.max(recent_prices))
        current = float(prices[-1])
        
        if highest == lowest:
            return 50.0, 50.0
        
        k = ((current - lowest) / (highest - lowest)) * 100
        d = k  # Simplified
        
        return k, d
    
    def _calculate_support_resistance(self, prices: np.ndarray) -> Tuple[float, float]:
        """Calculate support and resistance levels"""
        if len(prices) < 20:
            current_price = prices[-1]
            return current_price * 0.98, current_price * 1.02
        
        recent_prices = prices[-20:]
        
        # Simple pivot point calculation
        high = float(np.max(recent_prices))
        low = float(np.min(recent_prices))
        close = float(prices[-1])
        
        pivot = (high + low + close) / 3
        support = pivot - (high - low) * 0.382
        resistance = pivot + (high - low) * 0.382
        
        return support, resistance
    
    def _calculate_trend_strength(self, prices: np.ndarray) -> float:
        """Calculate trend strength (0-1)"""
        if len(prices) < 20:
            return 0.5
        
        # Simple ADX approximation
        recent_prices = prices[-20:]
        
        # Calculate directional movement
        up_moves = []
        down_moves = []
        
        for i in range(1, len(recent_prices)):
            up_move = max(0, recent_prices[i] - recent_prices[i-1])
            down_move = max(0, recent_prices[i-1] - recent_prices[i])
            up_moves.append(up_move)
            down_moves.append(down_move)
        
        avg_up = np.mean(up_moves)
        avg_down = np.mean(down_moves)
        
        if avg_up + avg_down == 0:
            return 0.5
        
        adx = abs(avg_up - avg_down) / (avg_up + avg_down)
        return min(adx, 1.0)
    
    def _calculate_atr(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate Average True Range (simplified)"""
        if len(prices) < 2:
            return float(prices[-1] * 0.02)
        
        # Simplified ATR using price changes
        changes = np.abs(np.diff(prices))
        if len(changes) < period:
            return float(np.mean(changes))
        
        return float(np.mean(changes[-period:]))
    
    def _determine_trend_direction(self, indicators: Dict) -> str:
        """Determine trend direction"""
        sma_9 = indicators.get('sma_9', 0)
        sma_21 = indicators.get('sma_21', 0)
        sma_50 = indicators.get('sma_50', 0)
        
        if sma_9 > sma_21 > sma_50:
            return 'STRONG_BULL'
        elif sma_9 > sma_21:
            return 'BULL'
        elif sma_9 < sma_21 < sma_50:
            return 'STRONG_BEAR'
        elif sma_9 < sma_21:
            return 'BEAR'
        else:
            return 'NEUTRAL'
    
    def _analyze_market_state(self, indicators: Dict) -> Dict:
        """Analyze current market state"""
        if not indicators:
            return {'trend': 'NEUTRAL', 'volatility': 'NORMAL', 'volume': 'NORMAL'}
        
        # Trend analysis
        trend = indicators.get('trend_direction', 'NEUTRAL')
        
        # Volume analysis
        volume_ratio = indicators.get('volume_ratio', 1)
        volume_state = 'HIGH' if volume_ratio > 1.5 else 'LOW' if volume_ratio < 0.7 else 'NORMAL'
        
        # Volatility (simplified)
        volatility = 'NORMAL'
        
        return {
            'trend': trend,
            'volatility': volatility,
            'volume': volume_state,
            'bb_squeeze': False  # Simplified
        }
    
    def _calculate_signal_confluence(self, indicators: Dict, market_state: Dict) -> Dict:
        """Calculate signal confluence with weights"""
        if not indicators:
            return {'action': 'HOLD', 'confidence': 0, 'confluence_score': 0}
        
        bull_score = 0.0
        bear_score = 0.0
        total_weight = 0.0
        reasons = []
        
        # RSI Analysis
        rsi = indicators.get('rsi', 50)
        if rsi < self.ta_params['rsi_oversold']:
            bull_score += self.indicator_weights['rsi']
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > self.ta_params['rsi_overbought']:
            bear_score += self.indicator_weights['rsi']
            reasons.append(f"RSI overbought ({rsi:.1f})")
        total_weight += self.indicator_weights['rsi']
        
        # MACD Analysis
        macd_histogram = indicators.get('macd_histogram', 0)
        if macd_histogram > 0:
            bull_score += self.indicator_weights['macd']
            reasons.append("MACD bullish")
        else:
            bear_score += self.indicator_weights['macd']
            reasons.append("MACD bearish")
        total_weight += self.indicator_weights['macd']
        
        # Bollinger Bands
        bb_position = indicators.get('bb_position', 0.5)
        if bb_position < 0.2:
            bull_score += self.indicator_weights['bb']
            reasons.append("Near lower BB")
        elif bb_position > 0.8:
            bear_score += self.indicator_weights['bb']
            reasons.append("Near upper BB")
        total_weight += self.indicator_weights['bb']
        
        # Stochastic
        stoch_k = indicators.get('stoch_k', 50)
        if stoch_k < self.ta_params['stoch_oversold']:
            bull_score += self.indicator_weights['stoch']
            reasons.append("Stochastic oversold")
        elif stoch_k > self.ta_params['stoch_overbought']:
            bear_score += self.indicator_weights['stoch']
            reasons.append("Stochastic overbought")
        total_weight += self.indicator_weights['stoch']
        
        # SMA Cross
        sma_9 = indicators.get('sma_9', 0)
        sma_21 = indicators.get('sma_21', 0)
        if sma_9 > sma_21:
            bull_score += self.indicator_weights['sma_cross']
            reasons.append("SMA bullish cross")
        else:
            bear_score += self.indicator_weights['sma_cross']
            reasons.append("SMA bearish cross")
        total_weight += self.indicator_weights['sma_cross']
        
        # Volume confirmation
        volume_ratio = indicators.get('volume_ratio', 1)
        if volume_ratio > self.ta_params['min_volume_ratio']:
            if bull_score > bear_score:
                bull_score += self.indicator_weights['volume']
            else:
                bear_score += self.indicator_weights['volume']
            reasons.append(f"Volume confirmation ({volume_ratio:.1f}x)")
        total_weight += self.indicator_weights['volume']
        
        # Calculate final scores
        bull_percentage = (bull_score / total_weight * 100) if total_weight > 0 else 0
        bear_percentage = (bear_score / total_weight * 100) if total_weight > 0 else 0
        
        # Determine action
        action = 'HOLD'
        confidence = 0
        confluence_score = max(bull_percentage, bear_percentage)
        
        if bull_percentage > bear_percentage and bull_percentage >= 60:
            action = 'BUY'
            confidence = bull_percentage
        elif bear_percentage > bull_percentage and bear_percentage >= 60:
            action = 'SELL'
            confidence = bear_percentage
        
        return {
            'action': action,
            'confidence': confidence,
            'confluence_score': confluence_score,
            'bull_score': bull_percentage,
            'bear_score': bear_percentage,
            'reasons': reasons,
            'volume_confirmed': volume_ratio > self.ta_params['min_volume_ratio']
        }
    
    def _should_generate_signal(self, signal_analysis: Dict) -> bool:
        """Check if we should generate a signal"""
        if signal_analysis['action'] == 'HOLD':
            return False
        
        if signal_analysis['confidence'] < self.ta_params['min_confidence']:
            return False
        
        # Check cooldown
        if self.signals:
            last_signal = self.signals[-1]
            last_signal_time = datetime.fromisoformat(last_signal['created_at'])
            if datetime.now() - last_signal_time < timedelta(minutes=self.signal_config['signal_cooldown_minutes']):
                return False
        
        # Check max active signals
        active_signals = [s for s in self.signals if s.get('status') == 'ACTIVE']
        if len(active_signals) >= self.signal_config['max_active_signals']:
            return False
        
        # Volume confirmation required
        if not signal_analysis.get('volume_confirmed', False):
            return False
        
        return True
    
    def _generate_high_quality_signal(self, signal_analysis: Dict, current_price: float, indicators: Dict):
        """Generate high quality signal with risk management"""
        try:
            atr = indicators.get('atr', current_price * 0.02)
            action = signal_analysis['action']
            
            if action == 'BUY':
                stop_loss = current_price - (atr * self.signal_config['stop_loss_atr_multiplier'])
                risk = current_price - stop_loss
                target_1 = current_price + (risk * self.signal_config['target_multipliers'][0])
                target_2 = current_price + (risk * self.signal_config['target_multipliers'][1])
                target_3 = current_price + (risk * self.signal_config['target_multipliers'][2])
                signal_type = 'CONFLUENCE_BUY'
            else:
                stop_loss = current_price + (atr * self.signal_config['stop_loss_atr_multiplier'])
                risk = stop_loss - current_price
                target_1 = current_price - (risk * self.signal_config['target_multipliers'][0])
                target_2 = current_price - (risk * self.signal_config['target_multipliers'][1])
                target_3 = current_price - (risk * self.signal_config['target_multipliers'][2])
                signal_type = 'CONFLUENCE_SELL'
            
            # Calculate risk/reward
            risk_amount = abs(current_price - stop_loss)
            reward_amount = abs(target_1 - current_price)
            risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
            
            if risk_reward_ratio < self.ta_params['min_risk_reward']:
                return
            
            signal = {
                'id': len(self.signals) + 1,
                'timestamp': datetime.now().isoformat(),
                'pattern_type': signal_type,
                'signal_type': signal_type,
                'entry_price': current_price,
                'target_price': target_1,  # For compatibility
                'target_1': target_1,
                'target_2': target_2,
                'target_3': target_3,
                'stop_loss': stop_loss,
                'confidence': round(signal_analysis['confidence'], 1),
                'confluence_score': round(signal_analysis['confluence_score'], 1),
                'risk_reward_ratio': round(risk_reward_ratio, 2),
                'atr_value': round(atr, 2),
                'volume_confirmation': signal_analysis['volume_confirmed'],
                'status': 'ACTIVE',
                'entry_reason': ' | '.join(signal_analysis['reasons']),
                'created_at': datetime.now().isoformat(),
                'profit_loss': 0,
                'max_profit': 0,
                'max_drawdown': 0
            }
            
            self.signals.append(signal)
            self._save_signal(signal)
            
            logger.info(f"[ENHANCED] New signal: {signal_type} @ ${current_price:.2f}")
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error generating signal: {e}")
    
    def _update_active_signals(self, current_price: float, indicators: Dict):
        """Update active signals"""
        for signal in self.signals:
            if signal.get('status') != 'ACTIVE':
                continue
            
            try:
                entry_price = signal['entry_price']
                is_buy = 'BUY' in signal.get('signal_type', signal.get('pattern_type', ''))
                
                # Calculate current P&L
                if is_buy:
                    pnl = ((current_price - entry_price) / entry_price) * 100
                else:
                    pnl = ((entry_price - current_price) / entry_price) * 100
                
                signal['profit_loss'] = round(pnl, 2)
                signal['max_profit'] = max(signal.get('max_profit', 0), pnl)
                signal['max_drawdown'] = min(signal.get('max_drawdown', 0), pnl)
                
                # Check exit conditions
                self._check_signal_exits(signal, current_price)
                
            except Exception as e:
                logger.error(f"[ENHANCED] Error updating signal {signal.get('id')}: {e}")
    
    def _check_signal_exits(self, signal: Dict, current_price: float):
        """Check if signal should be exited"""
        is_buy = 'BUY' in signal.get('signal_type', signal.get('pattern_type', ''))
        
        if is_buy:
            # Check targets
            if 'target_3' in signal and current_price >= signal['target_3']:
                self._exit_signal(signal, 'TARGET_3_HIT')
            elif 'target_2' in signal and current_price >= signal['target_2']:
                self._exit_signal(signal, 'TARGET_2_HIT')
            elif current_price >= signal.get('target_price', signal.get('target_1', 0)):
                self._exit_signal(signal, 'HIT_TARGET')
            # Check stop loss
            elif current_price <= signal['stop_loss']:
                self._exit_signal(signal, 'HIT_STOP')
        else:
            # Check targets (SELL)
            if 'target_3' in signal and current_price <= signal['target_3']:
                self._exit_signal(signal, 'TARGET_3_HIT')
            elif 'target_2' in signal and current_price <= signal['target_2']:
                self._exit_signal(signal, 'TARGET_2_HIT')
            elif current_price <= signal.get('target_price', signal.get('target_1', 0)):
                self._exit_signal(signal, 'HIT_TARGET')
            # Check stop loss
            elif current_price >= signal['stop_loss']:
                self._exit_signal(signal, 'HIT_STOP')
    
    def _exit_signal(self, signal: Dict, exit_type: str):
        """Exit a signal"""
        signal['status'] = exit_type
        signal['updated_at'] = datetime.now().isoformat()
        
        logger.info(f"[ENHANCED] Signal #{signal['id']} closed: {exit_type} | PnL: {signal['profit_loss']:.2f}%")
        
        # Update in database
        self._update_signal_status(signal)
    
    def save_price_data(self, timestamp, price, volume):
        """Save price data to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO price_history (timestamp, price, volume)
                VALUES (?, ?, ?)
            """, (timestamp.isoformat(), price, volume))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error saving price data: {e}")
    
    def save_analyzer_state(self):
        """Save analyzer state to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO analyzer_state (id, analysis_count, last_analysis)
                VALUES (1, ?, ?)
            """, (self.analysis_count, self.last_analysis.isoformat() if self.last_analysis else None))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error saving analyzer state: {e}")
    
    def _save_signal(self, signal):
        """Save signal to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO trading_signals 
                (timestamp, pattern_type, entry_price, target_price, stop_loss, 
                 confidence, status, created_at, profit_loss, activated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal['timestamp'],
                signal['pattern_type'],
                signal['entry_price'],
                signal.get('target_price', signal.get('target_1', 0)),
                signal['stop_loss'],
                signal['confidence'],
                signal['status'],
                signal['created_at'],
                signal['profit_loss'],
                signal.get('activated', False)
            ))
            
            # Also save to enhanced_signals table
            cursor.execute("""
                INSERT INTO enhanced_signals 
                (timestamp, signal_type, entry_price, target_1, target_2, target_3,
                 stop_loss, confidence, confluence_score, risk_reward_ratio, atr_value,
                 volume_confirmation, status, entry_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal['timestamp'],
                signal.get('signal_type', signal['pattern_type']),
                signal['entry_price'],
                signal.get('target_1', signal.get('target_price', 0)),
                signal.get('target_2', 0),
                signal.get('target_3', 0),
                signal['stop_loss'],
                signal['confidence'],
                signal.get('confluence_score', 0),
                signal.get('risk_reward_ratio', 0),
                signal.get('atr_value', 0),
                signal.get('volume_confirmation', False),
                signal['status'],
                signal.get('entry_reason', ''),
                signal['created_at']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error saving signal: {e}")
    
    def _update_signal_status(self, signal):
        """Update signal status in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE trading_signals 
                SET status = ?, profit_loss = ?
                WHERE id = ?
            """, (signal['status'], signal['profit_loss'], signal['id']))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error updating signal status: {e}")
    
    def get_comprehensive_analysis(self) -> Dict:
        """Get comprehensive analysis including all indicators and signals"""
        try:
            if len(self.price_history) < 20:
                # O retorno aqui já é um dict com tipos padrão, então não precisa de conversão
                return {
                    'status': 'INSUFFICIENT_DATA',
                    'message': 'Aguardando mais dados para análise completa',
                    'data_points': len(self.price_history)
                }
            
            current_price = self.price_history[-1]['price'] if self.price_history else 0
            indicators = self._calculate_comprehensive_indicators()
            market_state = self._analyze_market_state(indicators)
            signal_analysis = self._calculate_signal_confluence(indicators, market_state)
            
            # Active signals
            active_signals = [s for s in self.signals if s.get('status') == 'ACTIVE']
            
            # Format indicators for display
            technical_indicators = {}
            if indicators:
                technical_indicators = {
                    'RSI': round(indicators.get('rsi', 50), 2),
                    'RSI_Signal': 'OVERSOLD' if indicators.get('rsi', 50) < 30 else 'OVERBOUGHT' if indicators.get('rsi', 50) > 70 else 'NEUTRAL',
                    'MACD_Line': round(indicators.get('macd_line', 0), 4),
                    'MACD_Signal': round(indicators.get('macd_signal', 0), 4),
                    'MACD_Histogram': round(indicators.get('macd_histogram', 0), 4),
                    'BB_Position': round(indicators.get('bb_position', 0.5), 3),
                    'Stoch_K': round(indicators.get('stoch_k', 50), 2),
                    'Stoch_D': round(indicators.get('stoch_d', 50), 2),
                    'ATR': round(indicators.get('atr', 0), 2),
                    'Volume_Ratio': round(indicators.get('volume_ratio', 1), 2),
                    'Support': round(indicators.get('support', 0), 2),
                    'Resistance': round(indicators.get('resistance', 0), 2),
                    'Trend_Strength': round(indicators.get('trend_strength', 0), 3),
                    'SMA_9': round(indicators.get('sma_9', 0), 2),
                    'SMA_21': round(indicators.get('sma_21', 0), 2),
                    'EMA_12': round(indicators.get('ema_12', 0), 2),
                    'EMA_26': round(indicators.get('ema_26', 0), 2)
                }
            
            # Construção do dicionário de análise
            analysis = {
                'timestamp': datetime.now().isoformat(),
                'current_price': current_price,
                'technical_indicators': technical_indicators,
                'market_analysis': market_state,
                'signal_analysis': {
                    'recommended_action': signal_analysis.get('action', 'HOLD'),
                    'confidence': round(signal_analysis.get('confidence', 0), 1),
                    'confluence_score': round(signal_analysis.get('confluence_score', 0), 1),
                    'bull_score': round(signal_analysis.get('bull_score', 0), 1),
                    'bear_score': round(signal_analysis.get('bear_score', 0), 1),
                    'volume_confirmed': signal_analysis.get('volume_confirmed', False),
                    'reasons': signal_analysis.get('reasons', [])
                },
                'active_signals': [
                    {
                        'id': s['id'],
                        'type': s.get('signal_type', s.get('pattern_type', '')),
                        'entry': s['entry_price'],
                        'targets': [
                            s.get('target_1', s.get('target_price', 0)),
                            s.get('target_2', 0),
                            s.get('target_3', 0)
                        ],
                        'stop_loss': s['stop_loss'],
                        'current_pnl': round(s.get('profit_loss', 0), 2),
                        'max_profit': round(s.get('max_profit', 0), 2),
                        'risk_reward': s.get('risk_reward_ratio', 0),
                        'confidence': s['confidence'],
                        'created_at': s['created_at']
                    }
                    for s in active_signals
                ],
                'performance_summary': {
                    'total_signals_generated': len(self.signals),
                    'active_signals': len(active_signals),
                    'closed_signals': len([s for s in self.signals if s.get('status') != 'ACTIVE']),
                    'win_rate': self._calculate_win_rate(),
                    'analysis_count': self.analysis_count
                },
                'system_health': {
                    'data_quality': 'GOOD' if len(self.price_history) >= 50 else 'FAIR',
                    'indicator_status': 'ACTIVE' if indicators else 'CALCULATING',
                    'last_analysis': self.last_analysis.isoformat() if self.last_analysis else None
                }
            }
            
            # --- CHAME A FUNÇÃO DE CONVERSÃO AQUI ---
            final_analysis = convert_numpy_types(analysis)
            
            return final_analysis # Retorne o dicionário já com tipos Python nativos
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error getting comprehensive analysis: {e}")
            return {'error': str(e)}
    
    def get_current_analysis(self) -> Dict:
        """Compatibility method - redirects to comprehensive analysis"""
        return self.get_comprehensive_analysis()
    
    def get_market_scanner(self) -> Dict:
        """Market scanner for opportunities"""
        if len(self.price_history) < 30:
            return {
                'status': 'INSUFFICIENT_DATA',
                'message': 'Dados insuficientes para scanner'
            }
        
        indicators = self._calculate_comprehensive_indicators()
        market_state = self._analyze_market_state(indicators)
        signal_analysis = self._calculate_signal_confluence(indicators, market_state)
        
        opportunities = []
        
        # Check for extreme RSI
        rsi = indicators.get('rsi', 50)
        if rsi < 20:
            opportunities.append({
                'type': 'EXTREME_OVERSOLD',
                'description': f'RSI extremamente oversold ({rsi:.1f})',
                'priority': 'HIGH',
                'action': 'BUY_WATCH'
            })
        elif rsi > 80:
            opportunities.append({
                'type': 'EXTREME_OVERBOUGHT',
                'description': f'RSI extremamente overbought ({rsi:.1f})',
                'priority': 'HIGH',
                'action': 'SELL_WATCH'
            })
        
        # Volume spike
        volume_ratio = indicators.get('volume_ratio', 1)
        if volume_ratio > 2.0:
            opportunities.append({
                'type': 'VOLUME_SPIKE',
                'description': f'Volume spike detectado ({volume_ratio:.1f}x normal)',
                'priority': 'MEDIUM',
                'action': 'MOMENTUM_WATCH'
            })
        
        # Near support/resistance
        current_price = self.price_history[-1]['price']
        support = indicators.get('support', 0)
        resistance = indicators.get('resistance', 0)
        
        if support > 0 and abs(current_price - support) / current_price < 0.01:
            opportunities.append({
                'type': 'NEAR_SUPPORT',
                'description': f'Preço próximo ao suporte (${support:.2f})',
                'priority': 'MEDIUM',
                'action': 'BOUNCE_WATCH'
            })
        
        if resistance > 0 and abs(current_price - resistance) / current_price < 0.01:
            opportunities.append({
                'type': 'NEAR_RESISTANCE',
                'description': f'Preço próximo à resistência (${resistance:.2f})',
                'priority': 'MEDIUM',
                'action': 'REJECTION_WATCH'
            })
        
        # High confluence
        if signal_analysis.get('confluence_score', 0) > 80:
            opportunities.append({
                'type': 'HIGH_CONFLUENCE',
                'description': f'Alta confluência de indicadores ({signal_analysis["confluence_score"]:.1f}%)',
                'priority': 'HIGH',
                'action': signal_analysis.get('action', 'HOLD')
            })
        
        return {
            'timestamp': datetime.now().isoformat(),
            'market_state': market_state,
            'current_price': current_price,
            'opportunities_found': len(opportunities),
            'opportunities': opportunities,
            'overall_bias': signal_analysis.get('action', 'NEUTRAL'),
            'confidence': signal_analysis.get('confidence', 0),
            'key_levels': {
                'support': round(support, 2),
                'resistance': round(resistance, 2),
                'atr': round(indicators.get('atr', 0), 2)
            }
        }
    
    def get_performance_report(self, days: int = 30) -> Dict:
        """Generate performance report"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Filter signals in period
            recent_signals = [
                s for s in self.signals 
                if datetime.fromisoformat(s.get('created_at', '1970-01-01')) >= cutoff_date
            ]
            
            if not recent_signals:
                return {
                    'period_days': days,
                    'message': f'Nenhum sinal nos últimos {days} dias'
                }
            
            # Calculate statistics
            closed_signals = [s for s in recent_signals if s.get('status') != 'ACTIVE']
            winning_signals = [s for s in closed_signals if s.get('profit_loss', 0) > 0]
            losing_signals = [s for s in closed_signals if s.get('profit_loss', 0) < 0]
            
            total_trades = len(closed_signals)
            win_count = len(winning_signals)
            loss_count = len(losing_signals)
            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
            
            # Profit/Loss
            total_profit = sum([s.get('profit_loss', 0) for s in winning_signals])
            total_loss = sum([s.get('profit_loss', 0) for s in losing_signals])
            net_profit = total_profit + total_loss
            
            avg_win = total_profit / win_count if win_count > 0 else 0
            avg_loss = total_loss / loss_count if loss_count > 0 else 0
            profit_factor = abs(total_profit / total_loss) if total_loss != 0 else float('inf')
            
            # Signal type analysis
            signal_types = {}
            for signal in recent_signals:
                sig_type = signal.get('signal_type', signal.get('pattern_type', 'UNKNOWN'))
                if sig_type not in signal_types:
                    signal_types[sig_type] = {'count': 0, 'wins': 0, 'total_pnl': 0}
                
                signal_types[sig_type]['count'] += 1
                if signal.get('profit_loss', 0) > 0:
                    signal_types[sig_type]['wins'] += 1
                signal_types[sig_type]['total_pnl'] += signal.get('profit_loss', 0)
            
            return {
                'period_days': days,
                'analysis_period': f"{cutoff_date.date()} até {datetime.now().date()}",
                'overall_performance': {
                    'total_signals': len(recent_signals),
                    'closed_trades': total_trades,
                    'active_trades': len(recent_signals) - total_trades,
                    'win_rate': round(win_rate, 2),
                    'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 999,
                    'net_profit_pct': round(net_profit, 2)
                },
                'trade_statistics': {
                    'winning_trades': win_count,
                    'losing_trades': loss_count,
                    'average_win_pct': round(avg_win, 2),
                    'average_loss_pct': round(avg_loss, 2)
                },
                'signal_type_breakdown': {
                    sig_type: {
                        'total_signals': data['count'],
                        'win_rate': round((data['wins'] / data['count'] * 100), 2) if data['count'] > 0 else 0,
                        'total_pnl': round(data['total_pnl'], 2),
                        'avg_pnl': round(data['total_pnl'] / data['count'], 2) if data['count'] > 0 else 0
                    }
                    for sig_type, data in signal_types.items()
                },
                'recent_signals': [
                    {
                        'id': s['id'],
                        'created': s.get('created_at', ''),
                        'type': s.get('signal_type', s.get('pattern_type', '')),
                        'entry': s.get('entry_price', 0),
                        'status': s.get('status', ''),
                        'pnl': round(s.get('profit_loss', 0), 2),
                        'confidence': s.get('confidence', 0)
                    }
                    for s in recent_signals[-10:]
                ]
            }
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error generating performance report: {e}")
            return {'error': str(e)}
    
    def get_system_status(self) -> Dict:
        """Get system status"""
        
        # Obter o timestamp do último dado de preço de forma segura
        last_data_timestamp = None
        if self.price_history and isinstance(self.price_history[-1], dict) and 'timestamp' in self.price_history[-1]:
            ts = self.price_history[-1]['timestamp']
            if isinstance(ts, datetime):
                last_data_timestamp = ts.isoformat()
            elif isinstance(ts, str): # Se já for string ISO, use-o diretamente
                last_data_timestamp = ts
            # Se for NumPy datetime, a função convert_numpy_types cuidará
            
        # Obter o timestamp do último sinal de forma segura
        last_signal_time_iso = None
        if self.signals and isinstance(self.signals[-1], dict) and 'created_at' in self.signals[-1]:
            created_at = self.signals[-1]['created_at']
            if isinstance(created_at, datetime):
                last_signal_time_iso = created_at.isoformat()
            elif isinstance(created_at, str): # Se já for string ISO, use-o diretamente
                last_signal_time_iso = created_at
            # Se for NumPy datetime, a função convert_numpy_types cuidará

        status_data = {
            'system_info': {
                'version': '2.0.0-enhanced',
                'status': 'ACTIVE',
                'total_analysis': self.analysis_count,
                'database_path': self.db_path
            },
            'data_status': {
                'price_data_points': len(self.price_history),
                'volume_data_points': len(self.volume_history),
                'data_quality': 'GOOD' if len(self.price_history) >= 50 else 'FAIR',
                'last_data_timestamp': last_data_timestamp
            },
            'signal_status': {
                'total_signals_generated': len(self.signals),
                'active_signals': len([s for s in self.signals if s.get('status') == 'ACTIVE']),
                'closed_signals': len([s for s in self.signals if s.get('status') != 'ACTIVE']),
                'last_signal_time': last_signal_time_iso
            },
            'performance_overview': {
                'win_rate': self._calculate_win_rate(),
                'total_pnl': round(sum(s.get('profit_loss', 0) for s in self.signals), 2)
            }
        }
        
        # Aplica a função de conversão para garantir que todos os tipos sejam JSON-serializáveis
        return convert_numpy_types(status_data)
    
    def _calculate_win_rate(self) -> float:
        """Calcula a taxa de vitória com base nos sinais fechados."""
        closed_signals = [s for s in self.signals if s.get('status') != 'ACTIVE']
        if not closed_signals:
            return 0.0

        wins = sum(1 for s in closed_signals if s.get('profit_loss', 0) > 0)
        return (wins / len(closed_signals)) * 100.0
    
    def reset_signals_and_state(self):
        """Reset all signals and state"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM trading_signals")
            cursor.execute("DELETE FROM enhanced_signals")
            cursor.execute("DELETE FROM analyzer_state")
            
            conn.commit()
            conn.close()
            
            self.signals = []
            self.analysis_count = 0
            
            logger.info("[ENHANCED] Signals and state reset")
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error resetting signals: {e}")
    
    def export_signals_to_csv(self, filename: str = None) -> str:
        """Export signals to CSV"""
        if not filename:
            filename = f"trading_signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            import csv
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'id', 'timestamp', 'signal_type', 'entry_price', 
                    'target_1', 'target_2', 'target_3', 'stop_loss',
                    'confidence', 'risk_reward_ratio', 'status', 'profit_loss',
                    'created_at'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for signal in self.signals:
                    csv_signal = {
                        'id': signal.get('id', ''),
                        'timestamp': signal.get('timestamp', ''),
                        'signal_type': signal.get('signal_type', signal.get('pattern_type', '')),
                        'entry_price': signal.get('entry_price', ''),
                        'target_1': signal.get('target_1', signal.get('target_price', '')),
                        'target_2': signal.get('target_2', ''),
                        'target_3': signal.get('target_3', ''),
                        'stop_loss': signal.get('stop_loss', ''),
                        'confidence': signal.get('confidence', ''),
                        'risk_reward_ratio': signal.get('risk_reward_ratio', ''),
                        'status': signal.get('status', ''),
                        'profit_loss': signal.get('profit_loss', ''),
                        'created_at': signal.get('created_at', '')
                    }
                    writer.writerow(csv_signal)
            
            logger.info(f"[ENHANCED] Signals exported to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error exporting signals: {e}")
            return ""