# your_project/services/enhanced_trading_analyzer.py

import sqlite3
import os
import numpy as np
import pandas as pd
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from utils.logging_config import logger
from config import app_config
from database.setup import setup_trading_analyzer_db

class EnhancedTradingAnalyzer:
    """
    Enhanced Trading Analyzer with robust technical analysis and signal generation.
    Uses multiple indicators and confirmation signals for better accuracy.
    
    Características principais:
    - Análise multi-indicador com confluência
    - Gestão de risco aprimorada com ATR
    - Sistema de sinais baseado em probabilidade
    - Backtesting e performance tracking
    """
    
    def __init__(self, db_path: str = app_config.TRADING_ANALYZER_DB):
        self.db_path = db_path
        self.price_history = deque(maxlen=200)
        self.volume_history = deque(maxlen=200)
        self.ohlc_history = deque(maxlen=200)  # Para cálculos mais precisos
        self.analysis_count = 0
        self.signals = []
        self.last_analysis = None
        
        # Parâmetros de Análise Técnica Otimizados
        self.ta_params = {
            'rsi_period': 14,
            'rsi_overbought': 75,      # Mais restritivo
            'rsi_oversold': 25,        # Mais restritivo
            'sma_short': 9,            # Fibonacci
            'sma_long': 21,            # Fibonacci
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
            'min_confidence': 70,      # Aumentado para maior qualidade
            'min_risk_reward': 2.5,    # Melhor risk/reward
            'min_volume_ratio': 1.3,   # Volume confirmation
        }
        
        # Configuração de Sinais Aprimorada
        self.signal_config = {
            'max_active_signals': 3,
            'signal_cooldown_minutes': 120,  # 2 horas entre sinais
            'target_multipliers': [2.0, 3.5, 5.0],  # Targets mais conservadores
            'stop_loss_atr_multiplier': 2.0,
            'partial_take_profit': [0.5, 0.3, 0.2],  # 50%, 30%, 20% nos targets
            'trailing_stop_distance': 1.5,  # ATR multiplier para trailing stop
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
            # Tabela para OHLC data
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ohlc_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT UNIQUE,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Enhanced signals table
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
            
            # Performance tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE,
                    total_signals INTEGER,
                    winning_signals INTEGER,
                    losing_signals INTEGER,
                    win_rate REAL,
                    profit_factor REAL,
                    avg_win REAL,
                    avg_loss REAL,
                    max_drawdown REAL,
                    sharpe_ratio REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Market state tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS market_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    trend_direction TEXT,
                    volatility_regime TEXT,
                    volume_profile TEXT,
                    support_level REAL,
                    resistance_level REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info("[ENHANCED] Enhanced database schema initialized")
            
        except Exception as e:
            logger.error(f"[ENHANCED] Database initialization error: {e}")
        finally:
            conn.close()
    
    def add_ohlc_data(self, timestamp: datetime, open_price: float, high: float, 
                      low: float, close: float, volume: float = 0):
        """Add OHLC data for more precise technical analysis"""
        
        ohlc_data = {
            'timestamp': timestamp,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }
        
        self.ohlc_history.append(ohlc_data)
        
        # Manter compatibilidade com price_history
        self.price_history.append({
            'timestamp': timestamp,
            'price': close,
            'volume': volume
        })
        self.volume_history.append(volume)
        
        self.analysis_count += 1
        self.last_analysis = datetime.now()
        
        # Save to database
        self._save_ohlc_data(ohlc_data)
        
        # Analyze for signals
        if len(self.ohlc_history) >= 50:
            self._comprehensive_market_analysis()
    
    def _comprehensive_market_analysis(self):
        """Análise completa do mercado com múltiplos timeframes"""
        try:
            current_price = self.ohlc_history[-1]['close']
            
            # 1. Calcular todos os indicadores
            indicators = self._calculate_comprehensive_indicators()
            
            # 2. Determinar estado do mercado
            market_state = self._analyze_market_state(indicators)
            
            # 3. Calcular confluência de sinais
            signal_analysis = self._calculate_signal_confluence(indicators, market_state)
            
            # 4. Avaliar geração de sinais
            if self._should_generate_signal(signal_analysis):
                self._generate_high_quality_signal(signal_analysis, current_price, indicators)
            
            # 5. Atualizar sinais existentes
            self._update_active_signals(current_price, indicators)
            
            # 6. Calcular métricas de performance
            self._update_performance_metrics()
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error in comprehensive analysis: {e}")
    
    def _calculate_comprehensive_indicators(self) -> Dict:
        """Calcula indicadores técnicos abrangentes"""
        if len(self.ohlc_history) < 30:
            return {}
        
        # Extrair dados
        closes = np.array([d['close'] for d in self.ohlc_history])
        highs = np.array([d['high'] for d in self.ohlc_history])
        lows = np.array([d['low'] for d in self.ohlc_history])
        volumes = np.array([d['volume'] for d in self.ohlc_history])
        
        indicators = {}
        
        try:
            # RSI melhorado
            indicators['rsi'] = self._calculate_rsi_improved(closes, self.ta_params['rsi_period'])
            indicators['rsi_divergence'] = self._detect_rsi_divergence(closes)
            
            # Moving Averages
            indicators['sma_9'] = self._calculate_sma(closes, 9)
            indicators['sma_21'] = self._calculate_sma(closes, 21)
            indicators['sma_50'] = self._calculate_sma(closes, 50) if len(closes) >= 50 else closes[-1]
            indicators['ema_12'] = self._calculate_ema_improved(closes, 12)
            indicators['ema_26'] = self._calculate_ema_improved(closes, 26)
            
            # MACD aprimorado
            macd_line, signal_line, histogram = self._calculate_macd_improved(closes)
            indicators['macd_line'] = macd_line
            indicators['macd_signal'] = signal_line
            indicators['macd_histogram'] = histogram
            indicators['macd_divergence'] = self._detect_macd_divergence(closes, histogram)
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower, bb_width = self._calculate_bollinger_bands_improved(closes)
            indicators['bb_upper'] = bb_upper
            indicators['bb_middle'] = bb_middle
            indicators['bb_lower'] = bb_lower
            indicators['bb_position'] = (closes[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
            indicators['bb_squeeze'] = bb_width < np.mean([self._calculate_bollinger_width(closes, i) for i in range(10, 21)])
            
            # Stochastic aprimorado
            stoch_k, stoch_d = self._calculate_stochastic_improved(highs, lows, closes)
            indicators['stoch_k'] = stoch_k
            indicators['stoch_d'] = stoch_d
            indicators['stoch_divergence'] = self._detect_stochastic_divergence(closes, stoch_k)
            
            # ATR e volatilidade
            indicators['atr'] = self._calculate_atr_improved(highs, lows, closes)
            indicators['volatility_regime'] = self._classify_volatility_regime(indicators['atr'], closes)
            
            # Volume analysis
            indicators['volume_sma'] = self._calculate_sma(volumes, 20)
            indicators['volume_ratio'] = volumes[-1] / indicators['volume_sma'] if indicators['volume_sma'] > 0 else 1
            indicators['volume_trend'] = self._analyze_volume_trend(volumes)
            
            # Support/Resistance
            indicators['support'], indicators['resistance'] = self._calculate_support_resistance(highs, lows, closes)
            
            # Trend analysis
            indicators['trend_strength'] = self._calculate_trend_strength(closes)
            indicators['trend_direction'] = self._determine_trend_direction(indicators)
            
            return indicators
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error calculating indicators: {e}")
            return {}
    
    def _calculate_rsi_improved(self, prices: np.ndarray, period: int = 14) -> float:
        """RSI melhorado com Wilder's smoothing"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Wilder's smoothing
        alpha = 1.0 / period
        avg_gain = gains[0]
        avg_loss = losses[0]
        
        for i in range(1, len(gains)):
            avg_gain = alpha * gains[i] + (1 - alpha) * avg_gain
            avg_loss = alpha * losses[i] + (1 - alpha) * avg_loss
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi
    
    def _calculate_ema_improved(self, prices: np.ndarray, period: int) -> float:
        """EMA melhorado com inicialização SMA"""
        if len(prices) < period:
            return float(np.mean(prices))
        
        # Inicializar com SMA
        sma = np.mean(prices[:period])
        alpha = 2.0 / (period + 1.0)
        ema = sma
        
        for price in prices[period:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return float(ema)
    
    def _calculate_macd_improved(self, prices: np.ndarray) -> Tuple[float, float, float]:
        """MACD melhorado com EMAs precisas"""
        if len(prices) < 26:
            return 0.0, 0.0, 0.0
        
        ema_12 = self._calculate_ema_improved(prices, 12)
        ema_26 = self._calculate_ema_improved(prices, 26)
        macd_line = ema_12 - ema_26
        
        # Signal line (EMA de 9 períodos do MACD)
        # Simplificado para esta implementação
        signal_line = macd_line * 0.9  # Aproximação
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def _calculate_bollinger_bands_improved(self, prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[float, float, float, float]:
        """Bollinger Bands melhoradas com largura"""
        if len(prices) < period:
            price = float(prices[-1])
            return price, price, price, 0.0
        
        recent_prices = prices[-period:]
        middle = float(np.mean(recent_prices))
        std = float(np.std(recent_prices, ddof=1))
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        width = (upper - lower) / middle  # Largura normalizada
        
        return upper, middle, lower, width
    
    def _calculate_stochastic_improved(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, k_period: int = 14, d_period: int = 3) -> Tuple[float, float]:
        """Stochastic melhorado com %K e %D precisos"""
        if len(closes) < k_period:
            return 50.0, 50.0
        
        recent_highs = highs[-k_period:]
        recent_lows = lows[-k_period:]
        current_close = closes[-1]
        
        highest_high = float(np.max(recent_highs))
        lowest_low = float(np.min(recent_lows))
        
        if highest_high == lowest_low:
            stoch_k = 50.0
        else:
            stoch_k = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100.0
        
        # %D é a média móvel de %K
        if len(closes) >= k_period + d_period - 1:
            k_values = []
            for i in range(d_period):
                idx = -k_period - d_period + 1 + i
                if abs(idx) <= len(closes):
                    h = highs[idx:idx+k_period] if idx+k_period <= 0 else highs[idx:]
                    l = lows[idx:idx+k_period] if idx+k_period <= 0 else lows[idx:]
                    c = closes[idx+k_period-1] if idx+k_period-1 < 0 else closes[-1]
                    
                    hh = float(np.max(h)) if len(h) > 0 else highest_high
                    ll = float(np.min(l)) if len(l) > 0 else lowest_low
                    
                    if hh != ll:
                        k_val = ((c - ll) / (hh - ll)) * 100.0
                        k_values.append(k_val)
            
            stoch_d = float(np.mean(k_values)) if k_values else stoch_k
        else:
            stoch_d = stoch_k
        
        return stoch_k, stoch_d
    
    def _calculate_atr_improved(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """ATR melhorado com True Range preciso"""
        if len(closes) < 2:
            return float(closes[-1] * 0.02)  # 2% default
        
        true_ranges = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close_prev = abs(highs[i] - closes[i-1])
            low_close_prev = abs(lows[i] - closes[i-1])
            
            true_range = max(high_low, high_close_prev, low_close_prev)
            true_ranges.append(true_range)
        
        if len(true_ranges) < period:
            return float(np.mean(true_ranges))
        
        # Wilder's smoothing para ATR
        atr = np.mean(true_ranges[:period])
        alpha = 1.0 / period
        
        for tr in true_ranges[period:]:
            atr = alpha * tr + (1 - alpha) * atr
        
        return float(atr)
    
    def _analyze_market_state(self, indicators: Dict) -> Dict:
        """Analisa o estado atual do mercado"""
        if not indicators:
            return {'trend': 'NEUTRAL', 'volatility': 'NORMAL', 'volume': 'NORMAL'}
        
        # Trend Analysis
        trend = 'NEUTRAL'
        if indicators.get('sma_9', 0) > indicators.get('sma_21', 0):
            if indicators.get('trend_strength', 0) > 0.6:
                trend = 'STRONG_BULL'
            else:
                trend = 'BULL'
        elif indicators.get('sma_9', 0) < indicators.get('sma_21', 0):
            if indicators.get('trend_strength', 0) > 0.6:
                trend = 'STRONG_BEAR'
            else:
                trend = 'BEAR'
        
        # Volatility Analysis
        volatility = indicators.get('volatility_regime', 'NORMAL')
        
        # Volume Analysis
        volume_state = 'NORMAL'
        volume_ratio = indicators.get('volume_ratio', 1)
        if volume_ratio > 1.5:
            volume_state = 'HIGH'
        elif volume_ratio < 0.7:
            volume_state = 'LOW'
        
        return {
            'trend': trend,
            'volatility': volatility,
            'volume': volume_state,
            'bb_squeeze': indicators.get('bb_squeeze', False)
        }
    
    def _calculate_signal_confluence(self, indicators: Dict, market_state: Dict) -> Dict:
        """Calcula confluência de sinais com pesos"""
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
        macd_line = indicators.get('macd_line', 0)
        macd_signal = indicators.get('macd_signal', 0)
        if macd_line > macd_signal and macd_line > 0:
            bull_score += self.indicator_weights['macd']
            reasons.append("MACD bullish crossover")
        elif macd_line < macd_signal and macd_line < 0:
            bear_score += self.indicator_weights['macd']
            reasons.append("MACD bearish crossover")
        total_weight += self.indicator_weights['macd']
        
        # Bollinger Bands
        bb_position = indicators.get('bb_position', 0.5)
        if bb_position < 0.1:  # Muito próximo da banda inferior
            bull_score += self.indicator_weights['bb']
            reasons.append("BB oversold position")
        elif bb_position > 0.9:  # Muito próximo da banda superior
            bear_score += self.indicator_weights['bb']
            reasons.append("BB overbought position")
        total_weight += self.indicator_weights['bb']
        
        # Stochastic
        stoch_k = indicators.get('stoch_k', 50)
        stoch_d = indicators.get('stoch_d', 50)
        if stoch_k < self.ta_params['stoch_oversold'] and stoch_k > stoch_d:
            bull_score += self.indicator_weights['stoch']
            reasons.append("Stochastic oversold crossover")
        elif stoch_k > self.ta_params['stoch_overbought'] and stoch_k < stoch_d:
            bear_score += self.indicator_weights['stoch']
            reasons.append("Stochastic overbought crossover")
        total_weight += self.indicator_weights['stoch']
        
        # SMA Cross
        sma_9 = indicators.get('sma_9', 0)
        sma_21 = indicators.get('sma_21', 0)
        if sma_9 > sma_21 and market_state['trend'] in ['BULL', 'STRONG_BULL']:
            bull_score += self.indicator_weights['sma_cross']
            reasons.append("SMA bullish alignment")
        elif sma_9 < sma_21 and market_state['trend'] in ['BEAR', 'STRONG_BEAR']:
            bear_score += self.indicator_weights['sma_cross']
            reasons.append("SMA bearish alignment")
        total_weight += self.indicator_weights['sma_cross']
        
        # Volume Confirmation
        volume_ratio = indicators.get('volume_ratio', 1)
        if volume_ratio > self.ta_params['min_volume_ratio']:
            if bull_score > bear_score:
                bull_score += self.indicator_weights['volume']
            else:
                bear_score += self.indicator_weights['volume']
            reasons.append(f"Volume confirmation ({volume_ratio:.1f}x)")
        total_weight += self.indicator_weights['volume']
        
        # Calcular scores finais
        bull_percentage = (bull_score / total_weight * 100) if total_weight > 0 else 0
        bear_percentage = (bear_score / total_weight * 100) if total_weight > 0 else 0
        
        # Determinar ação
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
        """Determina se deve gerar um sinal baseado em critérios rigorosos"""
        if signal_analysis['action'] == 'HOLD':
            return False
        
        if signal_analysis['confidence'] < self.ta_params['min_confidence']:
            return False
        
        # Verificar cooldown
        if not self._can_generate_signal():
            return False
        
        # Verificar número máximo de sinais ativos
        active_signals = [s for s in self.signals if s.get('status') == 'ACTIVE']
        if len(active_signals) >= self.signal_config['max_active_signals']:
            return False
        
        # Volume confirmation obrigatório
        if not signal_analysis.get('volume_confirmed', False):
            logger.debug("[ENHANCED] Signal rejected: insufficient volume confirmation")
            return False
        
        return True
    
    def _generate_high_quality_signal(self, signal_analysis: Dict, current_price: float, indicators: Dict):
        """Gera sinal de alta qualidade com gestão de risco adequada"""
        try:
            atr = indicators.get('atr', current_price * 0.02)
            action = signal_analysis['action']
            
            if action == 'BUY':
                # Stop loss baseado em ATR + support level
                support = indicators.get('support', current_price - (atr * 2))
                stop_loss = min(support, current_price - (atr * self.signal_config['stop_loss_atr_multiplier']))
                
                # Targets múltiplos
                risk = current_price - stop_loss
                target_1 = current_price + (risk * self.signal_config['target_multipliers'][0])
                target_2 = current_price + (risk * self.signal_config['target_multipliers'][1])
                target_3 = current_price + (risk * self.signal_config['target_multipliers'][2])
                
                signal_type = 'CONFLUENCE_BUY'
                
            elif action == 'SELL':
                # Stop loss baseado em ATR + resistance level
                resistance = indicators.get('resistance', current_price + (atr * 2))
                stop_loss = max(resistance, current_price + (atr * self.signal_config['stop_loss_atr_multiplier']))
                
                # Targets múltiplos
                risk = stop_loss - current_price
                target_1 = current_price - (risk * self.signal_config['target_multipliers'][0])
                target_2 = current_price - (risk * self.signal_config['target_multipliers'][1])
                target_3 = current_price - (risk * self.signal_config['target_multipliers'][2])
                
                signal_type = 'CONFLUENCE_SELL'
            else:
                return
            
            # Calcular risk/reward para target principal
            risk_amount = abs(current_price - stop_loss)
            reward_amount = abs(target_1 - current_price)
            risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
            
            # Validar risk/reward
            if risk_reward_ratio < self.ta_params['min_risk_reward']:
                logger.debug(f"[ENHANCED] Signal rejected: poor R/R ratio {risk_reward_ratio:.2f}")
                return
            
            # Criar sinal aprimorado
            signal = {
                'id': len(self.signals) + 1,
                'timestamp': datetime.now().isoformat(),
                'signal_type': signal_type,
                'entry_price': current_price,
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
                'indicators_snapshot': str(indicators),
                'profit_loss': 0,
                'max_profit': 0,
                'max_drawdown': 0,
                'created_at': datetime.now().isoformat()
            }
            
            self.signals.append(signal)
            self._save_enhanced_signal(signal)
            
            logger.info(f"[ENHANCED] 🎯 NEW HIGH-QUALITY SIGNAL:")
            logger.info(f"  Type: {signal_type}")
            logger.info(f"  Entry: ${current_price:,.2f}")
            logger.info(f"  Targets: ${target_1:,.2f} | ${target_2:,.2f} | ${target_3:,.2f}")
            logger.info(f"  Stop: ${stop_loss:,.2f}")
            logger.info(f"  R/R: {risk_reward_ratio:.1f}:1 | Confidence: {signal_analysis['confidence']:.1f}%")
            logger.info(f"  Reasons: {signal['entry_reason']}")
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error generating signal: {e}")
    
    def _update_active_signals(self, current_price: float, indicators: Dict):
        """Atualiza sinais ativos com trailing stops e partial profits"""
        for signal in self.signals:
            if signal.get('status') != 'ACTIVE':
                continue
            
            try:
                entry_price = signal['entry_price']
                is_buy_signal = signal['signal_type'].endswith('_BUY')
                
                # Calcular profit/loss atual
                if is_buy_signal:
                    current_pnl = ((current_price - entry_price) / entry_price) * 100
                else:
                    current_pnl = ((entry_price - current_price) / entry_price) * 100
                
                signal['profit_loss'] = round(current_pnl, 2)
                signal['max_profit'] = max(signal.get('max_profit', 0), current_pnl)
                signal['max_drawdown'] = min(signal.get('max_drawdown', 0), current_pnl)
                
                # Verificar targets e stop loss
                self._check_signal_exits(signal, current_price, indicators)
                
            except Exception as e:
                logger.error(f"[ENHANCED] Error updating signal {signal.get('id')}: {e}")
    
    def _check_signal_exits(self, signal: Dict, current_price: float, indicators: Dict):
        """Verifica saídas do sinal (targets, stop loss, trailing stop)"""
        entry_price = signal['entry_price']
        is_buy_signal = signal['signal_type'].endswith('_BUY')
        
        if is_buy_signal:
            # Verificar targets (BUY)
            if current_price >= signal['target_3']:
                self._exit_signal(signal, current_price, 'TARGET_3_HIT', 'All targets achieved')
            elif current_price >= signal['target_2']:
                if 'TARGET_2_PARTIAL' not in signal.get('exit_reason', ''):
                    self._partial_exit(signal, current_price, 'TARGET_2_PARTIAL', 0.7)  # 70% out
            elif current_price >= signal['target_1']:
                if 'TARGET_1_PARTIAL' not in signal.get('exit_reason', ''):
                    self._partial_exit(signal, current_price, 'TARGET_1_PARTIAL', 0.5)  # 50% out
            
            # Verificar stop loss
            elif current_price <= signal['stop_loss']:
                self._exit_signal(signal, current_price, 'STOP_LOSS_HIT', 'Stop loss triggered')
            
            # Trailing stop (se em lucro)
            elif current_price > entry_price * 1.02:  # 2% de lucro mínimo
                atr = indicators.get('atr', entry_price * 0.02)
                trailing_stop = current_price - (atr * self.signal_config['trailing_stop_distance'])
                if trailing_stop > signal['stop_loss']:
                    signal['stop_loss'] = trailing_stop
                    logger.debug(f"[ENHANCED] Trailing stop updated: ${trailing_stop:.2f}")
        
        else:  # SELL signal
            # Verificar targets (SELL)
            if current_price <= signal['target_3']:
                self._exit_signal(signal, current_price, 'TARGET_3_HIT', 'All targets achieved')
            elif current_price <= signal['target_2']:
                if 'TARGET_2_PARTIAL' not in signal.get('exit_reason', ''):
                    self._partial_exit(signal, current_price, 'TARGET_2_PARTIAL', 0.7)
            elif current_price <= signal['target_1']:
                if 'TARGET_1_PARTIAL' not in signal.get('exit_reason', ''):
                    self._partial_exit(signal, current_price, 'TARGET_1_PARTIAL', 0.5)
            
            # Verificar stop loss
            elif current_price >= signal['stop_loss']:
                self._exit_signal(signal, current_price, 'STOP_LOSS_HIT', 'Stop loss triggered')
            
            # Trailing stop (se em lucro)
            elif current_price < entry_price * 0.98:  # 2% de lucro mínimo
                atr = indicators.get('atr', entry_price * 0.02)
                trailing_stop = current_price + (atr * self.signal_config['trailing_stop_distance'])
                if trailing_stop < signal['stop_loss']:
                    signal['stop_loss'] = trailing_stop
                    logger.debug(f"[ENHANCED] Trailing stop updated: ${trailing_stop:.2f}")
    
    def _partial_exit(self, signal: Dict, exit_price: float, reason: str, percentage: float):
        """Executa saída parcial do sinal"""
        current_reason = signal.get('exit_reason', '')
        if reason not in current_reason:
            signal['exit_reason'] = f"{current_reason} | {reason}" if current_reason else reason
            
            pnl = signal['profit_loss']
            logger.info(f"[ENHANCED] 📈 PARTIAL EXIT ({percentage*100:.0f}%): "
                       f"Signal #{signal['id']} @ ${exit_price:.2f} | PnL: {pnl:.2f}%")
    
    def _exit_signal(self, signal: Dict, exit_price: float, exit_type: str, reason: str):
        """Executa saída completa do sinal"""
        signal['status'] = exit_type
        signal['exit_reason'] = reason
        signal['updated_at'] = datetime.now().isoformat()
        
        pnl = signal['profit_loss']
        max_profit = signal.get('max_profit', 0)
        max_drawdown = signal.get('max_drawdown', 0)
        
        logger.info(f"[ENHANCED] 🏁 SIGNAL CLOSED:")
        logger.info(f"  Signal #{signal['id']} | Type: {signal['signal_type']}")
        logger.info(f"  Entry: ${signal['entry_price']:,.2f} → Exit: ${exit_price:,.2f}")
        logger.info(f"  Final PnL: {pnl:.2f}% | Max Profit: {max_profit:.2f}% | Max DD: {max_drawdown:.2f}%")
        logger.info(f"  Reason: {reason}")
        
        # Atualizar no banco de dados
        self._update_signal_in_db(signal)
    
    # Métodos auxiliares para detectar divergências
    def _detect_rsi_divergence(self, prices: np.ndarray) -> bool:
        """Detecta divergência no RSI"""
        if len(prices) < 30:
            return False
        
        # Implementação simplificada
        recent_highs = np.array([prices[i] for i in range(-10, 0) if i < 0 and abs(i) <= len(prices)])
        if len(recent_highs) < 5:
            return False
        
        price_trend = np.polyfit(range(len(recent_highs)), recent_highs, 1)[0]
        
        # RSI trend (simplificado)
        rsi_values = [self._calculate_rsi_improved(prices[:i+1]) for i in range(-10, 0) if abs(i) <= len(prices)]
        if len(rsi_values) < 5:
            return False
        
        rsi_trend = np.polyfit(range(len(rsi_values)), rsi_values, 1)[0]
        
        # Divergência: preço sobe mas RSI desce (ou vice-versa)
        return (price_trend > 0 and rsi_trend < 0) or (price_trend < 0 and rsi_trend > 0)
    
    def _detect_macd_divergence(self, prices: np.ndarray, histogram: float) -> bool:
        """Detecta divergência no MACD"""
        # Implementação simplificada para esta versão
        return False
    
    def _detect_stochastic_divergence(self, prices: np.ndarray, stoch_k: float) -> bool:
        """Detecta divergência no Stochastic"""
        # Implementação simplificada para esta versão
        return False
    
    def _calculate_bollinger_width(self, prices: np.ndarray, lookback: int) -> float:
        """Calcula largura das Bollinger Bands"""
        if len(prices) < lookback:
            return 0.0
        
        recent_prices = prices[-lookback:]
        std = np.std(recent_prices, ddof=1)
        mean = np.mean(recent_prices)
        
        return (std * 4) / mean  # Largura normalizada
    
    def _classify_volatility_regime(self, atr: float, prices: np.ndarray) -> str:
        """Classifica regime de volatilidade"""
        if len(prices) < 50:
            return 'NORMAL'
        
        # Calcular ATR histórico
        historical_atr = []
        for i in range(20, len(prices)):
            price_slice = prices[i-20:i]
            historical_atr.append(np.std(price_slice) / np.mean(price_slice))
        
        if not historical_atr:
            return 'NORMAL'
        
        avg_atr = np.mean(historical_atr)
        current_vol = atr / prices[-1]
        
        if current_vol > avg_atr * 1.5:
            return 'HIGH'
        elif current_vol < avg_atr * 0.5:
            return 'LOW'
        else:
            return 'NORMAL'
    
    def _analyze_volume_trend(self, volumes: np.ndarray) -> str:
        """Analisa tendência do volume"""
        if len(volumes) < 10:
            return 'NEUTRAL'
        
        recent_volumes = volumes[-10:]
        trend = np.polyfit(range(len(recent_volumes)), recent_volumes, 1)[0]
        
        if trend > np.mean(recent_volumes) * 0.1:
            return 'INCREASING'
        elif trend < -np.mean(recent_volumes) * 0.1:
            return 'DECREASING'
        else:
            return 'NEUTRAL'
    
    def _calculate_support_resistance(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> Tuple[float, float]:
        """Calcula níveis de suporte e resistência"""
        if len(closes) < 20:
            current_price = closes[-1]
            return current_price * 0.98, current_price * 1.02
        
        # Usar pivot points simplificados
        recent_highs = highs[-20:]
        recent_lows = lows[-20:]
        recent_closes = closes[-20:]
        
        # Pivot Point
        pivot = (recent_highs[-1] + recent_lows[-1] + recent_closes[-1]) / 3
        
        # Suporte e Resistência básicos
        support = pivot - (recent_highs[-1] - recent_lows[-1]) * 0.382  # Fibonacci 38.2%
        resistance = pivot + (recent_highs[-1] - recent_lows[-1]) * 0.382
        
        return float(support), float(resistance)
    
    def _calculate_trend_strength(self, prices: np.ndarray) -> float:
        """Calcula força da tendência (0-1)"""
        if len(prices) < 20:
            return 0.5
        
        # Usar ADX simplificado
        recent_prices = prices[-20:]
        
        # Calcular movimentos direcionais
        up_moves = []
        down_moves = []
        
        for i in range(1, len(recent_prices)):
            up_move = recent_prices[i] - recent_prices[i-1] if recent_prices[i] > recent_prices[i-1] else 0
            down_move = recent_prices[i-1] - recent_prices[i] if recent_prices[i] < recent_prices[i-1] else 0
            
            up_moves.append(up_move)
            down_moves.append(down_move)
        
        avg_up = np.mean(up_moves)
        avg_down = np.mean(down_moves)
        
        if avg_up + avg_down == 0:
            return 0.5
        
        di_diff = abs(avg_up - avg_down)
        di_sum = avg_up + avg_down
        
        adx = di_diff / di_sum
        return min(adx, 1.0)
    
    def _determine_trend_direction(self, indicators: Dict) -> str:
        """Determina direção da tendência"""
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
    
    def _can_generate_signal(self) -> bool:
        """Verifica se pode gerar novo sinal (cooldown)"""
        if not self.signals:
            return True
        
        last_signal_time = datetime.fromisoformat(self.signals[-1]['created_at'])
        time_diff = datetime.now() - last_signal_time
        
        return time_diff.total_seconds() >= (self.signal_config['signal_cooldown_minutes'] * 60)
    
    def _update_performance_metrics(self):
        """Atualiza métricas de performance"""
        try:
            today = datetime.now().date().isoformat()
            
            # Contar sinais de hoje
            today_signals = [s for s in self.signals 
                           if s.get('created_at', '').startswith(today)]
            
            if not today_signals:
                return
            
            winning_signals = len([s for s in today_signals 
                                 if s.get('status', '').startswith('TARGET')])
            losing_signals = len([s for s in today_signals 
                                if s.get('status') == 'STOP_LOSS_HIT'])
            
            total_signals = len(today_signals)
            win_rate = (winning_signals / total_signals * 100) if total_signals > 0 else 0
            
            # Calcular profit factor
            total_wins = sum([s.get('profit_loss', 0) for s in today_signals 
                            if s.get('profit_loss', 0) > 0])
            total_losses = abs(sum([s.get('profit_loss', 0) for s in today_signals 
                                   if s.get('profit_loss', 0) < 0]))
            
            profit_factor = (total_wins / total_losses) if total_losses > 0 else float('inf')
            
            # Salvar métricas
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO performance_metrics 
                (date, total_signals, winning_signals, losing_signals, 
                 win_rate, profit_factor, avg_win, avg_loss, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (
                today, total_signals, winning_signals, losing_signals,
                win_rate, profit_factor, 
                total_wins / winning_signals if winning_signals > 0 else 0,
                total_losses / losing_signals if losing_signals > 0 else 0
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error updating performance metrics: {e}")
    
    # Métodos de persistência de dados
    def _save_ohlc_data(self, ohlc_data: Dict):
        """Salva dados OHLC no banco"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO ohlc_data 
                (timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                ohlc_data['timestamp'].isoformat(),
                ohlc_data['open'], ohlc_data['high'], ohlc_data['low'],
                ohlc_data['close'], ohlc_data['volume']
            ))
            
            # Manter apenas dados recentes
            cursor.execute('''
                DELETE FROM ohlc_data 
                WHERE id NOT IN (
                    SELECT id FROM ohlc_data 
                    ORDER BY timestamp DESC 
                    LIMIT 1000
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error saving OHLC data: {e}")
    
    def _save_enhanced_signal(self, signal: Dict):
        """Salva sinal aprimorado no banco"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO enhanced_signals 
                (timestamp, signal_type, entry_price, target_1, target_2, target_3,
                 stop_loss, confidence, confluence_score, risk_reward_ratio, atr_value,
                 volume_confirmation, status, entry_reason, indicators_snapshot,
                 profit_loss, max_profit, max_drawdown, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal['timestamp'], signal['signal_type'], signal['entry_price'],
                signal['target_1'], signal['target_2'], signal['target_3'],
                signal['stop_loss'], signal['confidence'], signal['confluence_score'],
                signal['risk_reward_ratio'], signal['atr_value'], signal['volume_confirmation'],
                signal['status'], signal['entry_reason'], signal['indicators_snapshot'],
                signal['profit_loss'], signal['max_profit'], signal['max_drawdown'],
                signal['created_at']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error saving enhanced signal: {e}")
    
    def _update_signal_in_db(self, signal: Dict):
        """Atualiza sinal no banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE enhanced_signals 
                SET status = ?, profit_loss = ?, max_profit = ?, max_drawdown = ?,
                    exit_reason = ?, updated_at = datetime('now')
                WHERE id = ?
            ''', (
                signal['status'], signal['profit_loss'], 
                signal.get('max_profit', 0), signal.get('max_drawdown', 0),
                signal.get('exit_reason', ''), signal['id']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error updating signal in DB: {e}")
    
    # Métodos públicos para análise e relatórios
    def get_comprehensive_analysis(self) -> Dict:
        """Retorna análise técnica completa atual"""
        if len(self.ohlc_history) < 20:
            return {
                'status': 'INSUFFICIENT_DATA',
                'message': 'Aguardando mais dados para análise completa',
                'data_points': len(self.ohlc_history)
            }
        
        current_ohlc = self.ohlc_history[-1]
        indicators = self._calculate_comprehensive_indicators()
        market_state = self._analyze_market_state(indicators)
        signal_analysis = self._calculate_signal_confluence(indicators, market_state)
        
        # Performance stats
        active_signals = [s for s in self.signals if s.get('status') == 'ACTIVE']
        closed_signals = [s for s in self.signals if s.get('status') not in ['ACTIVE']]
        
        winning_trades = len([s for s in closed_signals if s.get('profit_loss', 0) > 0])
        total_closed = len(closed_signals)
        win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0
        
        return {
            'timestamp': datetime.now().isoformat(),
            'current_price': current_ohlc['close'],
            'ohlc': {
                'open': current_ohlc['open'],
                'high': current_ohlc['high'],
                'low': current_ohlc['low'],
                'close': current_ohlc['close'],
                'volume': current_ohlc['volume']
            },
            'technical_indicators': {
                'RSI': round(indicators.get('rsi', 50), 2),
                'RSI_Signal': 'OVERSOLD' if indicators.get('rsi', 50) < 30 else 'OVERBOUGHT' if indicators.get('rsi', 50) > 70 else 'NEUTRAL',
                'MACD_Line': round(indicators.get('macd_line', 0), 4),
                'MACD_Signal': round(indicators.get('macd_signal', 0), 4),
                'MACD_Histogram': round(indicators.get('macd_histogram', 0), 4),
                'BB_Position': round(indicators.get('bb_position', 0.5), 3),
                'BB_Squeeze': indicators.get('bb_squeeze', False),
                'Stoch_K': round(indicators.get('stoch_k', 50), 2),
                'Stoch_D': round(indicators.get('stoch_d', 50), 2),
                'ATR': round(indicators.get('atr', 0), 2),
                'Volume_Ratio': round(indicators.get('volume_ratio', 1), 2),
                'Support': round(indicators.get('support', 0), 2),
                'Resistance': round(indicators.get('resistance', 0), 2),
                'Trend_Strength': round(indicators.get('trend_strength', 0), 3)
            },
            'market_analysis': {
                'trend': market_state.get('trend', 'NEUTRAL'),
                'volatility': market_state.get('volatility', 'NORMAL'),
                'volume_state': market_state.get('volume', 'NORMAL'),
                'bb_squeeze_active': market_state.get('bb_squeeze', False)
            },
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
                    'type': s['signal_type'],
                    'entry': s['entry_price'],
                    'targets': [s['target_1'], s['target_2'], s['target_3']],
                    'stop_loss': s['stop_loss'],
                    'current_pnl': round(s.get('profit_loss', 0), 2),
                    'max_profit': round(s.get('max_profit', 0), 2),
                    'risk_reward': s['risk_reward_ratio'],
                    'confidence': s['confidence'],
                    'age_hours': (datetime.now() - datetime.fromisoformat(s['created_at'])).total_seconds() / 3600
                }
                for s in active_signals
            ],
            'performance_summary': {
                'total_signals_generated': len(self.signals),
                'active_signals': len(active_signals),
                'closed_signals': total_closed,
                'win_rate': round(win_rate, 1),
                'analysis_count': self.analysis_count,
                'system_uptime_hours': (datetime.now() - (self.last_analysis or datetime.now())).total_seconds() / 3600 if self.last_analysis else 0
            },
            'system_health': {
                'data_quality': 'GOOD' if len(self.ohlc_history) >= 50 else 'FAIR',
                'indicator_status': 'ACTIVE' if indicators else 'CALCULATING',
                'last_analysis': self.last_analysis.isoformat() if self.last_analysis else None,
                'next_signal_cooldown_minutes': max(0, self.signal_config['signal_cooldown_minutes'] - 
                    ((datetime.now() - datetime.fromisoformat(self.signals[-1]['created_at'])).total_seconds() / 60) 
                    if self.signals else 0)
            }
        }
    
    def get_performance_report(self, days: int = 30) -> Dict:
        """Gera relatório de performance detalhado"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Filtrar sinais do período
            recent_signals = [
                s for s in self.signals 
                if datetime.fromisoformat(s.get('created_at', '1970-01-01')) >= cutoff_date
            ]
            
            if not recent_signals:
                return {
                    'period_days': days,
                    'message': f'Nenhum sinal gerado nos últimos {days} dias'
                }
            
            # Calcular estatísticas
            closed_signals = [s for s in recent_signals if s.get('status') not in ['ACTIVE']]
            winning_signals = [s for s in closed_signals if s.get('profit_loss', 0) > 0]
            losing_signals = [s for s in closed_signals if s.get('profit_loss', 0) < 0]
            
            total_trades = len(closed_signals)
            win_count = len(winning_signals)
            loss_count = len(losing_signals)
            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
            
            # Profit/Loss calculations
            total_profit = sum([s.get('profit_loss', 0) for s in winning_signals])
            total_loss = sum([s.get('profit_loss', 0) for s in losing_signals])
            net_profit = total_profit + total_loss  # total_loss já é negativo
            
            avg_win = total_profit / win_count if win_count > 0 else 0
            avg_loss = total_loss / loss_count if loss_count > 0 else 0
            profit_factor = abs(total_profit / total_loss) if total_loss != 0 else float('inf')
            
            # Risk metrics
            max_drawdown = min([s.get('max_drawdown', 0) for s in recent_signals]) if recent_signals else 0
            max_profit = max([s.get('max_profit', 0) for s in recent_signals]) if recent_signals else 0
            
            # Signal type analysis
            signal_types = {}
            for signal in recent_signals:
                sig_type = signal.get('signal_type', 'UNKNOWN')
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
                    'profit_factor': round(profit_factor, 2),
                    'net_profit_pct': round(net_profit, 2),
                    'total_profit_pct': round(total_profit, 2),
                    'total_loss_pct': round(total_loss, 2)
                },
                'trade_statistics': {
                    'winning_trades': win_count,
                    'losing_trades': loss_count,
                    'average_win_pct': round(avg_win, 2),
                    'average_loss_pct': round(avg_loss, 2),
                    'largest_win_pct': round(max([s.get('profit_loss', 0) for s in winning_signals]) if winning_signals else 0, 2),
                    'largest_loss_pct': round(min([s.get('profit_loss', 0) for s in losing_signals]) if losing_signals else 0, 2),
                    'max_consecutive_wins': self._calculate_max_consecutive(recent_signals, 'wins'),
                    'max_consecutive_losses': self._calculate_max_consecutive(recent_signals, 'losses')
                },
                'risk_metrics': {
                    'max_drawdown_pct': round(max_drawdown, 2),
                    'max_profit_pct': round(max_profit, 2),
                    'average_risk_reward': round(np.mean([s.get('risk_reward_ratio', 0) for s in recent_signals]), 2),
                    'sharpe_ratio': self._calculate_sharpe_ratio(recent_signals),
                    'volatility': round(np.std([s.get('profit_loss', 0) for s in closed_signals]), 2) if closed_signals else 0
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
                        'type': s.get('signal_type', ''),
                        'entry': s.get('entry_price', 0),
                        'status': s.get('status', ''),
                        'pnl': round(s.get('profit_loss', 0), 2),
                        'confidence': s.get('confidence', 0),
                        'risk_reward': s.get('risk_reward_ratio', 0)
                    }
                    for s in recent_signals[-10:]  # Últimos 10 sinais
                ]
            }
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error generating performance report: {e}")
            return {'error': str(e)}
    
    def _calculate_max_consecutive(self, signals: List[Dict], win_or_loss: str) -> int:
        """Calcula máximo de vitórias ou derrotas consecutivas"""
        if not signals:
            return 0
        
        max_consecutive = 0
        current_consecutive = 0
        
        for signal in signals:
            if signal.get('status') not in ['TARGET_1_HIT', 'TARGET_2_HIT', 'TARGET_3_HIT', 'STOP_LOSS_HIT']:
                continue
            
            is_win = signal.get('profit_loss', 0) > 0
            
            if (win_or_loss == 'wins' and is_win) or (win_or_loss == 'losses' and not is_win):
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _calculate_sharpe_ratio(self, signals: List[Dict]) -> float:
        """Calcula Sharpe Ratio simplificado"""
        if not signals:
            return 0.0
        
        returns = [s.get('profit_loss', 0) for s in signals if s.get('status') not in ['ACTIVE']]
        
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        
        if std_return == 0:
            return 0.0
        
        # Assumindo risk-free rate de 0% para simplificar
        sharpe = mean_return / std_return
        return round(sharpe, 3)
    
    def get_market_scanner(self) -> Dict:
        """Scanner de mercado para identificar oportunidades"""
        if len(self.ohlc_history) < 30:
            return {
                'status': 'INSUFFICIENT_DATA',
                'message': 'Dados insuficientes para scanner'
            }
        
        indicators = self._calculate_comprehensive_indicators()
        market_state = self._analyze_market_state(indicators)
        signal_analysis = self._calculate_signal_confluence(indicators, market_state)
        
        # Oportunidades identificadas
        opportunities = []
        
        # 1. Oversold/Overbought extremos
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
        
        # 2. Bollinger Band squeeze
        if indicators.get('bb_squeeze', False):
            opportunities.append({
                'type': 'BB_SQUEEZE',
                'description': 'Bollinger Bands em squeeze - breakout iminente',
                'priority': 'MEDIUM',
                'action': 'BREAKOUT_WATCH'
            })
        
        # 3. Volume spike
        volume_ratio = indicators.get('volume_ratio', 1)
        if volume_ratio > 2.0:
            opportunities.append({
                'type': 'VOLUME_SPIKE',
                'description': f'Volume spike detectado ({volume_ratio:.1f}x normal)',
                'priority': 'MEDIUM',
                'action': 'MOMENTUM_WATCH'
            })
        
        # 4. Support/Resistance proximity
        current_price = self.ohlc_history[-1]['close']
        support = indicators.get('support', 0)
        resistance = indicators.get('resistance', 0)
        
        if support > 0 and abs(current_price - support) / current_price < 0.01:  # 1% do suporte
            opportunities.append({
                'type': 'NEAR_SUPPORT',
                'description': f'Preço próximo ao suporte (${support:.2f})',
                'priority': 'MEDIUM',
                'action': 'BOUNCE_WATCH'
            })
        
        if resistance > 0 and abs(current_price - resistance) / current_price < 0.01:  # 1% da resistência
            opportunities.append({
                'type': 'NEAR_RESISTANCE',
                'description': f'Preço próximo à resistência (${resistance:.2f})',
                'priority': 'MEDIUM',
                'action': 'REJECTION_WATCH'
            })
        
        # 5. High confluence signals
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
            },
            'scanner_recommendations': self._generate_scanner_recommendations(opportunities, signal_analysis)
        }
    
    def _generate_scanner_recommendations(self, opportunities: List[Dict], signal_analysis: Dict) -> List[str]:
        """Gera recomendações baseadas no scanner"""
        recommendations = []
        
        high_priority_opps = [opp for opp in opportunities if opp['priority'] == 'HIGH']
        
        if high_priority_opps:
            if len(high_priority_opps) > 1:
                recommendations.append("⚠️ ATENÇÃO: Múltiplas oportunidades de alta prioridade detectadas!")
            
            for opp in high_priority_opps:
                recommendations.append(f"🎯 {opp['description']} - Ação: {opp['action']}")
        
        # Recomendações baseadas na confluência
        confidence = signal_analysis.get('confidence', 0)
        if confidence > 70:
            action = signal_analysis.get('action', 'HOLD')
            recommendations.append(f"📊 Sinal de alta confiança: {action} (Confiança: {confidence:.1f}%)")
        
        # Recomendações de gestão de risco
        active_signals = len([s for s in self.signals if s.get('status') == 'ACTIVE'])
        if active_signals >= self.signal_config['max_active_signals']:
            recommendations.append("🛑 Limite máximo de sinais ativos atingido - aguardar fechamentos")
        
        if not recommendations:
            recommendations.append("📈 Mercado estável - aguardando oportunidades de alta qualidade")
        
        return recommendations
    
    def export_signals_to_csv(self, filename: str = None) -> str:
        """Exporta sinais para CSV"""
        if not filename:
            filename = f"trading_signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            import csv
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'id', 'timestamp', 'signal_type', 'entry_price', 'target_1', 'target_2', 'target_3',
                    'stop_loss', 'confidence', 'confluence_score', 'risk_reward_ratio', 'atr_value',
                    'volume_confirmation', 'status', 'profit_loss', 'max_profit', 'max_drawdown',
                    'entry_reason', 'exit_reason', 'created_at', 'updated_at'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for signal in self.signals:
                    # Filtrar apenas campos que existem no CSV
                    csv_signal = {field: signal.get(field, '') for field in fieldnames}
                    writer.writerow(csv_signal)
            
            logger.info(f"[ENHANCED] Signals exported to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"[ENHANCED] Error exporting signals: {e}")
            return ""
    
    def get_system_status(self) -> Dict:
        """Retorna status completo do sistema"""
        return {
            'system_info': {
                'version': '2.0.0-enhanced',
                'status': 'ACTIVE',
                'uptime_hours': (datetime.now() - (self.last_analysis or datetime.now())).total_seconds() / 3600 if self.last_analysis else 0,
                'total_analysis': self.analysis_count,
                'database_path': self.db_path
            },
            'data_status': {
                'ohlc_data_points': len(self.ohlc_history),
                'price_data_points': len(self.price_history),
                'volume_data_points': len(self.volume_history),
                'data_quality': 'EXCELLENT' if len(self.ohlc_history) >= 100 else 'GOOD' if len(self.ohlc_history) >= 50 else 'FAIR',
                'last_data_timestamp': self.ohlc_history[-1]['timestamp'].isoformat() if self.ohlc_history else None
            },
            'signal_status': {
                'total_signals_generated': len(self.signals),
                'active_signals': len([s for s in self.signals if s.get('status') == 'ACTIVE']),
                'closed_signals': len([s for s in self.signals if s.get('status') not in ['ACTIVE']]),
                'last_signal_time': self.signals[-1]['created_at'] if self.signals else None,
                'next_signal_cooldown_minutes': max(0, self.signal_config['signal_cooldown_minutes'] - 
                    ((datetime.now() - datetime.fromisoformat(self.signals[-1]['created_at'])).total_seconds() / 60) 
                    if self.signals else 0)
            },
            'configuration': {
                'technical_parameters': self.ta_params,
                'signal_configuration': self.signal_config,
                'indicator_weights': self.indicator_weights
            },
            'performance_overview': {
                'win_rate': self._calculate_overall_win_rate(),
                'profit_factor': self._calculate_overall_profit_factor(),
                'total_pnl': round(sum([s.get('profit_loss', 0) for s in self.signals]), 2),
                'active_pnl': round(sum([s.get('profit_loss', 0) for s in self.signals if s.get('status') == 'ACTIVE']), 2)
            }
        }
    
    def _calculate_overall_win_rate(self) -> float:
        """Calcula win rate geral"""
        closed_signals = [s for s in self.signals if s.get('status') not in ['ACTIVE']]
        if not closed_signals:
            return 0.0
        
        winning_signals = len([s for s in closed_signals if s.get('profit_loss', 0) > 0])
        return round((winning_signals / len(closed_signals) * 100), 2)
    
    def _calculate_overall_profit_factor(self) -> float:
        """Calcula profit factor geral"""
        closed_signals = [s for s in self.signals if s.get('status') not in ['ACTIVE']]
        if not closed_signals:
            return 0.0
        
        total_wins = sum([s.get('profit_loss', 0) for s in closed_signals if s.get('profit_loss', 0) > 0])
        total_losses = abs(sum([s.get('profit_loss', 0) for s in closed_signals if s.get('profit_loss', 0) < 0]))
        
        if total_losses == 0:
            return float('inf') if total_wins > 0 else 0.0
        
        return round(total_wins / total_losses, 2)
    
    # Método de compatibilidade com versão anterior
    def add_price_data(self, timestamp, price, volume=0):
        """Método de compatibilidade - converte para OHLC"""
        logger.warning("[ENHANCED] Using compatibility method - recommend switching to add_ohlc_data()")
        
        # Simular OHLC com apenas o preço de fechamento
        self.add_ohlc_data(
            timestamp=timestamp,
            open_price=price,
            high=price * 1.001,  # Simular high/low pequenos
            low=price * 0.999,
            close=price,
            volume=volume
        )
    
    def get_current_analysis(self):
        """Método de compatibilidade"""
        return self.get_comprehensive_analysis()

# Classe para backtesting (bonus)
class EnhancedBacktester:
    """
    Sistema de backtesting para validar estratégias
    """
    
    def __init__(self, analyzer: EnhancedTradingAnalyzer):
        self.analyzer = analyzer
        self.results = []
    
    def run_backtest(self, historical_data: List[Dict], initial_capital: float = 10000) -> Dict:
        """Executa backtesting com dados históricos"""
        capital = initial_capital
        positions = []
        trades = []
        
        for i, data_point in enumerate(historical_data):
            # Simular adição de dados
            self.analyzer.add_ohlc_data(
                timestamp=data_point['timestamp'],
                open_price=data_point['open'],
                high=data_point['high'],
                low=data_point['low'],
                close=data_point['close'],
                volume=data_point.get('volume', 0)
            )
            
            # Verificar sinais gerados
            new_signals = [s for s in self.analyzer.signals if s.get('created_at', '') == data_point['timestamp'].isoformat()]
            
            for signal in new_signals:
                if len(positions) < 3:  # Máximo 3 posições
                    positions.append({
                        'signal': signal,
                        'entry_price': signal['entry_price'],
                        'size': capital * 0.02,  # 2% do capital por trade
                        'entry_time': data_point['timestamp']
                    })
        
        return {
            'initial_capital': initial_capital,
            'final_capital': capital,
            'total_return': ((capital - initial_capital) / initial_capital) * 100,
            'total_trades': len(trades),
            'winning_trades': len([t for t in trades if t['pnl'] > 0]),
            'max_drawdown': 0,  # Calcular
            'sharpe_ratio': 0   # Calcular
        }

# Utilitários de configuração
def create_default_config() -> Dict:
    """Cria configuração padrão do sistema"""
    return {
        'ta_params': {
            'rsi_period': 14,
            'rsi_overbought': 75,
            'rsi_oversold': 25,
            'min_confidence': 70,
            'min_risk_reward': 2.5
        },
        'signal_config': {
            'max_active_signals': 3,
            'signal_cooldown_minutes': 120,
            'target_multipliers': [2.0, 3.5, 5.0]
        },
        'risk_management': {
            'max_portfolio_risk': 0.06,  # 6% do capital total
            'position_size': 0.02,       # 2% por posição
            'stop_loss_atr_multiplier': 2.0
        }
    }

def validate_config(config: Dict) -> bool:
    """Valida configuração do sistema"""
    required_keys = ['ta_params', 'signal_config', 'risk_management']
    return all(key in config for key in required_keys)

# Exemplo de uso e teste
if __name__ == "__main__":
    # Inicializar analyzer
    analyzer = EnhancedTradingAnalyzer()
    
    # Simular dados de teste
    import random
    base_price = 45000
    
    for i in range(100):
        timestamp = datetime.now() - timedelta(hours=100-i)
        
        # Simular movimento de preço
        change = random.uniform(-0.02, 0.02)
        base_price *= (1 + change)
        
        # Simular OHLC
        open_price = base_price
        high = base_price * (1 + abs(change) * 0.5)
        low = base_price * (1 - abs(change) * 0.5)
        close = base_price
        volume = random.uniform(100, 1000)
        
        analyzer.add_ohlc_data(timestamp, open_price, high, low, close, volume)
    
    # Obter análise
    analysis = analyzer.get_comprehensive_analysis()
    print("=== ENHANCED TRADING ANALYZER TEST ===")
    print(f"Current Price: ${analysis['current_price']:,.2f}")
    print(f"Recommended Action: {analysis['signal_analysis']['recommended_action']}")
    print(f"Confidence: {analysis['signal_analysis']['confidence']:.1f}%")
    print(f"Active Signals: {len(analysis['active_signals'])}")
    print(f"System Health: {analysis['system_health']['data_quality']}")
    
    # Obter scanner
    scanner = analyzer.get_market_scanner()
    print(f"\n=== MARKET SCANNER ===")
    print(f"Opportunities Found: {scanner['opportunities_found']}")
    for opp in scanner['opportunities']:
        print(f"- {opp['description']} [{opp['priority']}]")
    
    print("\n=== SYSTEM STATUS ===")
    status = analyzer.get_system_status()
    print(f"Version: {status['system_info']['version']}")
    print(f"Data Quality: {status['data_status']['data_quality']}")
    print(f"Total Signals: {status['signal_status']['total_signals_generated']}")
    print(f"Win Rate: {status['performance_overview']['win_rate']:.1f}%")