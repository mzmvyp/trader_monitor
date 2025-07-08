# your_project/services/multi_asset_manager.py - ARQUIVO NOVO

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import sqlite3
import threading
from utils.logging_config import logger
from config import app_config
from services.generic_asset_streamer import GenericAssetStreamer
from services.trading_analyzer import EnhancedTradingAnalyzer
from database.setup import setup_trading_analyzer_db, setup_bitcoin_stream_db

class MultiAssetManager:
    """
    Gerenciador central para múltiplos assets.
    Coordena streamers, analyzers e fornece APIs consolidadas.
    """
    
    def __init__(self):
        """Inicializa o gerenciador multi-asset"""
        self.streamers: Dict[str, GenericAssetStreamer] = {}
        self.analyzers: Dict[str, EnhancedTradingAnalyzer] = {}
        self.supported_assets = app_config.get_supported_asset_symbols()
        self.lock = threading.Lock()
        
        logger.info(f"[MULTI] Inicializando Multi-Asset Manager para: {', '.join(self.supported_assets)}")
        
        self._setup_databases()
        self._initialize_components()
    
    def _setup_databases(self):
        """Configura bancos de dados para todos os assets"""
        logger.info("[MULTI] Configurando bancos de dados multi-asset...")
        
        for asset_symbol in self.supported_assets:
            try:
                # Setup stream database
                stream_db_path = app_config.get_asset_db_path(asset_symbol, 'stream')
                setup_bitcoin_stream_db(stream_db_path)  # Reutilizar função existente
                
                # Setup trading database  
                trading_db_path = app_config.get_asset_db_path(asset_symbol, 'trading')
                setup_trading_analyzer_db(trading_db_path)  # Reutilizar função existente
                
                logger.info(f"[MULTI] Database setup completo para {asset_symbol}")
                
            except Exception as e:
                logger.error(f"[MULTI] Erro ao configurar database para {asset_symbol}: {e}")
    
    def _initialize_components(self):
        """Inicializa streamers e analyzers para todos os assets"""
        logger.info("[MULTI] Inicializando componentes...")
        
        for asset_symbol in self.supported_assets:
            try:
                # Inicializar streamer
                streamer = GenericAssetStreamer(
                    asset_symbol=asset_symbol,
                    max_queue_size=app_config.MULTI_ASSET_MAX_QUEUE_SIZE,
                    fetch_interval=app_config.ASSET_INTERVALS.get(asset_symbol, 300)
                )
                self.streamers[asset_symbol] = streamer
                
                # Inicializar analyzer
                trading_db_path = app_config.get_asset_db_path(asset_symbol, 'trading')
                analyzer = EnhancedTradingAnalyzer(db_path=trading_db_path)
                self.analyzers[asset_symbol] = analyzer
                
                # Conectar streamer ao analyzer
                streamer.add_subscriber(
                    lambda data, asset=asset_symbol: self._feed_analyzer(asset, data)
                )
                
                logger.info(f"[MULTI] Componentes inicializados para {asset_symbol}")
                
            except Exception as e:
                logger.error(f"[MULTI] Erro ao inicializar componentes para {asset_symbol}: {e}")
    
    def _feed_analyzer(self, asset_symbol: str, data):
        """Alimenta o analyzer com dados do streamer"""
        try:
            analyzer = self.analyzers.get(asset_symbol)
            if analyzer and data:
                analyzer.add_price_data(
                    timestamp=data.timestamp,
                    price=data.price,
                    volume=data.volume_24h
                )
                logger.debug(f"[MULTI] {asset_symbol} analyzer alimentado: ${data.price:.2f}")
        except Exception as e:
            logger.error(f"[MULTI] Erro ao alimentar analyzer {asset_symbol}: {e}")
    
    def start_streaming(self, assets: Optional[List[str]] = None):
        """
        Inicia streaming para assets especificados ou todos.
        
        Args:
            assets: Lista de símbolos de assets ou None para todos
        """
        if assets is None:
            assets = self.supported_assets
        
        with self.lock:
            for asset_symbol in assets:
                if asset_symbol in self.streamers:
                    try:
                        self.streamers[asset_symbol].start_streaming()
                        logger.info(f"[MULTI] Streaming iniciado para {asset_symbol}")
                    except Exception as e:
                        logger.error(f"[MULTI] Erro ao iniciar streaming {asset_symbol}: {e}")
                else:
                    logger.warning(f"[MULTI] Asset não suportado: {asset_symbol}")
    
    def stop_streaming(self, assets: Optional[List[str]] = None):
        """
        Para streaming para assets especificados ou todos.
        
        Args:
            assets: Lista de símbolos de assets ou None para todos
        """
        if assets is None:
            assets = self.supported_assets
        
        with self.lock:
            for asset_symbol in assets:
                if asset_symbol in self.streamers:
                    try:
                        self.streamers[asset_symbol].stop_streaming()
                        logger.info(f"[MULTI] Streaming parado para {asset_symbol}")
                    except Exception as e:
                        logger.error(f"[MULTI] Erro ao parar streaming {asset_symbol}: {e}")
    
    def get_asset_streamer(self, asset_symbol: str) -> Optional[GenericAssetStreamer]:
        """Retorna streamer do asset específico"""
        return self.streamers.get(asset_symbol.upper())
    
    def get_asset_analyzer(self, asset_symbol: str) -> Optional[EnhancedTradingAnalyzer]:
        """Retorna analyzer do asset específico"""
        return self.analyzers.get(asset_symbol.upper())
    
    def get_overview_data(self) -> Dict[str, Any]:
        """Retorna overview consolidado de todos os assets"""
        overview = {
            'timestamp': datetime.now().isoformat(),
            'assets': {},
            'totals': {
                'active_streamers': 0,
                'total_signals': 0,
                'total_data_points': 0
            },
            'performance_comparison': {}
        }
        
        for asset_symbol in self.supported_assets:
            try:
                asset_data = self._get_asset_summary(asset_symbol)
                overview['assets'][asset_symbol] = asset_data
                
                # Atualizar totais
                if asset_data['streaming']['is_running']:
                    overview['totals']['active_streamers'] += 1
                
                overview['totals']['total_signals'] += asset_data['trading']['total_signals']
                overview['totals']['total_data_points'] += asset_data['streaming']['data_points']
                
            except Exception as e:
                logger.error(f"[MULTI] Erro ao obter dados de {asset_symbol}: {e}")
                overview['assets'][asset_symbol] = {'error': str(e)}
        
        # Calcular comparações de performance
        overview['performance_comparison'] = self._calculate_performance_comparison()
        
        return overview
    
    def _get_asset_summary(self, asset_symbol: str) -> Dict[str, Any]:
        """Retorna resumo de um asset específico"""
        streamer = self.streamers.get(asset_symbol)
        analyzer = self.analyzers.get(asset_symbol)
        asset_config = app_config.get_asset_config(asset_symbol)
        
        summary = {
            'symbol': asset_symbol,
            'name': asset_config['name'],
            'config': asset_config,
            'streaming': {
                'is_running': False,
                'current_price': 0,
                'data_points': 0,
                'last_update': None,
                'api_errors': 0
            },
            'trading': {
                'total_signals': 0,
                'active_signals': 0,
                'win_rate': 0,
                'current_analysis': {}
            }
        }
        
        # Dados do streamer
        if streamer:
            stream_stats = streamer.get_stream_statistics()
            summary['streaming'] = {
                'is_running': stream_stats['is_running'],
                'current_price': stream_stats['last_price'] or 0,
                'data_points': stream_stats['total_data_points'],
                'last_update': stream_stats['last_fetch_time_iso'],
                'api_errors': stream_stats['api_errors']
            }
        
        # Dados do analyzer
        if analyzer:
            try:
                analysis = analyzer.get_comprehensive_analysis()
                if 'error' not in analysis:
                    summary['trading'] = {
                        'total_signals': len(analyzer.signals),
                        'active_signals': len(analysis.get('active_signals', [])),
                        'win_rate': analysis.get('performance_summary', {}).get('win_rate', 0),
                        'current_analysis': {
                            'recommended_action': analysis.get('signal_analysis', {}).get('recommended_action', 'HOLD'),
                            'confidence': analysis.get('signal_analysis', {}).get('confidence', 0),
                            'market_trend': analysis.get('market_analysis', {}).get('trend', 'NEUTRAL')
                        }
                    }
            except Exception as e:
                logger.error(f"[MULTI] Erro ao obter análise de {asset_symbol}: {e}")
                summary['trading']['error'] = str(e)
        
        return summary
    
    def _calculate_performance_comparison(self) -> Dict[str, Any]:
        """Calcula comparação de performance entre assets"""
        comparison = {
            'price_changes_24h': {},
            'volatility_comparison': {},
            'signal_performance': {},
            'correlation_matrix': {}
        }
        
        try:
            # Comparar mudanças de preço 24h
            for asset_symbol in self.supported_assets:
                streamer = self.streamers.get(asset_symbol)
                if streamer and streamer.data_queue:
                    recent_data = list(streamer.data_queue)
                    if len(recent_data) > 0:
                        latest = recent_data[-1]
                        comparison['price_changes_24h'][asset_symbol] = {
                            'current_price': latest.price,
                            'change_24h': latest.price_change_24h,
                            'volume_24h': latest.volume_24h
                        }
            
            # Comparar performance de sinais
            for asset_symbol in self.supported_assets:
                analyzer = self.analyzers.get(asset_symbol)
                if analyzer:
                    try:
                        performance = analyzer.get_performance_report(7)  # Últimos 7 dias
                        if 'error' not in performance:
                            comparison['signal_performance'][asset_symbol] = {
                                'win_rate': performance.get('overall_performance', {}).get('win_rate', 0),
                                'total_trades': performance.get('overall_performance', {}).get('closed_trades', 0),
                                'net_profit': performance.get('overall_performance', {}).get('net_profit_pct', 0)
                            }
                    except Exception as e:
                        logger.debug(f"[MULTI] Performance data não disponível para {asset_symbol}: {e}")
            
            # Análise de correlação básica (se habilitada)
            if app_config.CORRELATION_ANALYSIS_ENABLED:
                comparison['correlation_matrix'] = self._calculate_price_correlations()
                
        except Exception as e:
            logger.error(f"[MULTI] Erro ao calcular comparação de performance: {e}")
        
        return comparison
    
    def _calculate_price_correlations(self) -> Dict[str, float]:
        """Calcula correlações de preço entre assets"""
        correlations = {}
        
        try:
            # Obter dados de preço dos últimos períodos para cada asset
            price_data = {}
            for asset_symbol in self.supported_assets:
                streamer = self.streamers.get(asset_symbol)
                if streamer and streamer.data_queue:
                    prices = [data.price for data in list(streamer.data_queue)[-50:]]  # Últimos 50 pontos
                    if len(prices) >= 10:  # Mínimo de dados para correlação
                        price_data[asset_symbol] = prices
            
            # Calcular correlações par a par
            asset_pairs = []
            for i, asset1 in enumerate(price_data.keys()):
                for asset2 in list(price_data.keys())[i+1:]:
                    asset_pairs.append((asset1, asset2))
            
            for asset1, asset2 in asset_pairs:
                try:
                    correlation = self._calculate_correlation(price_data[asset1], price_data[asset2])
                    correlations[f"{asset1}_{asset2}"] = correlation
                except Exception as e:
                    logger.debug(f"[MULTI] Erro ao calcular correlação {asset1}-{asset2}: {e}")
                    
        except Exception as e:
            logger.error(f"[MULTI] Erro na análise de correlações: {e}")
        
        return correlations
    
    def _calculate_correlation(self, prices1: List[float], prices2: List[float]) -> float:
        """Calcula correlação simples entre duas séries de preços"""
        if len(prices1) != len(prices2) or len(prices1) < 2:
            return 0.0
        
        # Calcular retornos percentuais
        returns1 = [(prices1[i] - prices1[i-1]) / prices1[i-1] for i in range(1, len(prices1))]
        returns2 = [(prices2[i] - prices2[i-1]) / prices2[i-1] for i in range(1, len(prices2))]
        
        if len(returns1) < 2:
            return 0.0
        
        # Calcular correlação de Pearson simplificada
        mean1 = sum(returns1) / len(returns1)
        mean2 = sum(returns2) / len(returns2)
        
        numerator = sum((returns1[i] - mean1) * (returns2[i] - mean2) for i in range(len(returns1)))
        
        sum_sq1 = sum((r - mean1) ** 2 for r in returns1)
        sum_sq2 = sum((r - mean2) ** 2 for r in returns2)
        
        denominator = (sum_sq1 * sum_sq2) ** 0.5
        
        if denominator == 0:
            return 0.0
        
        correlation = numerator / denominator
        return round(correlation, 3)
    
    def get_asset_data(self, asset_symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Retorna dados específicos de um asset"""
        asset_symbol = asset_symbol.upper()
        
        if asset_symbol not in self.supported_assets:
            return {'error': f'Asset {asset_symbol} não suportado'}
        
        try:
            streamer = self.streamers.get(asset_symbol)
            analyzer = self.analyzers.get(asset_symbol)
            
            result = {
                'asset_symbol': asset_symbol,
                'config': app_config.get_asset_config(asset_symbol),
                'streaming_data': {},
                'analysis_data': {},
                'recent_data': []
            }
            
            # Dados do streamer
            if streamer:
                result['streaming_data'] = streamer.get_stream_statistics()
                result['recent_data'] = [data.to_dict() for data in streamer.get_recent_data(limit)]
            
            # Dados do analyzer
            if analyzer:
                result['analysis_data'] = analyzer.get_comprehensive_analysis()
            
            return result
            
        except Exception as e:
            logger.error(f"[MULTI] Erro ao obter dados de {asset_symbol}: {e}")
            return {'error': str(e)}
    
    def get_consolidated_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retorna sinais consolidados de todos os assets"""
        all_signals = []
        
        for asset_symbol in self.supported_assets:
            analyzer = self.analyzers.get(asset_symbol)
            if analyzer and analyzer.signals:
                for signal in analyzer.signals[-limit:]:
                    signal_data = signal.copy()
                    signal_data['asset_symbol'] = asset_symbol
                    signal_data['asset_name'] = app_config.get_asset_config(asset_symbol)['name']
                    all_signals.append(signal_data)
        
        # Ordenar por timestamp mais recente
        all_signals.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return all_signals[:limit]
    
    def get_system_health(self) -> Dict[str, Any]:
        """Retorna status de saúde do sistema multi-asset"""
        health = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'HEALTHY',
            'assets_status': {},
            'summary': {
                'total_assets': len(self.supported_assets),
                'active_streamers': 0,
                'total_errors': 0,
                'data_quality': 'GOOD'
            }
        }
        
        total_errors = 0
        active_streamers = 0
        
        for asset_symbol in self.supported_assets:
            asset_health = {
                'streamer_running': False,
                'analyzer_healthy': False,
                'recent_errors': 0,
                'data_points': 0,
                'last_update': None
            }
            
            # Status do streamer
            streamer = self.streamers.get(asset_symbol)
            if streamer:
                stats = streamer.get_stream_statistics()
                asset_health.update({
                    'streamer_running': stats['is_running'],
                    'recent_errors': stats['api_errors'],
                    'data_points': stats['total_data_points'],
                    'last_update': stats['last_fetch_time_iso']
                })
                
                if stats['is_running']:
                    active_streamers += 1
                
                total_errors += stats['api_errors']
            
            # Status do analyzer
            analyzer = self.analyzers.get(asset_symbol)
            if analyzer:
                try:
                    system_status = analyzer.get_system_status()
                    asset_health['analyzer_healthy'] = 'error' not in system_status
                except Exception as e:
                    asset_health['analyzer_healthy'] = False
                    logger.debug(f"[MULTI] Analyzer health check failed para {asset_symbol}: {e}")
            
            health['assets_status'][asset_symbol] = asset_health
        
        # Atualizar summary
        health['summary'].update({
            'active_streamers': active_streamers,
            'total_errors': total_errors
        })
        
        # Determinar status geral
        if active_streamers == 0:
            health['overall_status'] = 'STOPPED'
        elif total_errors > 10:
            health['overall_status'] = 'DEGRADED'
        elif active_streamers < len(self.supported_assets) // 2:
            health['overall_status'] = 'PARTIAL'
        
        return health
    
    def shutdown(self):
        """Desliga todos os componentes graciosamente"""
        logger.info("[MULTI] Iniciando shutdown do Multi-Asset Manager...")
        
        # Parar todos os streamers
        self.stop_streaming()
        
        # Salvar estado dos analyzers
        for asset_symbol, analyzer in self.analyzers.items():
            try:
                analyzer.save_analyzer_state()
                logger.info(f"[MULTI] Estado salvo para {asset_symbol}")
            except Exception as e:
                logger.error(f"[MULTI] Erro ao salvar estado de {asset_symbol}: {e}")
        
        logger.info("[MULTI] Multi-Asset Manager desligado com sucesso")