# your_project/services/analytics_engine.py

import sqlite3
from datetime import datetime, timedelta
from utils.logging_config import logger
from config import app_config

class BitcoinAnalyticsEngine:
    """
    Provides various analytical metrics and aggregated data for Bitcoin stream data
    stored in the database. It focuses on real-time and historical insights.
    """
    def __init__(self, db_path: str = app_config.BITCOIN_STREAM_DB):
        """
        Initializes the BitcoinAnalyticsEngine.

        Args:
            db_path (str): The file path for the SQLite database containing Bitcoin stream data.
        """
        self.db_path = db_path
        
    def get_real_time_metrics(self, time_window_minutes: int = 30) -> dict:
        """
        Retrieves real-time aggregated metrics for Bitcoin price data
        within a specified time window (e.g., last 30 minutes).

        Args:
            time_window_minutes (int): The duration in minutes for the real-time window.

        Returns:
            dict: A dictionary containing aggregated metrics.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate the cutoff time for the specified window
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        try:
            # First check if we have any data at all
            cursor.execute('SELECT COUNT(*) FROM bitcoin_stream')
            total_count = cursor.fetchone()[0]
            
            if total_count == 0:
                logger.info(f"[ANALYTICS] Nenhum dado no banco de dados.")
                return self._get_empty_metrics()
            
            # Check for data in the time window
            cursor.execute('''
                SELECT 
                    COUNT(*) as count,
                    AVG(price) as avg_price,
                    MIN(price) as min_price,
                    MAX(price) as max_price,
                    AVG(price_change_24h) as avg_change,
                    MAX(timestamp) as last_update
                FROM bitcoin_stream 
                WHERE timestamp > ?
            ''', (cutoff_time.isoformat(),))
            
            result = cursor.fetchone()
            
            if result and result[0] > 0:
                avg_price = round(result[1], 2) if result[1] is not None else 0
                min_price = round(result[2], 2) if result[2] is not None else 0
                max_price = round(result[3], 2) if result[3] is not None else 0
                avg_change = round(result[4], 2) if result[4] is not None else 0
                last_update_str = result[5] if result[5] else datetime.now().isoformat()

                return {
                    'data_points': result[0],
                    'avg_price': avg_price,
                    'min_price': min_price,
                    'max_price': max_price,
                    'avg_change_24h': avg_change,
                    'price_range': round(max_price - min_price, 2),
                    'last_update': last_update_str,
                    'total_records': total_count
                }
            else:
                # No data in time window, get latest data
                logger.info(f"[ANALYTICS] Sem dados nos últimos {time_window_minutes} minutos para métricas em tempo real.")
                
                cursor.execute('''
                    SELECT price, price_change_24h, timestamp
                    FROM bitcoin_stream 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                ''')
                
                latest = cursor.fetchone()
                if latest:
                    return {
                        'data_points': 0,
                        'avg_price': round(latest[0], 2),
                        'min_price': round(latest[0], 2),
                        'max_price': round(latest[0], 2),
                        'avg_change_24h': round(latest[1], 2) if latest[1] else 0,
                        'price_range': 0,
                        'last_update': latest[2],
                        'total_records': total_count
                    }
                else:
                    return self._get_empty_metrics()
                
        except Exception as e:
            logger.error(f"[ANALYTICS] Erro ao obter métricas em tempo real: {e}")
            return self._get_empty_metrics()
        finally:
            if conn:
                conn.close()

    def _get_empty_metrics(self) -> dict:
        """Returns empty metrics structure"""
        return {
            'data_points': 0,
            'avg_price': 0,
            'min_price': 0,
            'max_price': 0,
            'avg_change_24h': 0,
            'price_range': 0,
            'last_update': datetime.now().isoformat(),
            'total_records': 0
        }

    def get_historical_data(self, limit: int = 100) -> list[dict]:
        """
        Retrieves a limited number of historical Bitcoin stream data points.

        Args:
            limit (int): The maximum number of historical records to retrieve.

        Returns:
            list[dict]: A list of dictionaries, each representing a Bitcoin data point.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT timestamp, price, volume_24h, market_cap, price_change_24h, source
                FROM bitcoin_stream
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()

            # Convert rows to list of dictionaries for easier consumption
            historical_data = []
            for row in reversed(rows):  # Reverse to get chronological order
                historical_data.append({
                    'timestamp': row[0],
                    'price': row[1],
                    'volume_24h': row[2],
                    'market_cap': row[3],
                    'price_change_24h': row[4],
                    'source': row[5]
                })
            return historical_data
        except Exception as e:
            logger.error(f"[ANALYTICS] Erro ao obter dados históricos: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_analytics_summary(self) -> list[dict]:
        """
        Retrieves a summary of the calculated analytics from the 'bitcoin_analytics' table.

        Returns:
            list[dict]: A list of dictionaries, each representing an analytics summary record.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT 
                    window_start, window_end, avg_price, min_price, max_price, 
                    price_volatility, total_volume, data_points, created_at
                FROM bitcoin_analytics
                ORDER BY window_end DESC
                LIMIT 10
            ''')
            
            rows = cursor.fetchall()

            analytics_summary = []
            for row in rows:
                analytics_summary.append({
                    'window_start': row[0],
                    'window_end': row[1],
                    'avg_price': round(row[2], 2),
                    'min_price': round(row[3], 2),
                    'max_price': round(row[4], 2),
                    'price_volatility': round(row[5], 2),
                    'total_volume': round(row[6], 2),
                    'data_points': row[7],
                    'created_at': row[8]
                })
            return analytics_summary
        except Exception as e:
            logger.error(f"[ANALYTICS] Erro ao obter resumo de analytics: {e}")
            return []
        finally:
            if conn:
                conn.close()