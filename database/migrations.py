# your_project/database/migrations.py

import sqlite3
import os
import hashlib
from utils.logging_config import logger
from config import app_config

def migrate_database(db_path: str):
    """
    Performs database migrations for the given SQLite database path.
    Currently, it ensures the 'data_hash' column exists in 'bitcoin_stream'
    and populates it for existing records if it's newly added.
    Also ensures necessary indexes are present.

    Args:
        db_path (str): The file path of the SQLite database to migrate.
    """
    logger.info(f"[MIGRATION] Verificando e migrando banco de dados: {db_path}...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if bitcoin_stream table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bitcoin_stream';")
        if not cursor.fetchone():
            logger.info(f"[MIGRATION] Tabela 'bitcoin_stream' não encontrada em '{db_path}'. Ignorando migração de coluna.")
            return # Table doesn't exist, no need to migrate columns

        # Check for 'data_hash' column
        cursor.execute("PRAGMA table_info(bitcoin_stream)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'data_hash' not in columns:
            logger.info("[MIGRATION] Adicionando coluna 'data_hash' à tabela 'bitcoin_stream'...")
            cursor.execute('ALTER TABLE bitcoin_stream ADD COLUMN data_hash TEXT')
            
            # Populate data_hash for existing records
            logger.info("[MIGRATION] Preenchendo 'data_hash' para registros existentes...")
            cursor.execute('SELECT id, timestamp, price, source FROM bitcoin_stream')
            rows = cursor.fetchall()
            
            for row in rows:
                # Create a hash based on key data points to identify unique records
                hash_string = f"{row[1]}_{row[2]}_{row[3]}"
                data_hash = hashlib.md5(hash_string.encode()).hexdigest()[:16]
                cursor.execute('UPDATE bitcoin_stream SET data_hash = ? WHERE id = ?', 
                             (data_hash, row[0]))
            
            logger.info(f"[MIGRATION] Atualizados {len(rows)} registros com hash de dados.")
        else:
            logger.info("[MIGRATION] Coluna 'data_hash' já existe.")
        
        # Ensure indexes are present
        cursor.execute("PRAGMA index_list(bitcoin_stream)")
        existing_indexes = [idx[1] for idx in cursor.fetchall()]
        
        indexes_to_create = [
            ('idx_timestamp', 'CREATE INDEX IF NOT EXISTS idx_timestamp ON bitcoin_stream(timestamp)'),
            ('idx_data_hash', 'CREATE INDEX IF NOT EXISTS idx_data_hash ON bitcoin_stream(data_hash)'),
            ('idx_source', 'CREATE INDEX IF NOT EXISTS idx_source ON bitcoin_stream(source)')
        ]
        
        for idx_name, idx_sql in indexes_to_create:
            if idx_name not in existing_indexes:
                logger.info(f"[MIGRATION] Criando índice '{idx_name}'...")
                cursor.execute(idx_sql)
            else:
                logger.debug(f"[MIGRATION] Índice '{idx_name}' já existe.")
        
        conn.commit()
        logger.info("[MIGRATION] Migração concluída com sucesso.")
        
    except Exception as e:
        logger.error(f"[MIGRATION] Erro na migração para '{db_path}': {e}")
        conn.rollback()
        raise # Re-raise the exception after logging and rolling back
    finally:
        conn.close()

