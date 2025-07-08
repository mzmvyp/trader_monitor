# services/advanced_pattern_analyzer.py

import numpy as np
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from utils.logging_config import logger
from config import app_config

@dataclass
class PatternSignal:
    """Classe para representar um sinal de padrão avançado"""
    id: str
    timestamp: datetime
    pattern_type: str
    method: str  # 'ELLIOTT_WAVE', 'DOUBLE_BOTTOM', 'OCO', 'OCOI'
    entry_price: float
    stop_loss: float
    targets: List[float]
    confidence: float
    validation_score: float
    pattern_data: Dict
    created_at: datetime

class AdvancedPatternAnalyzer:
    """
    Analisador Avançado de Padrões com:
    - Ondas de Elliott (5 ondas impulso + 3 ondas correção)
    - Fundo Duplo (Double Bottom)
    - OCO (One-Cancels-Other)
    - OCOI (One-Cancels-Other-Increase)
    """
    
    def __init__(self, db_path: str = app_config.TRADING_ANALYZER_DB):
        self.db_path = db_path
        self.price_history = []
        self.volume_history = []
        self.patterns_detected = []
        self.method_performance = {}
        
        # Configurações de validação para cada método
        self.validation_config = {
            'ELLIOTT_WAVE': {
                'min_wave_ratio': 0.618,  # Fibonacci
                'max_wave_ratio': 1.618,  # Fibonacci
                'min_confirmation_volume': 1.2,
                'wave_tolerance': 0.05,   # 5% tolerância
                'min_waves_required': 5,
                'time_frame_hours': 24
            },
            'DOUBLE_BOTTOM': {
                'max_bottom_difference': 0.02,  # 2% diferença máxima
                'min_peak_height': 0.03,        # 3% altura mínima do pico
                'min_time_between_bottoms': 4,   # 4 horas mínimo
                'max_time_between_bottoms': 48,  # 48 horas máximo
                'volume_confirmation': True,
                'neckline_break_confirmation': True
            },
            'OCO': {
                'stop_distance_pct': 2.0,       # 2% stop loss
                'target_distance_pct': 4.0,     # 4% target
                'max_slippage': 0.1,            # 0.1% slippage máximo
                'execution_timeout_minutes': 5   # 5 minutos timeout
            },
            'OCOI': {
                'initial_stop_pct': 1.5,        # 1.5% stop inicial
                'increment_pct': 0.5,           # 0.5% incremento
                'max_increments': 3,            # máximo 3 incrementos
                'volume_increase_threshold': 1.5 # 50% aumento volume
            }
        }
        
        self.init_database()
        self.load_method_performance()
    
    def init_database(self):
        """Inicializa tabelas para padrões avançados"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Tabela para padrões avançados
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS advanced_patterns (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    pattern_type TEXT,
                    method TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    targets TEXT,  -- JSON array
                    confidence REAL,
                    validation_score REAL,
                    pattern_data TEXT,  -- JSON com dados específicos do padrão
                    status TEXT DEFAULT 'ACTIVE',
                    profit_loss REAL DEFAULT 0,
                    created_at TEXT,
                    closed_at TEXT,
                    close_reason TEXT
                )
            ''')
            
            # Tabela para performance por método
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS method_performance (
                    method TEXT PRIMARY KEY,
                    total_signals INTEGER DEFAULT 0,
                    winning_signals INTEGER DEFAULT 0,
                    losing_signals INTEGER DEFAULT 0,
                    total_profit_loss REAL DEFAULT 0,
                    avg_profit_loss REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    best_signal_id TEXT,
                    worst_signal_id TEXT,
                    last_updated TEXT
                )
            ''')
            
            # Tabela para ondas de Elliott
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS elliott_waves (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id TEXT,
                    wave_number INTEGER,
                    wave_type TEXT,  -- 'IMPULSE', 'CORRECTION'
                    start_price REAL,
                    end_price REAL,
                    start_time TEXT,
                    end_time TEXT,
                    fibonacci_ratio REAL,
                    validation_score REAL,
                    FOREIGN KEY (pattern_id) REFERENCES advanced_patterns(id)
                )
            ''')
            
            conn.commit()
            logger.info("[ADVANCED] Banco de dados de padrões avançados inicializado")
            
        except Exception as e:
            logger.error(f"[ADVANCED] Erro ao inicializar banco: {e}")
        finally:
            conn.close()
    
    def add_price_data(self, timestamp: datetime, price: float, volume: float):
        """Adiciona dados de preço e dispara análise de padrões"""
        self.price_history.append({
            'timestamp': timestamp,
            'price': price,
            'volume': volume
        })
        self.volume_history.append(volume)
        
        # Manter histórico limitado para performance
        if len(self.price_history) > 500:
            self.price_history = self.price_history[-400:]
            self.volume_history = self.volume_history[-400:]
        
        # Analisar padrões se temos dados suficientes
        if len(self.price_history) >= 50:
            self.analyze_all_patterns()
    
    def analyze_all_patterns(self):
        """Executa análise de todos os padrões avançados"""
        try:
            # 1. Análise de Ondas de Elliott
            elliott_signals = self.analyze_elliott_waves()
            
            # 2. Análise de Fundo Duplo
            double_bottom_signals = self.analyze_double_bottom()
            
            # 3. Análise OCO (se houver posições ativas)
            oco_signals = self.analyze_oco_opportunities()
            
            # 4. Análise OCOI (se houver posições ativas)
            ocoi_signals = self.analyze_ocoi_opportunities()
            
            # Processar todos os sinais encontrados
            all_signals = elliott_signals + double_bottom_signals + oco_signals + ocoi_signals
            
            for signal in all_signals:
                self.process_pattern_signal(signal)
                
        except Exception as e:
            logger.error(f"[ADVANCED] Erro na análise de padrões: {e}")
    
    def analyze_elliott_waves(self) -> List[PatternSignal]:
        """Análise de Ondas de Elliott - 5 ondas impulso + 3 correção"""
        if len(self.price_history) < 100:
            return []
        
        try:
            prices = np.array([p['price'] for p in self.price_history[-100:]])
            times = [p['timestamp'] for p in self.price_history[-100:]]
            
            # Encontrar pivôs (máximos e mínimos locais)
            pivots = self.find_pivots(prices, window=5)
            
            if len(pivots) < 8:  # Precisamos de pelo menos 8 pivôs para 5 ondas
                return []
            
            # Tentar identificar padrão de 5 ondas
            wave_patterns = self.identify_elliott_wave_pattern(pivots, prices, times)
            
            signals = []
            for pattern in wave_patterns:
                if self.validate_elliott_wave(pattern):
                    signal = self.create_elliott_wave_signal(pattern)
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"[ELLIOTT] Erro na análise de ondas: {e}")
            return []
    
    def find_pivots(self, prices: np.ndarray, window: int = 5) -> List[Dict]:
        """Encontra pivôs (máximos e mínimos locais)"""
        pivots = []
        
        for i in range(window, len(prices) - window):
            # Verificar se é máximo local
            if all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
               all(prices[i] >= prices[i+j] for j in range(1, window+1)):
                pivots.append({
                    'index': i,
                    'price': prices[i],
                    'type': 'HIGH'
                })
            
            # Verificar se é mínimo local
            elif all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
                 all(prices[i] <= prices[i+j] for j in range(1, window+1)):
                pivots.append({
                    'index': i,
                    'price': prices[i],
                    'type': 'LOW'
                })
        
        return pivots
    
    def identify_elliott_wave_pattern(self, pivots: List[Dict], prices: np.ndarray, times: List[datetime]) -> List[Dict]:
        """Identifica padrões de ondas de Elliott"""
        patterns = []
        
        # Procurar por sequência de 5 ondas impulso
        for i in range(len(pivots) - 8):
            wave_sequence = pivots[i:i+9]  # 9 pivôs para 5 ondas
            
            # Verificar se segue padrão alternado LOW-HIGH-LOW-HIGH...
            if self.is_valid_wave_sequence(wave_sequence):
                # Calcular ratios de Fibonacci
                fibonacci_ratios = self.calculate_fibonacci_ratios(wave_sequence)
                
                # Criar padrão de onda
                pattern = {
                    'waves': wave_sequence,
                    'fibonacci_ratios': fibonacci_ratios,
                    'start_time': times[wave_sequence[0]['index']],
                    'end_time': times[wave_sequence[-1]['index']],
                    'start_price': wave_sequence[0]['price'],
                    'end_price': wave_sequence[-1]['price']
                }
                
                patterns.append(pattern)
        
        return patterns
    
    def is_valid_wave_sequence(self, sequence: List[Dict]) -> bool:
        """Verifica se a sequência de pivôs forma um padrão válido de ondas"""
        if len(sequence) != 9:
            return False
        
        # Padrão deve ser LOW-HIGH-LOW-HIGH-LOW-HIGH-LOW-HIGH-LOW
        expected_pattern = ['LOW', 'HIGH', 'LOW', 'HIGH', 'LOW', 'HIGH', 'LOW', 'HIGH', 'LOW']
        
        for i, pivot in enumerate(sequence):
            if pivot['type'] != expected_pattern[i]:
                return False
        
        return True
    
    def calculate_fibonacci_ratios(self, wave_sequence: List[Dict]) -> Dict:
        """Calcula ratios de Fibonacci para validação das ondas"""
        try:
            # Ondas 1, 3, 5 (impulso) e 2, 4 (correção)
            wave1 = abs(wave_sequence[1]['price'] - wave_sequence[0]['price'])
            wave2 = abs(wave_sequence[2]['price'] - wave_sequence[1]['price'])
            wave3 = abs(wave_sequence[3]['price'] - wave_sequence[2]['price'])
            wave4 = abs(wave_sequence[4]['price'] - wave_sequence[3]['price'])
            wave5 = abs(wave_sequence[5]['price'] - wave_sequence[4]['price'])
            
            ratios = {
                'wave2_to_wave1': wave2 / wave1 if wave1 > 0 else 0,
                'wave3_to_wave1': wave3 / wave1 if wave1 > 0 else 0,
                'wave4_to_wave3': wave4 / wave3 if wave3 > 0 else 0,
                'wave5_to_wave1': wave5 / wave1 if wave1 > 0 else 0,
                'wave5_to_wave3': wave5 / wave3 if wave3 > 0 else 0
            }
            
            return ratios
            
        except Exception as e:
            logger.error(f"[ELLIOTT] Erro no cálculo de ratios: {e}")
            return {}
    
    def validate_elliott_wave(self, pattern: Dict) -> bool:
        """Valida se o padrão de Elliott atende aos critérios"""
        try:
            ratios = pattern['fibonacci_ratios']
            config = self.validation_config['ELLIOTT_WAVE']
            
            # Verificar ratios de Fibonacci típicos
            # Onda 2: normalmente 50-78.6% retração da onda 1
            if not (0.5 <= ratios.get('wave2_to_wave1', 0) <= 0.786):
                return False
            
            # Onda 3: normalmente 1.618x a onda 1 (maior onda)
            if not (1.0 <= ratios.get('wave3_to_wave1', 0) <= 2.618):
                return False
            
            # Onda 4: normalmente 23.6-50% retração da onda 3
            if not (0.236 <= ratios.get('wave4_to_wave3', 0) <= 0.5):
                return False
            
            # Onda 5: normalmente igual à onda 1 ou 0.618x onda 1
            wave5_ratio = ratios.get('wave5_to_wave1', 0)
            if not (0.618 <= wave5_ratio <= 1.618):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"[ELLIOTT] Erro na validação: {e}")
            return False
    
    def create_elliott_wave_signal(self, pattern: Dict) -> PatternSignal:
        """Cria sinal baseado no padrão de Elliott identificado"""
        try:
            current_price = self.price_history[-1]['price']
            wave_sequence = pattern['waves']
            
            # Determinar direção baseada na última onda
            last_wave_direction = "UP" if wave_sequence[-1]['price'] > wave_sequence[-2]['price'] else "DOWN"
            
            if last_wave_direction == "UP":
                # Sinal de compra no final da onda 5 ou início da correção
                entry_price = current_price
                stop_loss = current_price * 0.97  # 3% stop
                targets = [
                    current_price * 1.05,  # 5% target
                    current_price * 1.08,  # 8% target
                    current_price * 1.12   # 12% target
                ]
                pattern_type = "ELLIOTT_WAVE_BUY"
            else:
                # Sinal de venda
                entry_price = current_price
                stop_loss = current_price * 1.03  # 3% stop
                targets = [
                    current_price * 0.95,  # 5% target
                    current_price * 0.92,  # 8% target
                    current_price * 0.88   # 12% target
                ]
                pattern_type = "ELLIOTT_WAVE_SELL"
            
            # Calcular score de validação
            validation_score = self.calculate_elliott_validation_score(pattern)
            
            signal = PatternSignal(
                id=f"elliott_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now(),
                pattern_type=pattern_type,
                method="ELLIOTT_WAVE",
                entry_price=entry_price,
                stop_loss=stop_loss,
                targets=targets,
                confidence=min(90, validation_score * 100),
                validation_score=validation_score,
                pattern_data=pattern,
                created_at=datetime.now()
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"[ELLIOTT] Erro ao criar sinal: {e}")
            return None
    
    def calculate_elliott_validation_score(self, pattern: Dict) -> float:
        """Calcula score de validação para Elliott Wave (0-1)"""
        try:
            score = 0.0
            ratios = pattern['fibonacci_ratios']
            
            # Score baseado na proximidade aos ratios de Fibonacci ideais
            # Onda 2: ideal 61.8%
            wave2_score = 1.0 - abs(ratios.get('wave2_to_wave1', 0) - 0.618) / 0.618
            score += max(0, wave2_score) * 0.3
            
            # Onda 3: ideal 161.8%
            wave3_score = 1.0 - abs(ratios.get('wave3_to_wave1', 0) - 1.618) / 1.618
            score += max(0, wave3_score) * 0.4
            
            # Onda 4: ideal 38.2%
            wave4_score = 1.0 - abs(ratios.get('wave4_to_wave3', 0) - 0.382) / 0.382
            score += max(0, wave4_score) * 0.2
            
            # Onda 5: ideal 100%
            wave5_score = 1.0 - abs(ratios.get('wave5_to_wave1', 0) - 1.0)
            score += max(0, wave5_score) * 0.1
            
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"[ELLIOTT] Erro no score: {e}")
            return 0.5
    
    def analyze_double_bottom(self) -> List[PatternSignal]:
        """Análise de Fundo Duplo (Double Bottom)"""
        if len(self.price_history) < 50:
            return []
        
        try:
            prices = np.array([p['price'] for p in self.price_history[-100:]])
            times = [p['timestamp'] for p in self.price_history[-100:]]
            volumes = np.array([p['volume'] for p in self.price_history[-100:]])
            
            # Encontrar mínimos locais
            lows = self.find_local_minima(prices, window=10)
            
            if len(lows) < 2:
                return []
            
            signals = []
            
            # Procurar por pares de mínimos que formem fundo duplo
            for i in range(len(lows) - 1):
                for j in range(i + 1, len(lows)):
                    pattern = self.check_double_bottom_pattern(lows[i], lows[j], prices, times, volumes)
                    
                    if pattern and self.validate_double_bottom(pattern):
                        signal = self.create_double_bottom_signal(pattern)
                        if signal:
                            signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"[DOUBLE_BOTTOM] Erro na análise: {e}")
            return []
    
    def find_local_minima(self, prices: np.ndarray, window: int = 10) -> List[Dict]:
        """Encontra mínimos locais"""
        minima = []
        
        for i in range(window, len(prices) - window):
            if all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
               all(prices[i] <= prices[i+j] for j in range(1, window+1)):
                minima.append({
                    'index': i,
                    'price': prices[i]
                })
        
        return minima
    
    def check_double_bottom_pattern(self, low1: Dict, low2: Dict, prices: np.ndarray, 
                                   times: List[datetime], volumes: np.ndarray) -> Optional[Dict]:
        """Verifica se dois mínimos formam um padrão de fundo duplo válido"""
        try:
            config = self.validation_config['DOUBLE_BOTTOM']
            
            # Verificar diferença de preço entre os dois fundos
            price_diff = abs(low1['price'] - low2['price']) / min(low1['price'], low2['price'])
            if price_diff > config['max_bottom_difference']:
                return None
            
            # Verificar tempo entre os fundos
            time_diff_hours = (times[low2['index']] - times[low1['index']]).total_seconds() / 3600
            if not (config['min_time_between_bottoms'] <= time_diff_hours <= config['max_time_between_bottoms']):
                return None
            
            # Encontrar o pico entre os dois fundos
            start_idx = low1['index']
            end_idx = low2['index']
            peak_idx = start_idx + np.argmax(prices[start_idx:end_idx])
            peak_price = prices[peak_idx]
            
            # Verificar altura do pico
            peak_height = (peak_price - min(low1['price'], low2['price'])) / min(low1['price'], low2['price'])
            if peak_height < config['min_peak_height']:
                return None
            
            # Criar padrão
            pattern = {
                'low1': low1,
                'low2': low2,
                'peak': {'index': peak_idx, 'price': peak_price},
                'neckline': peak_price,
                'start_time': times[low1['index']],
                'end_time': times[low2['index']],
                'time_diff_hours': time_diff_hours,
                'price_diff_pct': price_diff * 100,
                'peak_height_pct': peak_height * 100,
                'volume_confirmation': self.check_volume_confirmation(volumes, start_idx, end_idx)
            }
            
            return pattern
            
        except Exception as e:
            logger.error(f"[DOUBLE_BOTTOM] Erro na verificação: {e}")
            return None
    
    def check_volume_confirmation(self, volumes: np.ndarray, start_idx: int, end_idx: int) -> bool:
        """Verifica confirmação de volume para fundo duplo"""
        try:
            # Volume no segundo fundo deve ser menor que no primeiro (divergência)
            volume1 = volumes[start_idx]
            volume2 = volumes[end_idx]
            
            return volume2 < volume1
            
        except:
            return False
    
    def validate_double_bottom(self, pattern: Dict) -> bool:
        """Valida se o padrão de fundo duplo atende aos critérios"""
        try:
            config = self.validation_config['DOUBLE_BOTTOM']
            
            # Verificar se neckline foi quebrada (preço atual deve estar acima)
            current_price = self.price_history[-1]['price']
            if config['neckline_break_confirmation'] and current_price <= pattern['neckline']:
                return False
            
            # Verificar confirmação de volume se necessário
            if config['volume_confirmation'] and not pattern['volume_confirmation']:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"[DOUBLE_BOTTOM] Erro na validação: {e}")
            return False
    
    def create_double_bottom_signal(self, pattern: Dict) -> Optional[PatternSignal]:
        """Cria sinal baseado no padrão de fundo duplo"""
        try:
            current_price = self.price_history[-1]['price']
            neckline = pattern['neckline']
            
            # Sinal de compra após quebra da neckline
            entry_price = current_price
            stop_loss = max(pattern['low1']['price'], pattern['low2']['price']) * 0.99  # 1% abaixo do fundo
            
            # Targets baseados na altura do padrão
            pattern_height = neckline - min(pattern['low1']['price'], pattern['low2']['price'])
            targets = [
                neckline + pattern_height * 0.5,  # 50% da altura
                neckline + pattern_height * 1.0,  # 100% da altura
                neckline + pattern_height * 1.618  # 161.8% da altura (Fibonacci)
            ]
            
            # Calcular score de validação
            validation_score = self.calculate_double_bottom_score(pattern)
            
            signal = PatternSignal(
                id=f"double_bottom_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now(),
                pattern_type="DOUBLE_BOTTOM_BUY",
                method="DOUBLE_BOTTOM",
                entry_price=entry_price,
                stop_loss=stop_loss,
                targets=targets,
                confidence=min(95, validation_score * 100),
                validation_score=validation_score,
                pattern_data=pattern,
                created_at=datetime.now()
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"[DOUBLE_BOTTOM] Erro ao criar sinal: {e}")
            return None
    
    def calculate_double_bottom_score(self, pattern: Dict) -> float:
        """Calcula score de validação para Double Bottom (0-1)"""
        try:
            score = 0.0
            
            # Score baseado na simetria dos fundos
            price_symmetry = 1.0 - (pattern['price_diff_pct'] / 2.0)  # Max 2% diferença
            score += max(0, price_symmetry) * 0.3
            
            # Score baseado na altura do pico
            peak_score = min(1.0, pattern['peak_height_pct'] / 5.0)  # Ideal 5%+
            score += peak_score * 0.3
            
            # Score baseado no tempo entre fundos
            time_score = min(1.0, pattern['time_diff_hours'] / 24.0)  # Ideal 24h+
            score += time_score * 0.2
            
            # Score de confirmação de volume
            volume_score = 1.0 if pattern['volume_confirmation'] else 0.5
            score += volume_score * 0.2
            
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"[DOUBLE_BOTTOM] Erro no score: {e}")
            return 0.5
    
    def analyze_oco_opportunities(self) -> List[PatternSignal]:
        """Análise de oportunidades OCO (One-Cancels-Other)"""
        # OCO é usado quando há incerteza sobre direção
        # Coloca ordens de compra e venda simultaneamente
        
        signals = []
        
        try:
            if len(self.price_history) < 20:
                return signals
            
            current_price = self.price_history[-1]['price']
            volatility = self.calculate_recent_volatility()
            
            # OCO é útil em momentos de baixa volatilidade antes de breakouts
            if volatility < 0.02:  # Volatilidade baixa (< 2%)
                signal = self.create_oco_signal(current_price, volatility)
                if signal:
                    signals.append(signal)
            
        except Exception as e:
            logger.error(f"[OCO] Erro na análise: {e}")
        
        return signals
    
    def analyze_ocoi_opportunities(self) -> List[PatternSignal]:
        """Análise de oportunidades OCOI (One-Cancels-Other-Increase)"""
        # OCOI é uma estratégia progressiva que aumenta posição em breakouts
        
        signals = []
        
        try:
            if len(self.price_history) < 30:
                return signals
            
            # Detectar breakouts com volume crescente
            if self.detect_volume_breakout():
                current_price = self.price_history[-1]['price']
                signal = self.create_ocoi_signal(current_price)
                if signal:
                    signals.append(signal)
            
        except Exception as e:
            logger.error(f"[OCOI] Erro na análise: {e}")
        
        return signals
    
    def calculate_recent_volatility(self) -> float:
        """Calcula volatilidade recente"""
        try:
            prices = [p['price'] for p in self.price_history[-20:]]
            returns = [prices[i]/prices[i-1] - 1 for i in range(1, len(prices))]
            return np.std(returns)
        except:
            return 0.02
    
    def detect_volume_breakout(self) -> bool:
        """Detecta breakout com confirmação de volume"""
        try:
            volumes = [p['volume'] for p in self.volume_history[-10:]]
            avg_volume = np.mean(volumes[:-3])
            recent_volume = np.mean(volumes[-3:])
            
            return recent_volume > avg_volume * 1.5  # 50% aumento no volume
        except:
            return False
    
    def create_oco_signal(self, current_price: float, volatility: float) -> Optional[PatternSignal]:
        """Cria sinal OCO"""
        try:
            config = self.validation_config['OCO']
            
            # OCO coloca duas ordens: uma de compra acima e uma de venda abaixo
            buy_price = current_price * (1 + config['target_distance_pct'] / 100)
            sell_price = current_price * (1 - config['target_distance_pct'] / 100)
            
            # Stops baseados na volatilidade
            stop_distance = max(volatility * 2, config['stop_distance_pct'] / 100)
            buy_stop = buy_price * (1 - stop_distance)
            sell_stop = sell_price * (1 + stop_distance)
            
            signal = PatternSignal(
                id=f"oco_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now(),
                pattern_type="OCO_BREAKOUT",
                method="OCO",
                entry_price=current_price,
                stop_loss=0,  # OCO tem stops separados
                targets=[buy_price, sell_price],  # Duas direções possíveis
                confidence=70,
                validation_score=0.7,
                pattern_data={
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'buy_stop': buy_stop,
                    'sell_stop': sell_stop,
                    'volatility': volatility,
                    'breakout_threshold': config['target_distance_pct']
                },
                created_at=datetime.now()
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"[OCO] Erro ao criar sinal: {e}")
            return None
    
    def create_ocoi_signal(self, current_price: float) -> Optional[PatternSignal]:
        """Cria sinal OCOI (One-Cancels-Other-Increase)"""
        try:
            config = self.validation_config['OCOI']
            
            # OCOI aumenta posição conforme breakout se confirma
            initial_stop = current_price * (1 - config['initial_stop_pct'] / 100)
            
            # Targets escalonados com incrementos
            targets = []
            for i in range(config['max_increments']):
                increment = (i + 1) * config['increment_pct'] / 100
                targets.append(current_price * (1 + increment))
            
            signal = PatternSignal(
                id=f"ocoi_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now(),
                pattern_type="OCOI_PROGRESSIVE",
                method="OCOI",
                entry_price=current_price,
                stop_loss=initial_stop,
                targets=targets,
                confidence=75,
                validation_score=0.75,
                pattern_data={
                    'initial_stop_pct': config['initial_stop_pct'],
                    'increment_pct': config['increment_pct'],
                    'max_increments': config['max_increments'],
                    'volume_threshold': config['volume_increase_threshold']
                },
                created_at=datetime.now()
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"[OCOI] Erro ao criar sinal: {e}")
            return None
    
    def process_pattern_signal(self, signal: PatternSignal):
        """Processa e salva sinal de padrão no banco de dados"""
        try:
            # Verificar se já existe sinal similar recente
            if self.is_duplicate_signal(signal):
                logger.debug(f"[PATTERN] Sinal duplicado ignorado: {signal.method}")
                return
            
            # Salvar no banco
            self.save_pattern_signal(signal)
            
            # Adicionar à lista de padrões detectados
            self.patterns_detected.append(signal)
            
            # Atualizar performance do método
            self.update_method_performance(signal.method, 'SIGNAL_CREATED')
            
            logger.info(f"[PATTERN] Novo sinal {signal.method}: {signal.pattern_type} @ ${signal.entry_price:.2f}")
            
        except Exception as e:
            logger.error(f"[PATTERN] Erro ao processar sinal: {e}")
    
    def is_duplicate_signal(self, signal: PatternSignal) -> bool:
        """Verifica se já existe sinal similar recente"""
        try:
            # Verificar últimos 5 sinais do mesmo método
            recent_signals = [s for s in self.patterns_detected[-5:] if s.method == signal.method]
            
            for recent in recent_signals:
                time_diff = (signal.timestamp - recent.timestamp).total_seconds() / 60
                price_diff = abs(signal.entry_price - recent.entry_price) / recent.entry_price
                
                # Considerado duplicado se menos de 30 minutos e preço similar
                if time_diff < 30 and price_diff < 0.01:  # 1% diferença
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"[PATTERN] Erro na verificação de duplicata: {e}")
            return False
    
    def save_pattern_signal(self, signal: PatternSignal):
        """Salva sinal de padrão no banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO advanced_patterns 
                (id, timestamp, pattern_type, method, entry_price, stop_loss, targets,
                 confidence, validation_score, pattern_data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal.id,
                signal.timestamp.isoformat(),
                signal.pattern_type,
                signal.method,
                signal.entry_price,
                signal.stop_loss,
                str(signal.targets),  # Convert list to string
                signal.confidence,
                signal.validation_score,
                str(signal.pattern_data),  # Convert dict to string
                signal.created_at.isoformat()
            ))
            
            # Se for Elliott Wave, salvar ondas individuais
            if signal.method == "ELLIOTT_WAVE" and 'waves' in signal.pattern_data:
                self.save_elliott_waves(signal.id, signal.pattern_data['waves'])
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[PATTERN] Erro ao salvar sinal: {e}")
    
    def save_elliott_waves(self, pattern_id: str, waves: List[Dict]):
        """Salva ondas individuais de Elliott"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for i, wave in enumerate(waves):
                cursor.execute('''
                    INSERT INTO elliott_waves 
                    (pattern_id, wave_number, wave_type, start_price, end_price, 
                     start_time, end_time, fibonacci_ratio, validation_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    pattern_id,
                    i + 1,
                    'IMPULSE' if i % 2 == 0 else 'CORRECTION',
                    wave['price'],
                    waves[i + 1]['price'] if i < len(waves) - 1 else wave['price'],
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    0.618,  # Placeholder
                    0.8     # Placeholder
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[ELLIOTT] Erro ao salvar ondas: {e}")
    
    def update_method_performance(self, method: str, action: str, profit_loss: float = 0):
        """Atualiza performance por método"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Buscar performance atual
            cursor.execute('SELECT * FROM method_performance WHERE method = ?', (method,))
            current = cursor.fetchone()
            
            if current is None:
                # Criar novo registro
                cursor.execute('''
                    INSERT INTO method_performance 
                    (method, total_signals, winning_signals, losing_signals, 
                     total_profit_loss, avg_profit_loss, win_rate, last_updated)
                    VALUES (?, 1, 0, 0, 0, 0, 0, ?)
                ''', (method, datetime.now().isoformat()))
            else:
                # Atualizar existente
                total_signals = current[1]
                winning_signals = current[2]
                losing_signals = current[3]
                total_pnl = current[4]
                
                if action == 'SIGNAL_CREATED':
                    total_signals += 1
                elif action == 'SIGNAL_CLOSED':
                    if profit_loss > 0:
                        winning_signals += 1
                    else:
                        losing_signals += 1
                    total_pnl += profit_loss
                
                # Calcular métricas
                closed_signals = winning_signals + losing_signals
                win_rate = (winning_signals / closed_signals * 100) if closed_signals > 0 else 0
                avg_pnl = total_pnl / closed_signals if closed_signals > 0 else 0
                
                cursor.execute('''
                    UPDATE method_performance 
                    SET total_signals = ?, winning_signals = ?, losing_signals = ?,
                        total_profit_loss = ?, avg_profit_loss = ?, win_rate = ?,
                        last_updated = ?
                    WHERE method = ?
                ''', (
                    total_signals, winning_signals, losing_signals,
                    total_pnl, avg_pnl, win_rate,
                    datetime.now().isoformat(), method
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[PERFORMANCE] Erro ao atualizar performance: {e}")
    
    def load_method_performance(self):
        """Carrega performance dos métodos do banco"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM method_performance')
            rows = cursor.fetchall()
            
            self.method_performance = {}
            for row in rows:
                self.method_performance[row[0]] = {
                    'total_signals': row[1],
                    'winning_signals': row[2],
                    'losing_signals': row[3],
                    'total_profit_loss': row[4],
                    'avg_profit_loss': row[5],
                    'win_rate': row[6],
                    'best_signal_id': row[7],
                    'worst_signal_id': row[8],
                    'last_updated': row[9]
                }
            
            conn.close()
            
        except Exception as e:
            logger.error(f"[PERFORMANCE] Erro ao carregar performance: {e}")
    
    def get_method_performance_report(self) -> Dict:
        """Retorna relatório de performance por método"""
        try:
            self.load_method_performance()
            
            # Adicionar ranking dos métodos
            methods_by_performance = sorted(
                self.method_performance.items(),
                key=lambda x: x[1]['win_rate'],
                reverse=True
            )
            
            report = {
                'total_methods': len(self.method_performance),
                'methods_performance': self.method_performance,
                'best_method': methods_by_performance[0][0] if methods_by_performance else None,
                'worst_method': methods_by_performance[-1][0] if methods_by_performance else None,
                'ranking': [{'method': method, 'win_rate': data['win_rate']} 
                           for method, data in methods_by_performance],
                'summary': {
                    'total_signals': sum(data['total_signals'] for data in self.method_performance.values()),
                    'total_profit_loss': sum(data['total_profit_loss'] for data in self.method_performance.values()),
                    'avg_win_rate': np.mean([data['win_rate'] for data in self.method_performance.values()]) if self.method_performance else 0
                }
            }
            
            return report
            
        except Exception as e:
            logger.error(f"[PERFORMANCE] Erro no relatório: {e}")
            return {'error': str(e)}
    
    def get_active_patterns(self) -> List[Dict]:
        """Retorna padrões ativos"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM advanced_patterns 
                WHERE status = 'ACTIVE' 
                ORDER BY created_at DESC
            ''')
            
            rows = cursor.fetchall()
            patterns = []
            
            for row in rows:
                patterns.append({
                    'id': row[0],
                    'timestamp': row[1],
                    'pattern_type': row[2],
                    'method': row[3],
                    'entry_price': row[4],
                    'stop_loss': row[5],
                    'targets': eval(row[6]) if row[6] else [],  # Convert string back to list
                    'confidence': row[7],
                    'validation_score': row[8],
                    'status': row[10],
                    'profit_loss': row[11],
                    'created_at': row[12]
                })
            
            conn.close()
            return patterns
            
        except Exception as e:
            logger.error(f"[PATTERNS] Erro ao buscar padrões ativos: {e}")
            return []
    
    def update_active_patterns(self, current_price: float):
        """Atualiza status dos padrões ativos"""
        try:
            active_patterns = self.get_active_patterns()
            
            for pattern in active_patterns:
                updated = False
                
                # Verificar stop loss
                if pattern['stop_loss'] > 0:
                    if (pattern['pattern_type'].endswith('_BUY') and current_price <= pattern['stop_loss']) or \
                       (pattern['pattern_type'].endswith('_SELL') and current_price >= pattern['stop_loss']):
                        self.close_pattern(pattern['id'], 'HIT_STOP', current_price)
                        updated = True
                
                # Verificar targets
                if not updated and pattern['targets']:
                    for i, target in enumerate(pattern['targets']):
                        if (pattern['pattern_type'].endswith('_BUY') and current_price >= target) or \
                           (pattern['pattern_type'].endswith('_SELL') and current_price <= target):
                            self.close_pattern(pattern['id'], f'HIT_TARGET_{i+1}', current_price)
                            updated = True
                            break
                
                # Atualizar P&L se ainda ativo
                if not updated:
                    profit_loss = self.calculate_pattern_pnl(pattern, current_price)
                    self.update_pattern_pnl(pattern['id'], profit_loss)
            
        except Exception as e:
            logger.error(f"[PATTERNS] Erro ao atualizar padrões: {e}")
    
    def close_pattern(self, pattern_id: str, reason: str, exit_price: float):
        """Fecha um padrão e atualiza performance"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Buscar padrão
            cursor.execute('SELECT * FROM advanced_patterns WHERE id = ?', (pattern_id,))
            pattern = cursor.fetchone()
            
            if pattern:
                # Calcular P&L final
                entry_price = pattern[4]
                if pattern[2].endswith('_BUY'):
                    pnl = ((exit_price - entry_price) / entry_price) * 100
                else:
                    pnl = ((entry_price - exit_price) / entry_price) * 100
                
                # Atualizar status
                cursor.execute('''
                    UPDATE advanced_patterns 
                    SET status = ?, profit_loss = ?, closed_at = ?, close_reason = ?
                    WHERE id = ?
                ''', (reason, pnl, datetime.now().isoformat(), reason, pattern_id))
                
                # Atualizar performance do método
                method = pattern[3]
                self.update_method_performance(method, 'SIGNAL_CLOSED', pnl)
                
                logger.info(f"[PATTERN] {method} fechado: {reason} | P&L: {pnl:.2f}%")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[PATTERNS] Erro ao fechar padrão: {e}")
    
    def calculate_pattern_pnl(self, pattern: Dict, current_price: float) -> float:
        """Calcula P&L atual de um padrão"""
        try:
            entry_price = pattern['entry_price']
            
            if pattern['pattern_type'].endswith('_BUY'):
                return ((current_price - entry_price) / entry_price) * 100
            else:
                return ((entry_price - current_price) / entry_price) * 100
                
        except:
            return 0.0
    
    def update_pattern_pnl(self, pattern_id: str, pnl: float):
        """Atualiza P&L de um padrão"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE advanced_patterns 
                SET profit_loss = ? 
                WHERE id = ?
            ''', (pnl, pattern_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[PATTERNS] Erro ao atualizar P&L: {e}")
    
    def get_comprehensive_analysis(self) -> Dict:
        """Retorna análise completa dos padrões avançados"""
        try:
            return {
                'timestamp': datetime.now().isoformat(),
                'active_patterns': self.get_active_patterns(),
                'method_performance': self.get_method_performance_report(),
                'pattern_summary': {
                    'elliott_waves_detected': len([p for p in self.patterns_detected if p.method == 'ELLIOTT_WAVE']),
                    'double_bottoms_detected': len([p for p in self.patterns_detected if p.method == 'DOUBLE_BOTTOM']),
                    'oco_signals': len([p for p in self.patterns_detected if p.method == 'OCO']),
                    'ocoi_signals': len([p for p in self.patterns_detected if p.method == 'OCOI']),
                    'total_patterns': len(self.patterns_detected)
                },
                'validation_config': self.validation_config,
                'recent_analysis': {
                    'data_points': len(self.price_history),
                    'last_analysis': datetime.now().isoformat(),
                    'system_status': 'ACTIVE'
                }
            }
            
        except Exception as e:
            logger.error(f"[ANALYSIS] Erro na análise completa: {e}")
            return {'error': str(e)}

# ==================== INTEGRAÇÃO COM O SISTEMA PRINCIPAL ====================

def integrate_advanced_patterns():
    """
    Função para integrar o analisador avançado com o sistema principal.
    Adicione esta função ao trading_analyzer.py existente.
    """
    return """
    # Adicionar no __init__ do EnhancedTradingAnalyzer:
    
    def __init__(self, db_path: str = app_config.TRADING_ANALYZER_DB):
        # ... código existente ...
        
        # NOVO: Adicionar analisador de padrões avançados
        self.advanced_analyzer = AdvancedPatternAnalyzer(db_path)
        
    def add_price_data(self, timestamp, price, volume=0):
        # ... código existente ...
        
        # NOVO: Alimentar também o analisador avançado
        self.advanced_analyzer.add_price_data(timestamp, price, volume)
        
        # NOVO: Atualizar padrões ativos
        self.advanced_analyzer.update_active_patterns(price)
    
    def get_comprehensive_analysis(self) -> Dict:
        # ... código existente ...
        
        # NOVO: Incluir análise de padrões avançados
        advanced_analysis = self.advanced_analyzer.get_comprehensive_analysis()
        analysis['advanced_patterns'] = advanced_analysis
        
        return analysis
    """