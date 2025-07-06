# your_project/database/setup.py

import sqlite3
import os
from utils.logging_config import logger
from config import app_config

def setup_bitcoin_stream_db(db_path: str):
    """
    Sets up the database schema for Bitcoin streaming data.
    Ensures the 'bitcoin_stream' and 'bitcoin_analytics' tables exist.
    Also adds a 'data_hash' column and creates necessary indexes if they don't exist.

    Args:
        db_path (str): The file path for the SQLite database.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create bitcoin_stream table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bitcoin_stream (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                price REAL,
                volume_24h REAL,
                market_cap REAL,
                price_change_24h REAL,
                source TEXT,
                processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create bitcoin_analytics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bitcoin_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                window_start DATETIME,
                window_end DATETIME,
                avg_price REAL,
                min_price REAL,
                max_price REAL,
                price_volatility REAL,
                total_volume REAL,
                data_points INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Add data_hash column if it doesn't exist (for migration purposes)
        cursor.execute("PRAGMA table_info(bitcoin_stream)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'data_hash' not in columns:
            logger.info("[DB_SETUP] Adicionando coluna 'data_hash' à tabela 'bitcoin_stream'.")
            cursor.execute('ALTER TABLE bitcoin_stream ADD COLUMN data_hash TEXT')
        
        # Create indexes for efficient querying
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON bitcoin_stream(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_hash ON bitcoin_stream(data_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_source ON bitcoin_stream(source)')
        
        conn.commit()
        logger.info(f"[DB_SETUP] Banco de dados Bitcoin Stream em '{db_path}' inicializado/verificado.")
        
    except Exception as e:
        logger.error(f"[DB_SETUP] Erro ao configurar banco de dados Bitcoin Stream: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def setup_trading_analyzer_db(db_path: str):
    """
    Sets up the database schema for the trading analyzer.
    Ensures the 'price_history', 'trading_signals', and 'analyzer_state' tables exist.

    Args:
        db_path (str): The file path for the SQLite database.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create price_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                price REAL,
                volume REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create trading_signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trading_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                pattern_type TEXT,
                entry_price REAL,
                target_price REAL,
                stop_loss REAL,
                confidence INTEGER,
                status TEXT,
                created_at DATETIME,
                profit_loss REAL DEFAULT 0,
                activated BOOLEAN DEFAULT 0
            )
        ''')
        
        # Create analyzer_state table (for persistence of analysis count and last analysis time)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analyzer_state (
                id INTEGER PRIMARY KEY,
                analysis_count INTEGER,
                last_analysis DATETIME,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        logger.info(f"[DB_SETUP] Banco de dados Trading Analyzer em '{db_path}' inicializado/verificado.")
        
    except Exception as e:
        logger.error(f"[DB_SETUP] Erro ao configurar banco de dados Trading Analyzer: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def initialize_databases():
    """
    Initializes all necessary databases for the application.
    """
    logger.info("[DB_SETUP] Inicializando todos os bancos de dados...")
    setup_bitcoin_stream_db(app_config.BITCOIN_STREAM_DB)
    setup_trading_analyzer_db(app_config.TRADING_ANALYZER_DB)
    logger.info("[DB_SETUP] Inicialização de bancos de dados concluída.")

