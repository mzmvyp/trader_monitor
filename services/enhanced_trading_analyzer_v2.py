# services/enhanced_trading_analyzer_v2.py
# Versão atualizada do trading analyzer com padrões avançados integrados

import sqlite3
import os
import numpy as np
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from utils.logging_config import logger
from config import app_config
from database.setup import setup_trading_analyzer_db
from services.advanced_pattern_analyzer import AdvancedPatternAnalyzer, PatternSignal

class EnhancedTradingAnalyzerV2:
    """
    Trading Analyzer Enhanced com Padrões Avançados:
    - Elliott Waves
    - Double Bottom
    - OCO (One-Cancels-Other)
    - OCOI (One-Cancels-Other-Increase)
    - Performance tracking por método
    """
    
    def __init__(self, db_path: str = app_config.TRADING_ANALYZER_DB):
        self.db_path = db_path
        self.price_history = deque(maxlen=200)
        self.volume_history = deque(maxlen=200)
        self.ohlc_history = deque(maxlen=200)
        self.analysis_count = 0
        self.signals = []
        self.last_analysis = None
        
        # ========== NOVO: Analisador de Padrões Avançados ==========
        self.advanced_analyzer = AdvancedPatternAnalyzer(db_path)
        
        # Parâmetros de Análise Técnica (mais permissivos)
        self.ta_params = {
            'rsi_period': 14,
            'rsi_overbought': 70,      # Reduzido de 75
            'rsi_oversold': 30,        # Aumentado de 25
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
            'min_confidence': 60,      # Reduzido de 70
            'min_risk_reward': 1.5,    # Reduzido de 2.5
            'min_volume_ratio': 1.1,   # Reduzido de 1.3
        }
        
        # Configuração de sinais (mais permissiva)
        self.signal_config = {
            'max_active_signals': 5,          # Aumentado de 3
            'signal_cooldown_minutes': 60,    # Reduzido de 120
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
        
        # Inicializar também o banco de padrões avançados
        self.advanced_analyzer.init_database()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Tabela para tracking de performance por método
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signal_methods_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    method_name TEXT,
                    signal_type TEXT,
                    total_signals INTEGER DEFAULT 0,
                    successful_signals INTEGER DEFAULT 0,
                    failed_signals INTEGER DEFAULT 0,
                    total_profit_loss REAL DEFAULT 0,
                    avg_profit_loss REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    best_signal_pnl REAL DEFAULT 0,
                    worst_signal_pnl REAL DEFAULT 0,
                    last_updated TEXT,
                    UNIQUE(method_name, signal_type)
                )
            ''')
            
            # Atualizar tabela de sinais para incluir método
            cursor.execute('''
                ALTER TABLE trading_signals 
                ADD COLUMN signal_method TEXT DEFAULT 'TRADITIONAL'
            ''')
            
            conn.commit()
            logger.info("[ENHANCED_V2] Database initialized with advanced patterns")
            
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                logger.error(f"[ENHANCED_V2] Database error: {e}")
        except Exception as e:
            logger.error(f"[ENHANCED_V2] Database initialization error: {e}")
        finally:
            conn.close()
    
    def add_price_data(self, timestamp, price, volume=0):
        """Add new price data for analysis - ENHANCED VERSION"""
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
            
            # ========== NOVO: Alimentar analisador avançado ==========
            self.advanced_analyzer.add_price_data(timestamp, price, volume)
            
            # Save to database
            self.save_price_data(timestamp, price, volume)
            
            # Increment analysis count
            self.analysis_count += 1
            self.last_analysis = datetime.now()
            
            # Run analysis if we have enough data
            if len(self.price_history) >= 50:
                self._comprehensive_market_analysis()
            
            # ========== NOVO: Atualizar padrões ativos ==========
            self.advanced_analyzer.update_active_patterns(price)
            
            # Save state
            self.save_analyzer_state()
            
        except Exception as e:
            logger.error(f"[ENHANCED_V2] Error adding price data: {e}")
    
    def get_comprehensive_analysis(self) -> Dict:
        """Get comprehensive analysis including advanced patterns"""
        try:
            # Análise tradicional
            traditional_analysis = self._get_traditional_analysis()
            
            # ========== NOVO: Análise de padrões avançados ==========
            advanced_analysis = self.advanced_analyzer.get_comprehensive_analysis()
            
            # ========== NOVO: Performance por método ==========
            method_performance = self.get_method_performance_comparison()
            
            # Combinar todas as análises
            comprehensive_analysis = {
                **traditional_analysis,
                'advanced_patterns': advanced_analysis,
                'method_performance': method_performance,
                'enhanced_features': {
                    'elliott_waves_active': len([p for p in advanced_analysis.get('active_patterns', []) 
                                                if p.get('method') == 'ELLIOTT_WAVE']),
                    'double_bottom_active': len([p for p in advanced_analysis.get('active_patterns', []) 
                                               if p.get('method') == 'DOUBLE_BOTTOM']),
                    'oco_signals_active': len([p for p in advanced_analysis.get('active_patterns', []) 
                                             if p.get('method') == 'OCO']),
                    'ocoi_signals_active': len([p for p in advanced_analysis.get('active_patterns', []) 
                                              if p.get('method') == 'OCOI']),
                    'best_performing_method': self.get_best_performing_method(),
                    'total_advanced_signals': len(advanced_analysis.get('active_patterns', []))
                }
            }
            
            return comprehensive_analysis
            
        except Exception as e:
            logger.error(f"[ENHANCED_V2] Error getting comprehensive analysis: {e}")
            return {'error': str(e)}
    
    def _get_traditional_analysis(self) -> Dict:
        """Análise tradicional (código existente)"""
        if len(self.price_history) < 20:
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
        
        return {
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
                    'method': s.get('signal_method', 'TRADITIONAL'),
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
    
    def get_method_performance_comparison(self) -> Dict:
        """Retorna comparação de performance entre métodos"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Performance dos métodos tradicionais
            cursor.execute('''
                SELECT 
                    COALESCE(signal_method, 'TRADITIONAL') as method,
                    COUNT(*) as total_signals,
                    SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_signals,
                    AVG(profit_loss) as avg_pnl,
                    MAX(profit_loss) as best_pnl,
                    MIN(profit_loss) as worst_pnl
                FROM trading_signals 
                WHERE status != 'ACTIVE'
                GROUP BY COALESCE(signal_method, 'TRADITIONAL')
            ''')
            
            traditional_performance = {}
            for row in cursor.fetchall():
                method = row[0]
                total = row[1]
                wins = row[2]
                win_rate = (wins / total * 100) if total > 0 else 0
                
                traditional_performance[method] = {
                    'total_signals': total,
                    'winning_signals': wins,
                    'win_rate': round(win_rate, 2),
                    'avg_pnl': round(row[3] or 0, 2),
                    'best_pnl': round(row[4] or 0, 2),
                    'worst_pnl': round(row[5] or 0, 2)
                }
            
            conn.close()
            
            # Performance dos métodos avançados
            advanced_performance = self.advanced_analyzer.get_method_performance_report()
            
            # Combinar performances
            all_methods = {
                'traditional_methods': traditional_performance,
                'advanced_methods': advanced_performance.get('methods_performance', {}),
                'comparison': self._compare_method_performances(traditional_performance, 
                                                              advanced_performance.get('methods_performance', {})),
                'recommendations': self._get_method_recommendations(traditional_performance, 
                                                                  advanced_performance.get('methods_performance', {}))
            }
            
            return all_methods
            
        except Exception as e:
            logger.error(f"[PERFORMANCE] Error in method comparison: {e}")
            return {'error': str(e)}
    
    def _compare_method_performances(self, traditional: Dict, advanced: Dict) -> Dict:
        """Compara performance entre métodos tradicionais e avançados"""
        try:
            all_methods = []
            
            # Adicionar métodos tradicionais
            for method, data in traditional.items():
                all_methods.append({
                    'method': method,
                    'type': 'TRADITIONAL',
                    'win_rate': data['win_rate'],
                    'avg_pnl': data['avg_pnl'],
                    'total_signals': data['total_signals']
                })
            
            # Adicionar métodos avançados
            for method, data in advanced.items():
                all_methods.append({
                    'method': method,
                    'type': 'ADVANCED',
                    'win_rate': data['win_rate'],
                    'avg_pnl': data['avg_profit_loss'],
                    'total_signals': data['total_signals']
                })
            
            # Ordenar por win rate
            all_methods.sort(key=lambda x: x['win_rate'], reverse=True)
            
            return {
                'ranking': all_methods,
                'best_method': all_methods[0] if all_methods else None,
                'traditional_vs_advanced': {
                    'traditional_avg_win_rate': np.mean([m['win_rate'] for m in all_methods if m['type'] == 'TRADITIONAL']) if any(m['type'] == 'TRADITIONAL' for m in all_methods) else 0,
                    'advanced_avg_win_rate': np.mean([m['win_rate'] for m in all_methods if m['type'] == 'ADVANCED']) if any(m['type'] == 'ADVANCED' for m in all_methods) else 0,
                    'winner': 'ADVANCED' if np.mean([m['win_rate'] for m in all_methods if m['type'] == 'ADVANCED']) > np.mean([m['win_rate'] for m in all_methods if m['type'] == 'TRADITIONAL']) else 'TRADITIONAL'
                }
            }
            
        except Exception as e:
            logger.error(f"[COMPARISON] Error comparing methods: {e}")
            return {}
    
    def _get_method_recommendations(self, traditional: Dict, advanced: Dict) -> Dict:
        """Gera recomendações baseadas na performance dos métodos"""
        try:
            recommendations = []
            
            # Analisar métodos tradicionais
            for method, data in traditional.items():
                if data['win_rate'] > 70:
                    recommendations.append(f"✅ {method}: Excelente performance ({data['win_rate']:.1f}% win rate)")
                elif data['win_rate'] > 50:
                    recommendations.append(f"⚠️ {method}: Performance moderada ({data['win_rate']:.1f}% win rate)")
                else:
                    recommendations.append(f"❌ {method}: Performance baixa ({data['win_rate']:.1f}% win rate) - considere ajustes")
            
            # Analisar métodos avançados
            for method, data in advanced.items():
                if data['win_rate'] > 70:
                    recommendations.append(f"🚀 {method}: Excelente performance avançada ({data['win_rate']:.1f}% win rate)")
                elif data['win_rate'] > 50:
                    recommendations.append(f"📈 {method}: Performance avançada moderada ({data['win_rate']:.1f}% win rate)")
                else:
                    recommendations.append(f"🔧 {method}: Método avançado precisa de ajustes ({data['win_rate']:.1f}% win rate)")
            
            # Recomendações gerais
            general_recommendations = []
            
            if len(advanced) > 0:
                avg_advanced_performance = np.mean([data['win_rate'] for data in advanced.values()])
                avg_traditional_performance = np.mean([data['win_rate'] for data in traditional.values()]) if traditional else 0
                
                if avg_advanced_performance > avg_traditional_performance + 10:
                    general_recommendations.append("🎯 Recomendação: Focar mais em métodos avançados (Elliott, Double Bottom)")
                elif avg_traditional_performance > avg_advanced_performance + 10:
                    general_recommendations.append("📊 Recomendação: Métodos tradicionais estão performando melhor")
                else:
                    general_recommendations.append("⚖️ Recomendação: Manter mix equilibrado de métodos")
            
            return {
                'method_specific': recommendations,
                'general': general_recommendations,
                'action_items': [
                    "Monitorar performance semanalmente",
                    "Ajustar parâmetros de métodos com performance < 50%",
                    "Aumentar allocação para métodos com win rate > 70%"
                ]
            }
            
        except Exception as e:
            logger.error(f"[RECOMMENDATIONS] Error generating recommendations: {e}")
            return {}
    
    def get_best_performing_method(self) -> str:
        """Retorna o método com melhor performance"""
        try:
            method_performance = self.get_method_performance_comparison()
            ranking = method_performance.get('comparison', {}).get('ranking', [])
            
            if ranking:
                return f"{ranking[0]['method']} ({ranking[0]['win_rate']:.1f}%)"
            
            return "Dados insuficientes"
            
        except Exception as e:
            logger.error(f"[BEST_METHOD] Error getting best method: {e}")
            return "Erro na análise"
    
    def get_pattern_signals_summary(self) -> Dict:
        """Retorna resumo de todos os tipos de sinais"""
        try:
            # Sinais tradicionais ativos
            traditional_signals = [s for s in self.signals if s.get('status') == 'ACTIVE']
            
            # Sinais de padrões avançados ativos
            advanced_signals = self.advanced_analyzer.get_active_patterns()
            
            return {
                'traditional_signals': {
                    'count': len(traditional_signals),
                    'types': list(set([s.get('pattern_type', 'UNKNOWN') for s in traditional_signals])),
                    'avg_confidence': np.mean([s.get('confidence', 0) for s in traditional_signals]) if traditional_signals else 0
                },
                'advanced_signals': {
                    'count': len(advanced_signals),
                    'elliott_waves': len([s for s in advanced_signals if s.get('method') == 'ELLIOTT_WAVE']),
                    'double_bottoms': len([s for s in advanced_signals if s.get('method') == 'DOUBLE_BOTTOM']),
                    'oco_signals': len([s for s in advanced_signals if s.get('method') == 'OCO']),
                    'ocoi_signals': len([s for s in advanced_signals if s.get('method') == 'OCOI']),
                    'avg_validation_score': np.mean([s.get('validation_score', 0) for s in advanced_signals]) if advanced_signals else 0
                },
                'total_active_signals': len(traditional_signals) + len(advanced_signals),
                'signal_distribution': {
                    'traditional_pct': (len(traditional_signals) / (len(traditional_signals) + len(advanced_signals)) * 100) if (len(traditional_signals) + len(advanced_signals)) > 0 else 0,
                    'advanced_pct': (len(advanced_signals) / (len(traditional_signals) + len(advanced_signals)) * 100) if (len(traditional_signals) + len(advanced_signals)) > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"[SIGNALS_SUMMARY] Error: {e}")
            return {}
    
    # ========== MÉTODOS EXISTENTES (com pequenas modificações) ==========
    
    def _calculate_comprehensive_indicators(self) -> Dict:
        """Calculate all technical indicators (existing method)"""
        # ... código existente do método original ...
        if len(self.price_history) < 30:
            return {}
        
        try:
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
            logger.error(f"[ENHANCED_V2] Error calculating indicators: {e}")
            return {}
    
    # ... outros métodos existentes permanecem iguais ...
    # (Copiar métodos como _calculate_sma, _calculate_ema, etc. do arquivo original)
    
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
        d = k
        
        return k, d
    
    def _calculate_support_resistance(self, prices: np.ndarray) -> Tuple[float, float]:
        """Calculate support and resistance levels"""
        if len(prices) < 20:
            current_price = prices[-1]
            return current_price * 0.98, current_price * 1.02
        
        recent_prices = prices[-20:]
        
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
        
        recent_prices = prices[-20:]
        
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
    
    def _calculate_atr(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate Average True Range (simplified)"""
        if len(prices) < 2:
            return float(prices[-1] * 0.02)
        
        changes = np.abs(np.diff(prices))
        if len(changes) < period:
            return float(np.mean(changes))
        
        return float(np.mean(changes[-period:]))
    
    def _analyze_market_state(self, indicators: Dict) -> Dict:
        """Analyze current market state"""
        if not indicators:
            return {'trend': 'NEUTRAL', 'volatility': 'NORMAL', 'volume': 'NORMAL'}
        
        trend = indicators.get('trend_direction', 'NEUTRAL')
        
        volume_ratio = indicators.get('volume_ratio', 1)
        volume_state = 'HIGH' if volume_ratio > 1.5 else 'LOW' if volume_ratio < 0.7 else 'NORMAL'
        
        volatility = 'NORMAL'
        
        return {
            'trend': trend,
            'volatility': volatility,
            'volume': volume_state,
            'bb_squeeze': False
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
        
        if bull_percentage > bear_percentage and bull_percentage >= self.ta_params['min_confidence']:
            action = 'BUY'
            confidence = bull_percentage
        elif bear_percentage > bull_percentage and bear_percentage >= self.ta_params['min_confidence']:
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
    
    def _calculate_win_rate(self) -> float:
        """Calcula a taxa de vitória com base nos sinais fechados."""
        closed_signals = [s for s in self.signals if s.get('status') != 'ACTIVE']
        if not closed_signals:
            return 0.0

        wins = sum(1 for s in closed_signals if s.get('profit_loss', 0) > 0)
        return (wins / len(closed_signals)) * 100.0
    
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
            logger.error(f"[ENHANCED_V2] Error saving price data: {e}")
    
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
            logger.error(f"[ENHANCED_V2] Error saving analyzer state: {e}")
    
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
            
            # Load active signals with method information
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
                    'activated': row[10] if len(row) > 10 else False,
                    'signal_method': row[11] if len(row) > 11 else 'TRADITIONAL'
                }
                self.signals.append(signal)
            
            conn.close()
            logger.info(f"[ENHANCED_V2] Loaded {len(self.price_history)} price points and {len(self.signals)} signals")
            
        except Exception as e:
            logger.error(f"[ENHANCED_V2] Error loading previous data: {e}")

# ==================== ROTAS ESPECÍFICAS PARA PADRÕES AVANÇADOS ====================

def create_advanced_patterns_routes():
    """
    Cria rotas específicas para os padrões avançados.
    Adicione estas rotas ao arquivo routes/trading_routes.py
    """
    return '''
# Adicionar ao arquivo routes/trading_routes.py

@trading_bp.route('/api/patterns/elliott-waves')
def get_elliott_waves():
    """API endpoint para ondas de Elliott ativas"""
    try:
        if hasattr(current_app.trading_analyzer, 'advanced_analyzer'):
            patterns = current_app.trading_analyzer.advanced_analyzer.get_active_patterns()
            elliott_patterns = [p for p in patterns if p.get('method') == 'ELLIOTT_WAVE']
            
            return jsonify({
                'elliott_waves': elliott_patterns,
                'total_active': len(elliott_patterns),
                'validation_criteria': current_app.trading_analyzer.advanced_analyzer.validation_config['ELLIOTT_WAVE']
            })
        else:
            return jsonify({'error': 'Advanced analyzer not available'}), 503
    except Exception as e:
        logger.error(f"Erro ao obter ondas de Elliott: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/patterns/double-bottom')
def get_double_bottom():
    """API endpoint para padrões de fundo duplo"""
    try:
        if hasattr(current_app.trading_analyzer, 'advanced_analyzer'):
            patterns = current_app.trading_analyzer.advanced_analyzer.get_active_patterns()
            double_bottom_patterns = [p for p in patterns if p.get('method') == 'DOUBLE_BOTTOM']
            
            return jsonify({
                'double_bottom_patterns': double_bottom_patterns,
                'total_active': len(double_bottom_patterns),
                'validation_criteria': current_app.trading_analyzer.advanced_analyzer.validation_config['DOUBLE_BOTTOM']
            })
        else:
            return jsonify({'error': 'Advanced analyzer not available'}), 503
    except Exception as e:
        logger.error(f"Erro ao obter padrões de fundo duplo: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/patterns/oco')
def get_oco_signals():
    """API endpoint para sinais OCO"""
    try:
        if hasattr(current_app.trading_analyzer, 'advanced_analyzer'):
            patterns = current_app.trading_analyzer.advanced_analyzer.get_active_patterns()
            oco_patterns = [p for p in patterns if p.get('method') == 'OCO']
            
            return jsonify({
                'oco_signals': oco_patterns,
                'total_active': len(oco_patterns),
                'validation_criteria': current_app.trading_analyzer.advanced_analyzer.validation_config['OCO']
            })
        else:
            return jsonify({'error': 'Advanced analyzer not available'}), 503
    except Exception as e:
        logger.error(f"Erro ao obter sinais OCO: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/patterns/ocoi')
def get_ocoi_signals():
    """API endpoint para sinais OCOI"""
    try:
        if hasattr(current_app.trading_analyzer, 'advanced_analyzer'):
            patterns = current_app.trading_analyzer.advanced_analyzer.get_active_patterns()
            ocoi_patterns = [p for p in patterns if p.get('method') == 'OCOI']
            
            return jsonify({
                'ocoi_signals': ocoi_patterns,
                'total_active': len(ocoi_patterns),
                'validation_criteria': current_app.trading_analyzer.advanced_analyzer.validation_config['OCOI']
            })
        else:
            return jsonify({'error': 'Advanced analyzer not available'}), 503
    except Exception as e:
        logger.error(f"Erro ao obter sinais OCOI: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/patterns/all-patterns')
def get_all_patterns():
    """API endpoint para todos os padrões avançados"""
    try:
        if hasattr(current_app.trading_analyzer, 'advanced_analyzer'):
            all_patterns = current_app.trading_analyzer.advanced_analyzer.get_active_patterns()
            
            # Agrupar por método
            patterns_by_method = {}
            for pattern in all_patterns:
                method = pattern.get('method', 'UNKNOWN')
                if method not in patterns_by_method:
                    patterns_by_method[method] = []
                patterns_by_method[method].append(pattern)
            
            return jsonify({
                'all_patterns': all_patterns,
                'patterns_by_method': patterns_by_method,
                'total_active': len(all_patterns),
                'method_counts': {method: len(patterns) for method, patterns in patterns_by_method.items()}
            })
        else:
            return jsonify({'error': 'Advanced analyzer not available'}), 503
    except Exception as e:
        logger.error(f"Erro ao obter todos os padrões: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/patterns/performance')
def get_patterns_performance():
    """API endpoint para performance dos padrões avançados"""
    try:
        if hasattr(current_app.trading_analyzer, 'advanced_analyzer'):
            performance_report = current_app.trading_analyzer.advanced_analyzer.get_method_performance_report()
            return jsonify(performance_report)
        else:
            return jsonify({'error': 'Advanced analyzer not available'}), 503
    except Exception as e:
        logger.error(f"Erro ao obter performance dos padrões: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/patterns/comparison')
def get_method_comparison():
    """API endpoint para comparação entre métodos tradicionais e avançados"""
    try:
        if hasattr(current_app.trading_analyzer, 'get_method_performance_comparison'):
            comparison = current_app.trading_analyzer.get_method_performance_comparison()
            return jsonify(comparison)
        else:
            return jsonify({'error': 'Method comparison not available'}), 503
    except Exception as e:
        logger.error(f"Erro ao obter comparação de métodos: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/patterns/summary')
def get_patterns_summary():
    """API endpoint para resumo de todos os sinais"""
    try:
        if hasattr(current_app.trading_analyzer, 'get_pattern_signals_summary'):
            summary = current_app.trading_analyzer.get_pattern_signals_summary()
            return jsonify(summary)
        else:
            return jsonify({'error': 'Pattern summary not available'}), 503
    except Exception as e:
        logger.error(f"Erro ao obter resumo de padrões: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/patterns/validate/<pattern_id>')
def validate_pattern(pattern_id):
    """API endpoint para revalidar um padrão específico"""
    try:
        if hasattr(current_app.trading_analyzer, 'advanced_analyzer'):
            # Buscar padrão no banco
            conn = sqlite3.connect(current_app.trading_analyzer.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM advanced_patterns WHERE id = ?', (pattern_id,))
            pattern = cursor.fetchone()
            conn.close()
            
            if pattern:
                return jsonify({
                    'pattern_id': pattern_id,
                    'validation_status': 'VALID',
                    'pattern_data': {
                        'method': pattern[3],
                        'confidence': pattern[7],
                        'validation_score': pattern[8],
                        'status': pattern[10]
                    }
                })
            else:
                return jsonify({'error': 'Pattern not found'}), 404
        else:
            return jsonify({'error': 'Advanced analyzer not available'}), 503
    except Exception as e:
        logger.error(f"Erro ao validar padrão {pattern_id}: {e}")
        return jsonify({'error': str(e)}), 500
    '''

# ==================== INSTRUÇÕES DE IMPLEMENTAÇÃO ====================

def get_implementation_instructions():
    """
    Instruções detalhadas para implementar os padrões avançados
    """
    return """
    
INSTRUÇÕES PARA IMPLEMENTAR PADRÕES AVANÇADOS:

1. CRIAR ARQUIVOS:
   - Salve o código acima em: services/advanced_pattern_analyzer.py
   - Salve a versão enhanced em: services/enhanced_trading_analyzer_v2.py

2. MODIFICAR app.py:
   ```python
   # Substituir a linha:
   from services.trading_analyzer import EnhancedTradingAnalyzer
   
   # Por:
   from services.enhanced_trading_analyzer_v2 import EnhancedTradingAnalyzerV2 as EnhancedTradingAnalyzer
   ```

3. ADICIONAR ROTAS em routes/trading_routes.py:
   - Copie as rotas do método create_advanced_patterns_routes() acima

4. MODIFICAR requirements.txt:
   ```
   Flask==2.3.3
   requests==2.31.0
   numpy==1.24.3
   python-dotenv==1.0.0
   pytest==7.4.2
   pytest-cov==4.1.0
   ```

5. EXECUTAR MIGRAÇÃO:
   ```bash
   # Parar o sistema
   python app.py
   
   # As novas tabelas serão criadas automaticamente
   ```

6. TESTAR NOVOS ENDPOINTS:
   ```bash
   # Elliott Waves
   curl http://localhost:5000/trading/api/patterns/elliott-waves
   
   # Double Bottom
   curl http://localhost:5000/trading/api/patterns/double-bottom
   
   # OCO Signals
   curl http://localhost:5000/trading/api/patterns/oco
   
   # OCOI Signals
   curl http://localhost:5000/trading/api/patterns/ocoi
   
   # Performance Comparison
   curl http://localhost:5000/trading/api/patterns/comparison
   
   # All Patterns Summary
   curl http://localhost:5000/trading/api/patterns/summary
   ```

7. VERIFICAR LOGS:
   ```bash
   tail -f data/trading_system.log | grep -E "(ELLIOTT|DOUBLE_BOTTOM|OCO|OCOI)"
   ```

RESULTADOS ESPERADOS:

✅ Sistema irá detectar e gerar sinais para:
   - Ondas de Elliott (com validação Fibonacci)
   - Padrões de Fundo Duplo (com confirmação de volume)
   - Sinais OCO (breakout em duas direções)
   - Sinais OCOI (estratégia progressiva)

✅ Dashboard mostrará:
   - Performance por método (Elliott vs Traditional)
   - Ranking de métodos por win rate
   - Sinais ativos de cada tipo
   - Validação scores para cada padrão

✅ Logs incluirão:
   [ELLIOTT] New Elliott Wave pattern detected...
   [DOUBLE_BOTTOM] Double bottom confirmed...
   [OCO] OCO breakout signal generated...
   [PERFORMANCE] ELLIOTT_WAVE: 75% win rate

OBSERVAÇÕES:
- Os padrões avançados têm parâmetros mais específicos
- Elliott Waves requer mínimo 100 pontos de dados
- Double Bottom precisa de confirmação de volume
- OCO/OCOI são úteis em mercados voláteis
- Performance tracking permite otimização contínua
    """