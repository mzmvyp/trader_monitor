# your_project/services/generic_asset_streamer.py - ARQUIVO NOVO

import time
import threading
import requests
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Callable
from utils.logging_config import logger
from config import app_config
from models.bitcoin_data import BitcoinData  # Reutilizar modelo existente

class GenericAssetStreamer:
    """
    Generic asset data streamer que pode ser usado para qualquer cryptocurrency.
    Baseado no BitcoinDataStreamer existente, mas genérico e reutilizável.
    """
    
    def __init__(self, 
                 asset_symbol: str,
                 max_queue_size: int = None,
                 fetch_interval: int = None):
        """
        Inicializa o GenericAssetStreamer.

        Args:
            asset_symbol (str): Símbolo do asset (BTC, ETH, SOL)
            max_queue_size (int): Tamanho máximo da queue em memória
            fetch_interval (int): Intervalo entre fetches em segundos
        """
        self.asset_symbol = asset_symbol.upper()
        self.asset_config = app_config.get_asset_config(self.asset_symbol)
        
        # Configurações específicas do asset
        self.binance_symbol = self.asset_config['symbol']
        self.min_price = self.asset_config['min_price']
        self.max_price = self.asset_config['max_price']
        self.precision = self.asset_config['precision']
        
        # Configurações de streaming
        self.max_queue_size = max_queue_size or app_config.MULTI_ASSET_MAX_QUEUE_SIZE
        self.fetch_interval = fetch_interval or app_config.ASSET_INTERVALS.get(self.asset_symbol, 300)
        
        # Estado do streamer
        self.is_running = False
        self.data_queue = deque(maxlen=self.max_queue_size)
        self.subscribers = []
        self.last_fetch_time = 0
        self.api_errors = 0
        self.max_consecutive_errors = app_config.BITCOIN_STREAM_MAX_CONSECUTIVE_ERRORS
        self.last_successful_price = None
        self._stream_thread = None
        
        logger.info(f"[{self.asset_symbol}] Generic streamer inicializado: {self.binance_symbol}")

    def add_subscriber(self, callback: Callable):
        """Registra callback para notificações de novos dados"""
        if callback not in self.subscribers:
            self.subscribers.append(callback)
            logger.info(f"[{self.asset_symbol}] Subscriber adicionado. Total: {len(self.subscribers)}")
        
    def remove_subscriber(self, callback: Callable):
        """Remove callback da lista de subscribers"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            logger.info(f"[{self.asset_symbol}] Subscriber removido. Total: {len(self.subscribers)}")
    
    def _can_fetch_from_api(self) -> bool:
        """Verifica se pode fazer fetch da API baseado no intervalo"""
        time_since_last = time.time() - self.last_fetch_time
        return time_since_last >= self.fetch_interval
    
    def _mark_api_fetch(self):
        """Marca timestamp do último fetch bem-sucedido"""
        self.last_fetch_time = time.time()
    
    def _handle_api_error(self, error: str):
        """Trata erros da API e incrementa contador"""
        self.api_errors += 1
        logger.error(f"[{self.asset_symbol}] Erro na API Binance (#{self.api_errors}): {error}")
        
        if self.api_errors >= self.max_consecutive_errors:
            logger.warning(f"[{self.asset_symbol}] API desabilitada temporariamente devido a erros consecutivos.")
    
    def _reset_api_errors(self):
        """Reseta contador de erros da API"""
        if self.api_errors > 0:
            logger.info(f"[{self.asset_symbol}] API recuperada - resetando contador de erros.")
        self.api_errors = 0
        
    def _fetch_binance_data(self) -> Optional[BitcoinData]:
        """
        Faz fetch dos dados do asset da API Binance.
        Retorna BitcoinData (reutilizando modelo existente) ou None se erro.
        """
        if not self._can_fetch_from_api():
            logger.debug(f"[{self.asset_symbol}] Aguardando intervalo de fetch ({self.fetch_interval}s).")
            return None
            
        if self.api_errors >= self.max_consecutive_errors:
            logger.warning(f"[{self.asset_symbol}] API desabilitada. Não tentando fetch.")
            return None
        
        try:
            url = app_config.BINANCE_API_URL
            params = {'symbol': self.binance_symbol}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            self._mark_api_fetch()
            self._reset_api_errors()
            
            # Criar BitcoinData (nome genérico mas funciona para qualquer asset)
            asset_data = BitcoinData(
                timestamp=datetime.now(),
                price=float(data['lastPrice']),
                volume_24h=float(data['volume']) * float(data['lastPrice']),
                market_cap=0,  # Binance API não fornece market cap diretamente
                price_change_24h=float(data['priceChangePercent']),
                source=f'binance_{self.asset_symbol.lower()}'
            )
            
            return asset_data
            
        except requests.exceptions.RequestException as e:
            self._handle_api_error(f"Erro de requisição: {e}")
            return None
        except ValueError as e:
            self._handle_api_error(f"Erro de conversão de dados: {e}")
            return None
        except KeyError as e:
            self._handle_api_error(f"Chave ausente na resposta: {e}")
            return None
        except Exception as e:
            self._handle_api_error(f"Erro inesperado: {e}")
            return None
    
    def _validate_price_data(self, data: BitcoinData) -> bool:
        """Valida dados de preço para sanity checks"""
        if not data or data.price <= 0:
            logger.warning(f"[{self.asset_symbol}] Preço rejeitado - inválido: {data.price:.2f}")
            return False
        
        # Verificar range específico do asset
        if not (self.min_price <= data.price <= self.max_price):
            logger.warning(f"[{self.asset_symbol}] Preço fora da faixa esperada: ${data.price:.2f} (Esperado: ${self.min_price:.0f}-${self.max_price:.0f})")
            return False
        
        # Verificar variação extrema se temos preço anterior
        if self.last_successful_price:
            price_change_pct = abs(data.price - self.last_successful_price) / self.last_successful_price
            if price_change_pct > app_config.PRICE_CHANGE_THRESHOLD_PCT:
                logger.warning(f"[{self.asset_symbol}] Variação muito grande: ${self.last_successful_price:.2f} -> ${data.price:.2f} (>{app_config.PRICE_CHANGE_THRESHOLD_PCT*100:.0f}%)")
                return False
        
        return True
    
    def _is_duplicate_data(self, new_data: BitcoinData) -> bool:
        """Verifica se os dados são duplicados"""
        if not self.data_queue:
            return False
        
        last_data = self.data_queue[-1]
        time_diff = (new_data.timestamp - last_data.timestamp).total_seconds()
        same_price = abs(new_data.price - last_data.price) < (0.01 * (10 ** (2 - self.precision)))
        
        return same_price and time_diff < 60
    
    def start_streaming(self):
        """Inicia o processo de streaming em thread separada"""
        if self.is_running:
            logger.warning(f"[{self.asset_symbol}] Streaming já está em execução.")
            return
        
        self.is_running = True
        logger.info(f"[{self.asset_symbol}] Iniciando Asset Data Streaming...")
        
        def stream_worker():
            """Worker function para thread de streaming"""
            consecutive_failures = 0
            max_failures_before_pause = 10
            
            while self.is_running:
                try:
                    data = self._fetch_binance_data()
                    
                    if data and self._validate_price_data(data) and not self._is_duplicate_data(data):
                        self.data_queue.append(data)
                        self.last_successful_price = data.price
                        
                        # Notificar subscribers
                        for callback in self.subscribers[:]:
                            try:
                                callback(data)
                            except Exception as e:
                                logger.error(f"[{self.asset_symbol}] Erro no subscriber '{callback.__name__}': {e}")
                                self.remove_subscriber(callback)
                        
                        consecutive_failures = 0
                        logger.info(f"[{self.asset_symbol}] Dados coletados: ${data.price:.{self.precision}f} - Change: {data.price_change_24h:.2f}%")
                        
                    elif data and self._is_duplicate_data(data):
                        logger.debug(f"[{self.asset_symbol}] Dados duplicados ignorados: ${data.price:.{self.precision}f}")
                    
                    else:
                        consecutive_failures += 1
                        logger.warning(f"[{self.asset_symbol}] Falha ao coletar/validar dados. Falhas consecutivas: {consecutive_failures}")
                        if consecutive_failures >= max_failures_before_pause:
                            logger.error(f"[{self.asset_symbol}] Muitas falhas consecutivas. Pausando por 5 minutos...")
                            time.sleep(300)
                            consecutive_failures = 0
                    
                    time.sleep(self.fetch_interval)
                    
                except Exception as e:
                    consecutive_failures += 1
                    logger.critical(f"[{self.asset_symbol}] Erro crítico no thread: {e}")
                    time.sleep(60)
            
            logger.info(f"[{self.asset_symbol}] Asset Data Streaming finalizado.")
        
        self._stream_thread = threading.Thread(target=stream_worker, daemon=True)
        self._stream_thread.start()
        
    def stop_streaming(self):
        """Para o processo de streaming"""
        if not self.is_running:
            logger.warning(f"[{self.asset_symbol}] Streaming não está em execução.")
            return
        
        self.is_running = False
        logger.info(f"[{self.asset_symbol}] Parando Asset Data Streaming...")
        
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=self.fetch_interval + 5)
            if self._stream_thread.is_alive():
                logger.warning(f"[{self.asset_symbol}] Thread não terminou graciosamente.")
        
    def get_recent_data(self, limit: int = 100) -> List[BitcoinData]:
        """Retorna dados recentes da queue em memória"""
        return list(self.data_queue)[-limit:]
    
    def get_stream_statistics(self) -> Dict:
        """Retorna estatísticas atuais do streamer"""
        return {
            'asset_symbol': self.asset_symbol,
            'binance_symbol': self.binance_symbol,
            'is_running': self.is_running,
            'total_data_points': len(self.data_queue),
            'api_errors': self.api_errors,
            'last_fetch_time': self.last_fetch_time,
            'last_fetch_time_iso': datetime.fromtimestamp(self.last_fetch_time).isoformat() if self.last_fetch_time > 0 else None,
            'last_price': self.last_successful_price,
            'queue_size': len(self.data_queue),
            'subscribers_count': len(self.subscribers),
            'source': f'binance_{self.asset_symbol.lower()}',
            'fetch_interval_minutes': self.fetch_interval / 60,
            'asset_config': self.asset_config
        }
    
    def get_current_price(self) -> Optional[float]:
        """Retorna preço atual se disponível"""
        if self.data_queue:
            return self.data_queue[-1].price
        return None