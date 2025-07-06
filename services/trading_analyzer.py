# your_project/services/trading_analyzer.py

import sqlite3
import os
from collections import deque
from datetime import datetime, timedelta
from utils.logging_config import logger
from config import app_config
from database.setup import setup_trading_analyzer_db # Import setup for initial table creation

class SimpleTradingAnalyzer:
    """
    Analyzes Bitcoin price history to identify potential trading signals
    and provides insights into market indicators and pattern performance.
    It persists its state (price history, signals, analysis count) to a SQLite database.
    """
    def __init__(self, db_path: str = app_config.TRADING_ANALYZER_DB):
        """
        Initializes the SimpleTradingAnalyzer.

        Args:
            db_path (str): The file path for the SQLite database to store analyzer data.
        """
        self.db_path = db_path
        # deque for efficient appending/popping from both ends, with a max length
        self.price_history = deque(maxlen=200) 
        self.analysis_count = 0 # Counter for how many price data points have been analyzed
        self.signals = [] # List to store generated trading signals
        self.last_analysis = None # Timestamp of the last analysis performed
        self.init_database()
        self.load_previous_data()
        
    def init_database(self):
        """
        Initializes the SQLite database for the trading analyzer.
        This ensures that the necessary tables (`price_history`, `trading_signals`, `analyzer_state`)
        are created if they don't already exist.
        """
        setup_trading_analyzer_db(self.db_path)
        
    def load_previous_data(self):
        """
        Loads previous price history, trading signals, and analyzer state from the database
        to resume analysis from where it left off.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Load recent price history (up to maxlen)
            cursor.execute('''
                SELECT timestamp, price, volume 
                FROM price_history 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (self.price_history.maxlen,))
            
            # Fetch and append in reverse order to maintain chronological order in deque
            price_data = cursor.fetchall()
            for row in reversed(price_data):
                self.price_history.append({
                    'timestamp': datetime.fromisoformat(row[0]), # Convert ISO string back to datetime
                    'price': row[1],
                    'volume': row[2]
                })
            
            # Load active and recent (last 24 hours) trading signals
            cursor.execute('''
                SELECT id, timestamp, pattern_type, entry_price, target_price, 
                       stop_loss, confidence, status, created_at, profit_loss, activated
                FROM trading_signals 
                WHERE status = 'ACTIVE' OR created_at > datetime('now', '-24 hours')
                ORDER BY created_at DESC
            ''')
            
            signal_data = cursor.fetchall()
            for row in signal_data:
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
                    'profit_loss': row[9] or 0, # Handle NULL profit_loss
                    'activated': bool(row[10])
                }
                self.signals.append(signal)
            
            # Load analyzer state (analysis count and last analysis timestamp)
            cursor.execute('SELECT analysis_count, last_analysis FROM analyzer_state WHERE id = 1')
            state = cursor.fetchone()
            if state:
                self.analysis_count = state[0] or 0
                if state[1]:
                    self.last_analysis = datetime.fromisoformat(state[1])
            
            conn.close()
            
            logger.info(f"[ANALYZER] Carregados: {len(self.price_history)} preços, {len(self.signals)} sinais, análises: {self.analysis_count}.")
            
        except Exception as e:
            logger.error(f"[ANALYZER] Erro ao carregar dados anteriores: {e}")
    
    def save_price_data(self, timestamp: datetime, price: float, volume: float):
        """
        Saves a single price data point to the 'price_history' table.
        Also prunes older records to keep the table size manageable.

        Args:
            timestamp (datetime): The timestamp of the price data.
            price (float): The Bitcoin price.
            volume (float): The trading volume at that time.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO price_history (timestamp, price, volume)
                VALUES (?, ?, ?)
            ''', (timestamp.isoformat(), price, volume))
            
            # Keep only the most recent 1000 records to prevent database bloat
            cursor.execute('''
                DELETE FROM price_history 
                WHERE id NOT IN (
                    SELECT id FROM price_history 
                    ORDER BY timestamp DESC 
                    LIMIT 1000
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.debug(f"[ANALYZER] Preço salvo: {price:.2f} em {timestamp.isoformat()}")
            
        except Exception as e:
            logger.error(f"[ANALYZER] Erro ao salvar preço: {e}")
    
    def save_signal(self, signal: dict):
        """
        Saves a newly generated trading signal to the 'trading_signals' table.

        Args:
            signal (dict): A dictionary representing the trading signal.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trading_signals 
                (timestamp, pattern_type, entry_price, target_price, stop_loss, 
                 confidence, status, created_at, profit_loss, activated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal['timestamp'], signal['pattern_type'], signal['entry_price'],
                signal['target_price'], signal['stop_loss'], signal['confidence'],
                signal['status'], signal['created_at'], signal['profit_loss'],
                signal['activated']
            ))
            
            conn.commit()
            conn.close()
            logger.debug(f"[ANALYZER] Sinal salvo: {signal['pattern_type']} - {signal['status']}")
            
        except Exception as e:
            logger.error(f"[ANALYZER] Erro ao salvar sinal: {e}")
    
    def save_analyzer_state(self):
        """
        Persists the current state of the analyzer (analysis count, last analysis timestamp)
        to the 'analyzer_state' table. This ensures continuity across application restarts.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Use INSERT OR REPLACE to either insert a new record or update the existing one (id=1)
            cursor.execute('''
                INSERT OR REPLACE INTO analyzer_state 
                (id, analysis_count, last_analysis, updated_at)
                VALUES (1, ?, ?, datetime('now'))
            ''', (
                self.analysis_count,
                self.last_analysis.isoformat() if self.last_analysis else None
            ))
            
            conn.commit()
            conn.close()
            logger.debug(f"[ANALYZER] Estado do analyzer salvo. Análises: {self.analysis_count}")
            
        except Exception as e:
            logger.error(f"[ANALYZER] Erro ao salvar estado do analyzer: {e}")
        
    def add_price_data(self, timestamp: datetime, price: float, volume: float = 0):
        """
        Adds a new price data point to the in-memory price history.
        Triggers periodic saving of price data and analyzer state to the database,
        and generates sample signals based on analysis count.

        Args:
            timestamp (datetime): The timestamp of the price data.
            price (float): The Bitcoin price.
            volume (float): The trading volume (defaults to 0 if not provided).
        """
        self.price_history.append({
            'timestamp': timestamp,
            'price': price,
            'volume': volume
        })
        self.analysis_count += 1
        self.last_analysis = datetime.now()
        
        # Save price data and analyzer state periodically to reduce database writes
        if self.analysis_count % 10 == 0:
            self.save_price_data(timestamp, price, volume)
            self.save_analyzer_state()
        
        # Create a sample signal periodically (e.g., every 50 data points)
        if self.analysis_count % 50 == 0 and len(self.price_history) > 20:
            self._create_sample_signal(price)
    
    def _create_sample_signal(self, current_price: float):
        """
        Generates a sample trading signal based on the current price.
        This is a placeholder for actual trading logic.

        Args:
            current_price (float): The current Bitcoin price.
        """
        # Simulate different pattern types
        pattern_type = 'INDICATORS_BUY' if len(self.signals) % 2 == 0 else 'DOUBLE_BOTTOM'
        
        signal = {
            'id': len(self.signals) + 1, # Simple ID generation
            'timestamp': datetime.now().isoformat(),
            'pattern_type': pattern_type,
            'entry_price': current_price * 1.001, # Small markup for entry
            'target_price': current_price * 1.025, # 2.5% target
            'stop_loss': current_price * 0.985, # 1.5% stop loss
            'confidence': 75, # Fixed confidence for sample
            'status': 'ACTIVE', # Initially active
            'created_at': datetime.now().isoformat(),
            'profit_loss': 0,
            'activated': False # Could be true if actual entry logic was implemented
        }
        self.signals.append(signal)
        self.save_signal(signal) # Persist the new signal
        logger.info(f"[TRADE] Novo sinal criado: {signal['pattern_type']} @ ${signal['entry_price']:.2f}")
    
    def get_current_analysis(self) -> dict:
        """
        Provides a comprehensive analysis of the current market state,
        including current price, simulated indicators, active signals,
        recent signals, and pattern performance statistics.

        Returns:
            dict: A dictionary containing various analysis metrics.
        """
        current_price = self.price_history[-1]['price'] if self.price_history else 0
        
        indicators = {}
        # Simulate indicator values if enough price history is available
        if len(self.price_history) >= 20:
            recent_prices = [p['price'] for p in list(self.price_history)[-20:]]
            indicators = {
                'RSI': round(45 + (len(self.price_history) % 40), 2), # Relative Strength Index
                'SMA_12': round(sum(recent_prices[-12:]) / 12 if len(recent_prices) >= 12 else current_price, 2), # Simple Moving Average 12-period
                'SMA_30': round(current_price * 0.998, 2), # Simple Moving Average 30-period (simulated)
                'MACD': round(5.5 + (self.analysis_count % 10) / 5, 2), # Moving Average Convergence Divergence
                'STOCH_K': round(35 + (self.analysis_count % 50), 2) # Stochastic Oscillator %K
            }
        
        # Simulate pattern statistics based on existing signals
        # In a real system, these would be calculated from actual trade outcomes
        pattern_stats = [
            {
                'pattern_type': 'INDICATORS_BUY',
                'total_signals': max(1, len([s for s in self.signals if 'BUY' in s['pattern_type']])),
                'successful_signals': max(1, len([s for s in self.signals if 'BUY' in s['pattern_type']]) // 2),
                'failed_signals': max(0, len([s for s in self.signals if 'BUY' in s['pattern_type']]) // 3),
                'success_rate': round(65.5 + (len(self.signals) % 5), 2), # Dynamic success rate
                'avg_profit': round(2.3 + (len(self.signals) % 3) / 10, 2),
                'avg_loss': round(-1.2 - (len(self.signals) % 2) / 10, 2)
            },
            {
                'pattern_type': 'DOUBLE_BOTTOM',
                'total_signals': max(1, len([s for s in self.signals if 'DOUBLE' in s['pattern_type']])),
                'successful_signals': max(1, len([s for s in self.signals if 'DOUBLE' in s['pattern_type']]) // 2),
                'failed_signals': max(0, len([s for s in self.signals if 'DOUBLE' in s['pattern_type']]) // 4),
                'success_rate': round(72.1 + (len(self.signals) % 7), 2), # Dynamic success rate
                'avg_profit': round(3.1 + (len(self.signals) % 4) / 10, 2),
                'avg_loss': round(-1.5 - (len(self.signals) % 3) / 10, 2)
            }
        ]
        
        return {
            'current_price': current_price,
            'indicators': indicators,
            'active_signals': len([s for s in self.signals if s['status'] == 'ACTIVE']),
            'recent_signals': self.signals[-20:] if self.signals else [], # Return up to 20 most recent signals
            'pattern_stats': pattern_stats,
            'system_info': {
                'analysis_count': self.analysis_count,
                'data_points': len(self.price_history),
                'last_analysis': self.last_analysis.isoformat() if self.last_analysis else None
            }
        }
    
    def get_system_health(self) -> dict:
        """
        Provides a concise summary of the analyzer's operational health.

        Returns:
            dict: Health metrics including total analysis count, active signals, data points, and last analysis time.
        """
        return {
            'total_analysis': self.analysis_count,
            'active_signals': len([s for s in self.signals if s['status'] == 'ACTIVE']),
            'data_points': len(self.price_history),
            'last_analysis': self.last_analysis.isoformat() if self.last_analysis else None
        }

    def reset_signals_and_state(self):
        """
        Clears all trading signals and resets the analyzer's state,
        including clearing them from the persistent database.
        """
        try:
            self.signals.clear() # Clear in-memory signals
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM trading_signals') # Delete from database
            cursor.execute('DELETE FROM analyzer_state') # Delete analyzer state from database
            conn.commit()
            conn.close()
            
            self.analysis_count = 0
            self.last_analysis = None
            
            logger.info("[ANALYZER] Sistema de sinais e estado do analyzer resetado completamente.")
            
        except Exception as e:
            logger.error(f"[ANALYZER] Erro ao resetar sinais e estado do analyzer: {e}")
            raise # Re-raise to indicate failure

