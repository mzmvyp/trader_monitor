# your_project/database/processors.py

import sqlite3
import os
import threading
import hashlib
from datetime import datetime, timedelta
from utils.logging_config import logger
from config import app_config
from models.bitcoin_data import BitcoinData
from database.migrations import migrate_database # Import migration function
from database.setup import setup_bitcoin_stream_db # Import setup for initial table creation

class BitcoinStreamProcessor:
    """
    Processes incoming Bitcoin data stream, stores it in a SQLite database,
    and performs real-time analytics updates.
    It uses a batching mechanism for efficient database writes and
    ensures data integrity by checking for duplicates using hashes.
    """
    def __init__(self, db_path: str = app_config.BITCOIN_STREAM_DB):
        """
        Initializes the BitcoinStreamProcessor.

        Args:
            db_path (str): The path to the SQLite database file for Bitcoin stream data.
        """
        self.db_path = db_path
        self.batch_size = app_config.BITCOIN_PROCESSOR_BATCH_SIZE
        self.batch_buffer = [] # Stores (BitcoinData, data_hash) tuples
        self.last_processed_hash = None # To prevent immediate duplicates
        self.processing_lock = threading.Lock() # Ensures thread-safe batch processing
        self.init_database()
        
    def init_database(self):
        """
        Initializes the database by ensuring tables and columns exist,
        and runs any necessary migrations.
        """
        # Ensure the database directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Check if database file exists before setup to determine if migration is needed
        db_exists = os.path.exists(self.db_path)
        
        # Setup the database schema (creates tables if they don't exist)
        setup_bitcoin_stream_db(self.db_path)

        # If the database existed before this run, apply migrations
        if db_exists:
            migrate_database(self.db_path)
        else:
            logger.info(f"[PROCESSOR] Novo banco de dados '{self.db_path}' criado, migrações aplicadas na inicialização.")
        
    def _generate_data_hash(self, data: BitcoinData) -> str:
        """
        Generates a unique hash for a BitcoinData object based on its timestamp, price, and source.
        This helps in detecting and preventing duplicate entries.

        Args:
            data (BitcoinData): The BitcoinData object to hash.

        Returns:
            str: A 16-character MD5 hash string.
        """
        hash_string = f"{data.timestamp.isoformat()}_{data.price}_{data.source}"
        return hashlib.md5(hash_string.encode()).hexdigest()[:16]
        
    def process_stream_data(self, data: BitcoinData):
        """
        Adds incoming Bitcoin data to a buffer. When the buffer reaches `batch_size`,
        it triggers a batch processing operation to write data to the database.
        Includes a check for immediate duplicates to avoid redundant processing.

        Args:
            data (BitcoinData): The BitcoinData object to process.
        """
        with self.processing_lock:
            data_hash = self._generate_data_hash(data)
            
            # Prevent processing immediate duplicates (e.g., if API sends same data twice quickly)
            if data_hash == self.last_processed_hash:
                logger.debug(f"[PROCESSOR] Dados duplicados ignorados (hash: {data_hash}).")
                return
            
            self.batch_buffer.append((data, data_hash))
            self.last_processed_hash = data_hash # Update last processed hash

            # If batch buffer is full, process it
            if len(self.batch_buffer) >= self.batch_size:
                self._process_batch()
                
    def _process_batch(self):
        """
        Writes the buffered Bitcoin data to the 'bitcoin_stream' table in the database
        and updates the 'bitcoin_analytics' table.
        This method is called when the batch buffer is full or during shutdown.
        """
        if not self.batch_buffer:
            return # Nothing to process
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        inserted_count = 0
        
        try:
            # Iterate through the buffered data and insert into bitcoin_stream table
            for data, data_hash in self.batch_buffer:
                try:
                    cursor.execute('''
                        INSERT INTO bitcoin_stream 
                        (timestamp, price, volume_24h, market_cap, price_change_24h, source, data_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        data.timestamp.isoformat(), # Store datetime as ISO string
                        data.price, 
                        data.volume_24h,
                        data.market_cap, 
                        data.price_change_24h, 
                        data.source, 
                        data_hash
                    ))
                    inserted_count += 1
                    
                except sqlite3.IntegrityError as e:
                    # Handle cases where a unique constraint might be violated (e.g., if data_hash was unique)
                    # Note: data_hash is not unique in current schema, but this is good practice.
                    if "UNIQUE constraint failed" in str(e):
                        logger.debug(f"[PROCESSOR] Dados duplicados no banco (hash: {data_hash}).")
                    else:
                        logger.error(f"[PROCESSOR] Erro de integridade ao inserir dados: {e}")
                except Exception as e:
                    logger.error(f"[PROCESSOR] Erro ao inserir registro individual: {e}")
                        
            # Only update analytics if new data was successfully inserted
            if inserted_count > 0:
                self._update_analytics(cursor)
            
            conn.commit() # Commit all changes in the batch
            
            if inserted_count > 0:
                logger.info(f"[PROCESSOR] Lote processado: {inserted_count}/{len(self.batch_buffer)} registros inseridos.")
            
        except Exception as e:
            logger.error(f"[PROCESSOR] Erro ao processar lote de dados: {e}")
            conn.rollback() # Rollback changes if any error occurs during batch processing
        finally:
            conn.close()
            self.batch_buffer.clear() # Clear the buffer after processing (or rollback)
    
    def _update_analytics(self, cursor: sqlite3.Cursor):
        """
        Calculates and updates real-time analytics in the 'bitcoin_analytics' table
        based on recent Bitcoin stream data (last 1 hour).

        Args:
            cursor (sqlite3.Cursor): The SQLite database cursor to use for updates.
        """
        try:
            one_hour_ago = datetime.now() - timedelta(hours=1)
            
            # Fetch recent data for analytics calculation
            cursor.execute('''
                SELECT price, volume_24h, timestamp
                FROM bitcoin_stream 
                WHERE timestamp > ?
                ORDER BY timestamp
            ''', (one_hour_ago.isoformat(),)) # Use ISO format for comparison
            
            recent_data = cursor.fetchall()
            
            if len(recent_data) > 0:
                # Extract prices and volumes from the fetched data
                prices = [row[0] for row in recent_data]
                volumes = [row[1] for row in recent_data if row[1] is not None and row[1] > 0] # Filter valid volumes
                
                # Determine the time window for the analytics
                window_start = min(row[2] for row in recent_data)
                window_end = max(row[2] for row in recent_data)
                
                # Calculate key metrics
                avg_price = sum(prices) / len(prices)
                min_price = min(prices)
                max_price = max(prices)
                # Calculate price volatility as percentage change
                price_volatility = ((max_price - min_price) / avg_price * 100) if avg_price > 0 else 0
                total_volume = sum(volumes) if volumes else 0 # Sum of valid volumes
                
                # Insert or update analytics record
                cursor.execute('''
                    INSERT INTO bitcoin_analytics 
                    (window_start, window_end, avg_price, min_price, max_price, 
                     price_volatility, total_volume, data_points)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    window_start, window_end, avg_price, min_price, max_price,
                    price_volatility, total_volume, len(recent_data)
                ))
                logger.debug(f"[PROCESSOR] Analytics atualizados para janela: {window_start} a {window_end}.")
                
        except Exception as e:
            logger.error(f"[PROCESSOR] Erro ao atualizar analytics: {e}")

    def force_process_batch(self):
        """
        Forces the processing of any remaining data in the batch buffer,
        useful during application shutdown to ensure all data is persisted.
        """
        with self.processing_lock:
            if self.batch_buffer:
                logger.info(f"[PROCESSOR] Forçando processamento do lote restante ({len(self.batch_buffer)} itens).")
                self._process_batch()
            else:
                logger.debug("[PROCESSOR] Buffer de processamento de Bitcoin vazio, nada para forçar.")

