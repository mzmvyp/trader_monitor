# your_project/services/bitcoin_streamer.py

import time
import threading
import requests
from collections import deque
from datetime import datetime
from utils.logging_config import logger
from config import app_config
from models.bitcoin_data import BitcoinData

class BitcoinDataStreamer:
    """
    Manages the streaming of Bitcoin price data from a specified API (e.g., Binance).
    It fetches data at regular intervals, validates it, and notifies registered subscribers.
    Includes error handling and duplicate data prevention.
    """
    def __init__(self, 
                 max_queue_size: int = app_config.BITCOIN_STREAM_MAX_QUEUE_SIZE,
                 fetch_interval: int = app_config.BITCOIN_STREAM_FETCH_INTERVAL_SECONDS):
        """
        Initializes the BitcoinDataStreamer.

        Args:
            max_queue_size (int): Maximum number of BitcoinData objects to keep in memory.
            fetch_interval (int): Interval (in seconds) between API data fetches.
        """
        self.is_running = False
        self.data_queue = deque(maxlen=max_queue_size) # Stores recent BitcoinData objects
        self.subscribers = [] # List of callback functions to notify with new data
        self.last_fetch_time = 0 # Timestamp of the last successful API fetch
        self.fetch_interval = fetch_interval
        self.api_errors = 0 # Counter for consecutive API errors
        self.max_consecutive_errors = app_config.BITCOIN_STREAM_MAX_CONSECUTIVE_ERRORS
        self.last_successful_price = None # Stores the last validated price for anomaly detection
        self._stream_thread = None # To hold the streaming thread

    def add_subscriber(self, callback):
        """
        Registers a callback function to be notified when new Bitcoin data is available.

        Args:
            callback (callable): A function that accepts a BitcoinData object as an argument.
        """
        if callback not in self.subscribers:
            self.subscribers.append(callback)
            logger.info(f"[STREAMER] Novo subscriber adicionado. Total: {len(self.subscribers)}")
        
    def remove_subscriber(self, callback):
        """
        Unregisters a callback function.

        Args:
            callback (callable): The callback function to remove.
        """
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            logger.info(f"[STREAMER] Subscriber removido. Total: {len(self.subscribers)}")
    
    def _can_fetch_from_api(self) -> bool:
        """
        Checks if enough time has passed since the last API fetch to perform a new one.

        Returns:
            bool: True if a new fetch can be performed, False otherwise.
        """
        time_since_last = time.time() - self.last_fetch_time
        return time_since_last >= self.fetch_interval
    
    def _mark_api_fetch(self):
        """Records the current time as the last successful API fetch time."""
        self.last_fetch_time = time.time()
    
    def _handle_api_error(self, error: str):
        """
        Increments the API error counter and logs the error.
        If consecutive errors exceed a threshold, it logs a warning about temporary API disablement.

        Args:
            error (str): The error message from the API call.
        """
        self.api_errors += 1
        logger.error(f"[STREAMER] Erro na API Binance (#{self.api_errors}): {error}")
        
        if self.api_errors >= self.max_consecutive_errors:
            logger.warning("[STREAMER] API Binance desabilitada temporariamente devido a erros consecutivos.")
    
    def _reset_api_errors(self):
        """Resets the API error counter if a successful fetch occurs."""
        if self.api_errors > 0:
            logger.info("[STREAMER] API Binance recuperada - resetando contador de erros.")
        self.api_errors = 0
        
    def _fetch_binance_data(self) -> BitcoinData | None:
        """
        Fetches Bitcoin price data from the Binance API.
        Includes checks for fetch interval and maximum consecutive errors.

        Returns:
            BitcoinData | None: A BitcoinData object if successful, None otherwise.
        """
        if not self._can_fetch_from_api():
            logger.debug(f"[STREAMER] Aguardando intervalo de fetch da API ({self.fetch_interval}s).")
            return None
            
        if self.api_errors >= self.max_consecutive_errors:
            logger.warning("[STREAMER] API Binance desabilitada. Não tentando fetch.")
            return None
        
        try:
            url = app_config.BINANCE_API_URL
            params = {'symbol': app_config.BINANCE_SYMBOL}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            data = response.json()
            
            self._mark_api_fetch()
            self._reset_api_errors()
            
            # Construct BitcoinData object from API response
            return BitcoinData(
                timestamp=datetime.now(),
                price=float(data['lastPrice']),
                volume_24h=float(data['volume']) * float(data['lastPrice']), # Calculate volume in USD
                market_cap=0, # Binance 24hr ticker doesn't provide market cap directly
                price_change_24h=float(data['priceChangePercent']),
                source='binance'
            )
            
        except requests.exceptions.RequestException as e:
            self._handle_api_error(f"Erro de requisição: {e}")
            return None
        except ValueError as e:
            self._handle_api_error(f"Erro de conversão de dados da API: {e}")
            return None
        except KeyError as e:
            self._handle_api_error(f"Chave ausente na resposta da API: {e}")
            return None
        except Exception as e:
            self._handle_api_error(f"Erro inesperado ao buscar dados da API: {e}")
            return None
    
    def _validate_price_data(self, data: BitcoinData) -> bool:
        """
        Validates the fetched Bitcoin price data for sanity checks.
        Checks for non-positive prices, extreme price changes, and prices outside expected range.

        Args:
            data (BitcoinData): The BitcoinData object to validate.

        Returns:
            bool: True if the data is considered valid, False otherwise.
        """
        if not data or data.price <= 0:
            logger.warning(f"[STREAMER] Preço rejeitado - inválido ou não positivo: {data.price:.2f}")
            return False
        
        if self.last_successful_price:
            price_change_pct = abs(data.price - self.last_successful_price) / self.last_successful_price
            if price_change_pct > app_config.PRICE_CHANGE_THRESHOLD_PCT:
                logger.warning(f"[STREAMER] Preço rejeitado - variação muito grande: ${self.last_successful_price:.2f} -> ${data.price:.2f} (>{app_config.PRICE_CHANGE_THRESHOLD_PCT*100:.0f}%)")
                return False
        
        if not (app_config.MIN_EXPECTED_PRICE <= data.price <= app_config.MAX_EXPECTED_PRICE):
            logger.warning(f"[STREAMER] Preço rejeitado - fora da faixa esperada: ${data.price:.2f} (Esperado: ${app_config.MIN_EXPECTED_PRICE:.0f}-${app_config.MAX_EXPECTED_PRICE:.0f})")
            return False
        
        return True
    
    def _is_duplicate_data(self, new_data: BitcoinData) -> bool:
        """
        Checks if the new data is a duplicate of the last data point in the queue.
        Considers data duplicated if price is almost identical and timestamp is very close.

        Args:
            new_data (BitcoinData): The new BitcoinData object to check.

        Returns:
            bool: True if it's a duplicate, False otherwise.
        """
        if not self.data_queue:
            return False
        
        last_data = self.data_queue[-1]
        time_diff = (new_data.timestamp - last_data.timestamp).total_seconds()
        same_price = abs(new_data.price - last_data.price) < 0.01 # Price difference less than 1 cent
        
        # Consider it a duplicate if price is the same and fetched within 60 seconds
        return same_price and time_diff < 60
    
    def start_streaming(self):
        """
        Starts the Bitcoin data streaming process in a separate thread.
        If already running, it logs a warning.
        """
        if self.is_running:
            logger.warning("[STREAMER] Streaming já está em execução.")
            return
        
        self.is_running = True
        logger.info("[START] Iniciando Bitcoin Data Streaming (Binance)...")
        
        def stream_worker():
            """Worker function for the streaming thread."""
            consecutive_failures = 0
            max_failures_before_pause = 10
            
            while self.is_running:
                try:
                    data = self._fetch_binance_data()
                    
                    if data and self._validate_price_data(data) and not self._is_duplicate_data(data):
                        self.data_queue.append(data)
                        self.last_successful_price = data.price
                        
                        # Notify all registered subscribers
                        for callback in self.subscribers[:]: # Iterate over a copy to allow removal during iteration
                            try:
                                callback(data)
                            except Exception as e:
                                logger.error(f"[STREAMER] Erro no subscriber '{callback.__name__}': {e}")
                                self.remove_subscriber(callback) # Remove problematic subscriber
                        
                        consecutive_failures = 0 # Reset failures on success
                        logger.info(f"[DATA] Dados coletados: ${data.price:.2f} (binance) - Change: {data.price_change_24h:.2f}%")
                        
                    elif data and self._is_duplicate_data(data):
                        logger.debug(f"[STREAMER] Dados duplicados ignorados: ${data.price:.2f}.")
                    
                    else:
                        # Data was None (API error) or invalid
                        consecutive_failures += 1
                        logger.warning(f"[STREAMER] Falha ao coletar/validar dados. Falhas consecutivas: {consecutive_failures}")
                        if consecutive_failures >= max_failures_before_pause:
                            logger.error(f"[STREAMER] Muitas falhas consecutivas ({consecutive_failures}). Pausando streaming por 5 minutos...")
                            time.sleep(300) # Pause for a longer period
                            consecutive_failures = 0 # Reset after pause
                    
                    time.sleep(self.fetch_interval) # Wait for the next fetch interval
                    
                except Exception as e:
                    consecutive_failures += 1
                    logger.critical(f"[STREAMER] Erro crítico no thread de streaming: {e}")
                    time.sleep(60) # Short pause on critical error to prevent rapid looping
            
            logger.info("[DATA] Bitcoin Data Streaming finalizado.")
        
        # Start the worker thread as a daemon so it exits with the main program
        self._stream_thread = threading.Thread(target=stream_worker, daemon=True)
        self._stream_thread.start()
        
    def stop_streaming(self):
        """
        Stops the Bitcoin data streaming process.
        """
        if not self.is_running:
            logger.warning("[STREAMER] Streaming não está em execução.")
            return
        
        self.is_running = False
        logger.info("[STOP] Parando Bitcoin Data Streaming...")
        # The daemon thread will exit when is_running becomes False
        # If the thread is joined, it will block until the thread finishes its current sleep/fetch cycle.
        # For a graceful shutdown, a small timeout for join might be considered, but for daemon, it's optional.
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=self.fetch_interval + 5) # Give it a bit more time than fetch interval
            if self._stream_thread.is_alive():
                logger.warning("[STREAMER] Thread de streaming não terminou graciosamente.")
        
    def get_recent_data(self, limit: int = 100) -> list[BitcoinData]:
        """
        Retrieves a list of the most recent BitcoinData points from the in-memory queue.

        Args:
            limit (int): The maximum number of recent data points to return.

        Returns:
            list[BitcoinData]: A list of recent BitcoinData objects.
        """
        return list(self.data_queue)[-limit:]
    
    def get_stream_statistics(self) -> dict:
        """
        Provides current statistics about the Bitcoin data streamer.

        Returns:
            dict: A dictionary containing streamer status, data points count, API errors, etc.
        """
        return {
            'is_running': self.is_running,
            'total_data_points': len(self.data_queue),
            'api_errors': self.api_errors,
            'last_fetch_time': self.last_fetch_time,
            'last_price': self.last_successful_price,
            'queue_size': len(self.data_queue),
            'subscribers_count': len(self.subscribers),
            'source': 'binance',
            'fetch_interval_minutes': self.fetch_interval / 60
        }

