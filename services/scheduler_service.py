# services/scheduler_service.py

import os
import numpy as np
import schedule
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from services.signal_generator import SignalGenerator, SignalManager
from models.trading_signal import TradingSignal, SignalStatus
from config import app_config

logger = logging.getLogger(__name__)

class TradingScheduler:
    """
    Scheduler para análise automática e gerenciamento de sinais
    """
    
    def __init__(self, signal_generator: SignalGenerator, signal_manager: SignalManager):
        self.signal_generator = signal_generator
        self.signal_manager = signal_manager
        self.is_running = False
        self.scheduler_thread = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Cache de análises técnicas para evitar requests duplicados
        self.analysis_cache = {}
        self.last_analysis_time = {}
        
        # Estatísticas de performance
        self.performance_stats = {
            'signals_generated': 0,
            'signals_closed': 0,
            'total_profit': 0.0,
            'analysis_runs': 0,
            'errors': 0
        }
        
    def start(self):
        """Inicia o scheduler"""
        if self.is_running:
            logger.warning("Scheduler already running")
            return
            
        self.is_running = True
        self._setup_schedules()
        
        # Iniciar thread do scheduler
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Trading Scheduler started")
    
    def stop(self):
        """Para o scheduler"""
        self.is_running = False
        schedule.clear()
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=10)
            
        self.executor.shutdown(wait=True)
        logger.info("Trading Scheduler stopped")
    
    def _setup_schedules(self):
        """Configura todos os agendamentos"""
        
        # Análise técnica a cada 5 minutos para BTC
        schedule.every(5).minutes.do(
            self._safe_run, self._run_technical_analysis, 'BTC'
        ).tag('analysis', 'btc')
        
        # Análise técnica a cada 5 minutos para ETH
        schedule.every(5).minutes.do(
            self._safe_run, self._run_technical_analysis, 'ETH'
        ).tag('analysis', 'eth')
        
        # Análise técnica a cada 5 minutos para SOL
        schedule.every(5).minutes.do(
            self._safe_run, self._run_technical_analysis, 'SOL'
        ).tag('analysis', 'sol')
        
        # Atualização de preços a cada 30 segundos
        schedule.every(30).seconds.do(
            self._safe_run, self._update_all_prices
        ).tag('price_update')
        
        # Limpeza de cache a cada hora
        schedule.every().hour.do(
            self._safe_run, self._cleanup_cache
        ).tag('cleanup')
        
        # Backup de sinais a cada 6 horas
        schedule.every(6).hours.do(
            self._safe_run, self._backup_signals
        ).tag('backup')
        
        # Análise de performance diária
        schedule.every().day.at("00:00").do(
            self._safe_run, self._daily_performance_analysis
        ).tag('performance')
        
        # Limpeza de sinais antigos semanalmente
        schedule.every().sunday.at("02:00").do(
            self._safe_run, self._weekly_cleanup
        ).tag('weekly_cleanup')
        
        # Verificação de saúde do sistema a cada 15 minutos
        schedule.every(15).minutes.do(
            self._safe_run, self._health_check
        ).tag('health')
        
        logger.info("Scheduler jobs configured")
    
    def _run_scheduler(self):
        """Loop principal do scheduler"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(5)
    
    def _safe_run(self, func, *args, **kwargs):
        """Executa função de forma segura com tratamento de erros"""
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in scheduled job {func.__name__}: {e}")
            self.performance_stats['errors'] += 1
    
    def _run_technical_analysis(self, asset_symbol: str):
        """Executa análise técnica para um asset específico"""
        try:
            logger.debug(f"Running technical analysis for {asset_symbol}")
            
            # Verificar se análise recente já existe
            if self._should_skip_analysis(asset_symbol):
                return
            
            # Obter dados de preço atual
            current_price = self._fetch_current_price(asset_symbol)
            if not current_price:
                logger.warning(f"Could not fetch price for {asset_symbol}")
                return
            
            # Executar análise técnica
            analysis = self._perform_technical_analysis(asset_symbol, current_price)
            if not analysis:
                logger.warning(f"Technical analysis failed for {asset_symbol}")
                return
            
            # Cache da análise
            self.analysis_cache[asset_symbol] = analysis
            self.last_analysis_time[asset_symbol] = datetime.now()
            
            # Tentar gerar sinal
            signal = self.signal_generator.generate_signal_from_analysis(
                asset_symbol=asset_symbol,
                technical_analysis=analysis,
                current_price=current_price
            )
            
            if signal:
                self.performance_stats['signals_generated'] += 1
                logger.info(f"Generated signal for {asset_symbol}: {signal.signal_type.value}")
            
            self.performance_stats['analysis_runs'] += 1
            
        except Exception as e:
            logger.error(f"Error in technical analysis for {asset_symbol}: {e}")
            self.performance_stats['errors'] += 1
    
    def _should_skip_analysis(self, asset_symbol: str, min_interval_minutes: int = 5) -> bool:
        """Verifica se deve pular análise por já ter sido feita recentemente"""
        if asset_symbol not in self.last_analysis_time:
            return False
        
        time_since_last = datetime.now() - self.last_analysis_time[asset_symbol]
        return time_since_last.total_seconds() < (min_interval_minutes * 60)
    
    def _perform_technical_analysis(self, asset_symbol: str, current_price: float) -> Optional[Dict]:
        """Executa análise técnica usando o sistema existente"""
        try:
            # Integrar com o trading analyzer existente baseado no asset
            if asset_symbol == 'BTC':
                # Usar o sistema existente do Bitcoin
                from app_fixed import app
                with app.app_context():
                    if hasattr(app, 'trading_analyzer'):
                        # Adicionar dados de preço ao analyzer
                        app.trading_analyzer.add_price_data(
                            timestamp=datetime.now(),
                            price=current_price,
                            volume=self._estimate_volume(asset_symbol)
                        )
                        
                        # Obter análise completa
                        analysis = app.trading_analyzer._calculate_comprehensive_indicators()
                        return analysis
            else:
                # Para outros assets, usar análise básica
                return self._basic_technical_analysis(asset_symbol, current_price)
                
        except Exception as e:
            logger.error(f"Error performing technical analysis for {asset_symbol}: {e}")
            return None
    
    def _basic_technical_analysis(self, asset_symbol: str, current_price: float) -> Dict:
        """Análise técnica básica para assets que não têm analyzer dedicado"""
        try:
            # Obter histórico de preços recente (simulado - substituir por dados reais)
            price_history = self._get_price_history(asset_symbol, periods=50)
            
            if len(price_history) < 20:
                return {}
            
            # Calcular indicadores básicos
            prices = np.array(price_history)
            
            # RSI simplificado
            rsi = self._calculate_simple_rsi(prices)
            
            # Médias móveis
            sma_9 = np.mean(prices[-9:]) if len(prices) >= 9 else current_price
            sma_21 = np.mean(prices[-21:]) if len(prices) >= 21 else current_price
            
            # MACD simplificado
            ema_12 = self._calculate_simple_ema(prices, 12)
            ema_26 = self._calculate_simple_ema(prices, 26)
            macd = ema_12 - ema_26
            
            # Volume estimado
            volume_ratio = self._estimate_volume_ratio(asset_symbol)
            
            return {
                'RSI': rsi,
                'SMA_9': sma_9,
                'SMA_21': sma_21,
                'MACD': macd,
                'MACD_Signal': macd * 0.9,
                'MACD_Histogram': macd * 0.1,
                'Volume_Ratio': volume_ratio,
                'BB_Position': 0.5,  # Placeholder
                'Stoch_K': min(100, max(0, rsi)),
                'Stoch_D': min(100, max(0, rsi)),
                'Trend_Strength': abs(sma_9 - sma_21) / sma_21 if sma_21 > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error in basic technical analysis: {e}")
            return {}
    
    def _get_price_history(self, asset_symbol: str, periods: int = 50) -> List[float]:
        """Obter histórico de preços - integrar com fonte de dados real"""
        try:
            # Placeholder - substituir por dados reais do seu sistema
            # Simular dados para demonstração
            current_price = self._fetch_current_price(asset_symbol) or 50000
            
            # Simular histórico com variação realística
            history = []
            base_price = current_price
            for i in range(periods):
                # Variação aleatória de -2% a +2%
                variation = np.random.uniform(-0.02, 0.02)
                price = base_price * (1 + variation)
                history.append(price)
                base_price = price
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting price history for {asset_symbol}: {e}")
            return []
    
    def _calculate_simple_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calcula RSI simples"""
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
        return 100.0 - (100.0 / (1.0 + rs))
    
    def _calculate_simple_ema(self, prices: np.ndarray, period: int) -> float:
        """Calcula EMA simples"""
        if len(prices) < period:
            return float(np.mean(prices))
        
        alpha = 2.0 / (period + 1.0)
        ema = float(prices[0])
        
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return ema
    
    def _estimate_volume(self, asset_symbol: str) -> float:
        """Estima volume - substituir por dados reais"""
        # Placeholder - volume estimado baseado no asset
        volume_estimates = {
            'BTC': 1000000,
            'ETH': 500000,
            'SOL': 200000
        }
        return volume_estimates.get(asset_symbol, 100000)
    
    def _estimate_volume_ratio(self, asset_symbol: str) -> float:
        """Estima ratio de volume - substituir por cálculo real"""
    
    def _update_all_prices(self):
        """Atualiza preços de todos os assets com sinais ativos"""
        try:
            active_assets = set()
            
            # Obter assets com sinais ativos
            for asset in ['BTC', 'ETH', 'SOL']:
                if self.signal_manager.get_active_signals(asset):
                    active_assets.add(asset)
            
            # Se não há sinais ativos, ainda atualizar pelo menos BTC
            if not active_assets:
                active_assets.add('BTC')
            
            for asset in active_assets:
                self._update_asset_price_for_signals(asset)
                
        except Exception as e:
            logger.error(f"Error updating all prices: {e}")
    
    def _update_asset_price_for_signals(self, asset_symbol: str):
        """Atualiza preço de um asset específico para seus sinais"""
        try:
            current_price = self._fetch_current_price(asset_symbol)
            if current_price:
                # Atualizar sinais ativos com novo preço
                self.signal_manager.update_signals_with_price(asset_symbol, current_price)
                
                # Integrar com trading analyzer se for BTC
                if asset_symbol == 'BTC':
                    self._update_trading_analyzer(current_price)
                
        except Exception as e:
            logger.error(f"Error updating price for {asset_symbol}: {e}")
    
    def _update_trading_analyzer(self, current_price: float):
        """Atualiza o trading analyzer existente com novo preço"""
        try:
            from app_fixed import app
            with app.app_context():
                if hasattr(app, 'trading_analyzer'):
                    app.trading_analyzer.add_price_data(
                        timestamp=datetime.now(),
                        price=current_price,
                        volume=self._estimate_volume('BTC')
                    )
        except Exception as e:
            logger.error(f"Error updating trading analyzer: {e}")
    
    def _cleanup_cache(self):
        """Limpa cache de análises antigas"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=1)
            
            # Limpar análises antigas
            expired_keys = [
                key for key, timestamp in self.last_analysis_time.items()
                if timestamp < cutoff_time
            ]
            
            for key in expired_keys:
                if key in self.analysis_cache:
                    del self.analysis_cache[key]
                del self.last_analysis_time[key]
            
            logger.debug(f"Cleaned up {len(expired_keys)} cache entries")
            
        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}")
    
    def _backup_signals(self):
        """Faz backup dos sinais"""
        try:
            backup_count = self.signal_manager.cleanup_old_signals(days_to_keep=30)
            logger.info(f"Backup completed, cleaned up {backup_count} old signals")
            
        except Exception as e:
            logger.error(f"Error in backup: {e}")
    
    def _daily_performance_analysis(self):
        """Análise diária de performance"""
        try:
            # Estatísticas gerais
            stats = self.signal_manager.get_performance_stats(days=30)
            
            # Log das estatísticas
            logger.info(f"[DAILY_STATS] Total signals: {stats.get('total_signals', 0)}")
            logger.info(f"[DAILY_STATS] Success rate: {stats.get('success_rate', 0):.1f}%")
            logger.info(f"[DAILY_STATS] Average profit: {stats.get('avg_profit', 0):.2f}%")
            
            # Salvar métricas no banco (opcional)
            self._save_daily_metrics(stats)
            
        except Exception as e:
            logger.error(f"Error in daily performance analysis: {e}")
    
    def _save_daily_metrics(self, stats: Dict):
        """Salva métricas diárias no banco"""
        try:
            # Implementar se necessário - salvar métricas históricas
            pass
        except Exception as e:
            logger.error(f"Error saving daily metrics: {e}")
    
    def _weekly_cleanup(self):
        """Limpeza semanal de dados antigos"""
        try:
            # Limpar sinais muito antigos
            deleted_count = self.signal_manager.cleanup_old_signals(days_to_keep=60)
            
            # Limpar logs antigos se necessário
            self._cleanup_old_logs()
            
            logger.info(f"Weekly cleanup completed: {deleted_count} signals removed")
            
        except Exception as e:
            logger.error(f"Error in weekly cleanup: {e}")
    
    def _cleanup_old_logs(self):
        """Limpa logs antigos"""
        try:
            # Implementar limpeza de logs se necessário
            pass
        except Exception as e:
            logger.error(f"Error cleaning up logs: {e}")
    
    def _health_check(self):
        """Verificação de saúde do sistema"""
        try:
            issues = []
            
            # Verificar se há sinais ativos há muito tempo
            active_signals = self.signal_manager.get_active_signals()
            old_signals = [
                s for s in active_signals 
                if (datetime.now() - s.created_at).days > 7
            ]
            
            if old_signals:
                issues.append(f"{len(old_signals)} sinais ativos há mais de 7 dias")
            
            # Verificar taxa de erro
            if self.performance_stats['errors'] > 10:
                issues.append(f"Alta taxa de erros: {self.performance_stats['errors']}")
            
            # Verificar se análises estão rodando
            if self.performance_stats['analysis_runs'] == 0:
                issues.append("Nenhuma análise executada recentemente")
            
            if issues:
                logger.warning(f"[HEALTH_CHECK] Issues found: {', '.join(issues)}")
            else:
                logger.debug("[HEALTH_CHECK] System healthy")
            
            # Reset de contadores diários
            if datetime.now().hour == 0:  # Meia-noite
                self.performance_stats['analysis_runs'] = 0
                self.performance_stats['errors'] = 0
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
    
    def get_scheduler_status(self) -> Dict:
        """Retorna status do scheduler"""
        try:
            return {
                'is_running': self.is_running,
                'performance_stats': self.performance_stats.copy(),
                'cache_size': len(self.analysis_cache),
                'last_analysis_times': {
                    asset: time.isoformat() for asset, time in self.last_analysis_time.items()
                },
                'active_jobs': len(schedule.jobs),
                'next_run_times': [
                    {
                        'job': str(job.job_func),
                        'next_run': job.next_run.isoformat() if job.next_run else None
                    }
                    for job in schedule.jobs[:5]  # Próximos 5 jobs
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            return {'error': str(e)}
    
    def force_analysis(self, asset_symbol: str = None):
        """Força análise imediata"""
        try:
            if asset_symbol:
                self._run_technical_analysis(asset_symbol)
                logger.info(f"Forced analysis for {asset_symbol}")
            else:
                for asset in ['BTC', 'ETH', 'SOL']:
                    self._run_technical_analysis(asset)
                logger.info("Forced analysis for all assets")
                
        except Exception as e:
            logger.error(f"Error forcing analysis: {e}")
    
    def force_price_update(self, asset_symbol: str = None):
        """Força atualização de preços"""
        try:
            if asset_symbol:
                self._update_asset_price_for_signals(asset_symbol)
                logger.info(f"Forced price update for {asset_symbol}")
            else:
                self._update_all_prices()
                logger.info("Forced price update for all assets")
                
        except Exception as e:
            logger.error(f"Error forcing price update: {e}")


# ===================================================================
# INTEGRAÇÃO COM O SISTEMA EXISTENTE
# ===================================================================

class TradingSystemIntegration:
    """
    Classe para integrar o novo sistema de sinais com o sistema existente
    """
    
    def __init__(self, app):
        self.app = app
        self.scheduler = None
        self.signal_manager = None
        self.signal_generator = None
        
    def initialize(self):
        """Inicializa a integração"""
        try:
            # Inicializar sistema de sinais
            from services.signal_generator import init_signal_system, signal_manager, signal_generator
            from config import app_config
            
            db_path = os.path.join(app_config.DATA_DIR, 'trading_signals.db')
            init_signal_system(db_path)
            
            self.signal_manager = signal_manager
            self.signal_generator = signal_generator
            
            # Inicializar scheduler
            self.scheduler = TradingScheduler(signal_generator, signal_manager)
            self.scheduler.start()
            
            # Integrar com trading analyzer existente
            self._integrate_with_existing_analyzer()
            
            logger.info("[INTEGRATION] Trading system integration completed")
            
        except Exception as e:
            logger.error(f"[INTEGRATION] Error initializing: {e}")
    
    def _integrate_with_existing_analyzer(self):
        """Integra com o trading analyzer existente"""
        try:
            if hasattr(self.app, 'trading_analyzer'):
                # Monkey patch para integrar geração de sinais
                original_add_price_data = self.app.trading_analyzer.add_price_data
                
                def enhanced_add_price_data(timestamp, price, volume=0):
                    # Chamar método original
                    original_add_price_data(timestamp, price, volume)
                    
                    # Adicionar ao novo sistema de sinais
                    if self.signal_generator:
                        # Obter análise do analyzer
                        analysis = self.app.trading_analyzer._calculate_comprehensive_indicators()
                        
                        # Tentar gerar sinal
                        if analysis:
                            signal = self.signal_generator.generate_signal_from_analysis(
                                asset_symbol='BTC',
                                technical_analysis=analysis,
                                current_price=price,
                                pattern_type=None
                            )
                            
                            if signal:
                                logger.info(f"[INTEGRATION] Generated signal via analyzer integration")
                
                # Substituir método
                self.app.trading_analyzer.add_price_data = enhanced_add_price_data
                
                logger.info("[INTEGRATION] Enhanced existing trading analyzer")
                
        except Exception as e:
            logger.error(f"[INTEGRATION] Error integrating with analyzer: {e}")
    
    def stop(self):
        """Para a integração"""
        try:
            if self.scheduler:
                self.scheduler.stop()
            
            if self.signal_generator:
                self.signal_generator.stop_monitoring()
            
            logger.info("[INTEGRATION] Trading system integration stopped")
            
        except Exception as e:
            logger.error(f"[INTEGRATION] Error stopping integration: {e}")
    
    def get_integration_status(self) -> Dict:
        """Retorna status da integração"""
        try:
            return {
                'scheduler_running': self.scheduler.is_running if self.scheduler else False,
                'signal_generator_running': self.signal_generator.is_running if self.signal_generator else False,
                'signal_manager_active': self.signal_manager is not None,
                'integration_healthy': all([
                    self.scheduler and self.scheduler.is_running,
                    self.signal_generator,
                    self.signal_manager
                ])
            }
            
        except Exception as e:
            logger.error(f"[INTEGRATION] Error getting status: {e}")
            return {'error': str(e)}


# ===================================================================
# ROUTES PARA CONTROLE DO SCHEDULER
# ===================================================================

def create_scheduler_routes():
    """
    Cria rotas para controle do scheduler.
    Adicionar ao arquivo routes/trading_routes.py
    """
    return '''
# Adicionar estas rotas ao arquivo routes/trading_routes.py

@trading_bp.route('/api/scheduler/status')
def get_scheduler_status():
    """Status do scheduler"""
    try:
        if hasattr(current_app, 'trading_integration'):
            status = current_app.trading_integration.get_integration_status()
            
            if current_app.trading_integration.scheduler:
                scheduler_status = current_app.trading_integration.scheduler.get_scheduler_status()
                status.update(scheduler_status)
            
            return jsonify({
                'success': True,
                'data': status
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Trading integration not available'
            }), 503
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@trading_bp.route('/api/scheduler/force-analysis', methods=['POST'])
def force_analysis():
    """Força análise técnica"""
    try:
        data = request.get_json() or {}
        asset = data.get('asset')
        
        if hasattr(current_app, 'trading_integration') and current_app.trading_integration.scheduler:
            current_app.trading_integration.scheduler.force_analysis(asset)
            
            return jsonify({
                'success': True,
                'message': f'Analysis forced for {asset or "all assets"}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Scheduler not available'
            }), 503
    except Exception as e:
        logger.error(f"Error forcing analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@trading_bp.route('/api/scheduler/force-price-update', methods=['POST'])
def force_price_update():
    """Força atualização de preços"""
    try:
        data = request.get_json() or {}
        asset = data.get('asset')
        
        if hasattr(current_app, 'trading_integration') and current_app.trading_integration.scheduler:
            current_app.trading_integration.scheduler.force_price_update(asset)
            
            return jsonify({
                'success': True,
                'message': f'Price update forced for {asset or "all assets"}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Scheduler not available'
            }), 503
    except Exception as e:
        logger.error(f"Error forcing price update: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@trading_bp.route('/api/scheduler/performance-stats')
def get_performance_stats():
    """Estatísticas de performance do scheduler"""
    try:
        if hasattr(current_app, 'trading_integration') and current_app.trading_integration.signal_manager:
            stats = current_app.trading_integration.signal_manager.get_performance_stats(days=30)
            
            return jsonify({
                'success': True,
                'data': stats
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Signal manager not available'
            }), 503
    except Exception as e:
        logger.error(f"Error getting performance stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    '''