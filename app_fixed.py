# app_fixed.py - Versão COMPLETA INCREMENTADA com Trading Signals + Multi-Timeframe + SIGNAL MONITOR

import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta
import traceback
from services.signal_generator import init_signal_system, signals_bp, signal_generator, signal_manager
from models.trading_signal import TradingSignal, SignalType, SignalSource

from flask import redirect


print("[START] Inicializando Sistema Integrado Multi-Asset Trading com Persistência COMPLETA + MULTI-TIMEFRAME + TRADING SIGNALS...")

try:
    from flask import Flask, render_template, jsonify, request, current_app

    # Import modularized components
    from config import app_config
    from utils.logging_config import logger
    from models.bitcoin_data import BitcoinData
    from database.setup import initialize_databases
    from database.processors import BitcoinStreamProcessor
    from services.bitcoin_streamer import BitcoinDataStreamer
    from services.trading_analyzer import EnhancedTradingAnalyzer
    from services.analytics_engine import BitcoinAnalyticsEngine

    # ===== NOVOS IMPORTS - SISTEMAS COMPLETOS =====
    from config_manager import DynamicConfigManager, dynamic_config_manager
    from middleware.config_middleware import ConfigurationMiddleware, config_middleware
    from services.notification_service import NotificationService, notification_service, setup_notification_integration
    from services.backup_service import BackupService, backup_service

    # ===== NOVOS IMPORTS - SISTEMA TRADING SIGNALS =====
    try:
        from services.signal_generator import init_signal_system, signals_bp, signal_generator, signal_manager
        from models.trading_signal import TradingSignal, SignalType, SignalSource
        TRADING_SIGNALS_AVAILABLE = True
        logger.info("[INIT] Sistema Trading Signals carregado ✅")
    except ImportError as e:
        TRADING_SIGNALS_AVAILABLE = False
        logger.warning(f"[INIT] Sistema Trading Signals não disponível: {e}")

    # ===== NOVOS IMPORTS - SISTEMA MULTI-TIMEFRAME =====
    try:
        from services.multi_timeframe_manager import MultiTimeframeManager
        from services.websocket_multi_adapter import WebSocketMultiAdapter
        from routes.multi_strategy_routes import setup_multi_strategy_routes
        from services.websocket_integration import ExistingSystemIntegration
        MULTI_TIMEFRAME_AVAILABLE = True
        logger.info("[INIT] Sistema Multi-Timeframe carregado ✅")
    except ImportError as e:
        MULTI_TIMEFRAME_AVAILABLE = False
        logger.warning(f"[INIT] Sistema Multi-Timeframe não disponível: {e}")

    # Multi-Asset Components (se existirem)
    try:
        from services.multi_asset_manager import MultiAssetManager
        MULTI_ASSET_AVAILABLE = True
        logger.info("[INIT] Multi-Asset components carregados")
    except ImportError as e:
        MULTI_ASSET_AVAILABLE = False
        logger.warning(f"[INIT] Multi-Asset não disponível: {e}")

    # Import blueprints for routes
    from routes.main_routes import main_bp
    from routes.bitcoin_routes import bitcoin_bp
    from routes.trading_routes import trading_bp
    from routes.settings_routes import settings_bp

    # Multi-Asset Routes (se existirem)
    try:
        from routes.multi_asset_routes import multi_asset_bp
        MULTI_ASSET_ROUTES_AVAILABLE = True
        logger.info("[INIT] Multi-Asset routes carregados")
    except ImportError as e:
        MULTI_ASSET_ROUTES_AVAILABLE = False
        logger.warning(f"[INIT] Multi-Asset routes não disponíveis: {e}")

    logger.info("[INIT] Todos os imports concluídos com sucesso")

except Exception as e:
    print(f"[CRITICAL ERROR] Erro nos imports: {e}")
    traceback.print_exc()
    sys.exit(1)

# ==================== INTEGRATED CONTROLLER COMPLETO + MULTI-TIMEFRAME + TRADING SIGNALS + SIGNAL MONITOR ====================
class IntegratedController:
    """
    Controlador principal COMPLETO da aplicação, responsável por inicializar
    todos os componentes incluindo os novos sistemas de configuração, 
    notificações, backup, MULTI-TIMEFRAME, TRADING SIGNALS E SIGNAL MONITOR.
    """
    def __init__(self):
        """
        Initializes the Flask application and all integrated components.
        """
        logger.info("[CTRL] Inicializando IntegratedController COMPLETO + MULTI-TIMEFRAME + TRADING SIGNALS + SIGNAL MONITOR...")
        
        self.app = Flask(__name__)
        self.app.config.from_object(app_config)

        # Store datetime and timedelta directly on app for easy access in routes
        self.app.datetime = datetime
        self.app.timedelta = timedelta

        # ===== INICIALIZAR NOVOS SISTEMAS PRIMEIRO =====
        logger.info("[CTRL] Inicializando sistemas de configuração...")
        
        # 1. Dynamic Config Manager
        self.config_manager = dynamic_config_manager
        
        # 2. Configuration Middleware
        self.config_middleware = config_middleware
        self.config_middleware.register_app_instance(self.app)
        
        # 3. Notification Service
        self.notification_service = notification_service
        
        # 4. Backup Service
        self.backup_service = backup_service
        
        logger.info("[CTRL] Sistemas avançados inicializados ✅")

        # Initialize core services
        logger.info("[CTRL] Inicializando serviços principais...")
        
        self.bitcoin_streamer = BitcoinDataStreamer(
            max_queue_size=app_config.BITCOIN_STREAM_MAX_QUEUE_SIZE,
            fetch_interval=app_config.BITCOIN_STREAM_FETCH_INTERVAL_SECONDS
        )
        logger.info("[CTRL] BitcoinStreamer criado")
        
        self.bitcoin_processor = BitcoinStreamProcessor(
            db_path=app_config.BITCOIN_STREAM_DB
        )
        logger.info("[CTRL] BitcoinProcessor criado")
        
        self.bitcoin_analytics = BitcoinAnalyticsEngine(
            db_path=app_config.BITCOIN_STREAM_DB
        )
        logger.info("[CTRL] BitcoinAnalytics criado")
        
         
        self.trading_analyzer = EnhancedTradingAnalyzer(
            db_path=app_config.TRADING_ANALYZER_DB
        )
        logger.info("[CTRL] TradingAnalyzer criado")
        
        # ===== NOVO: CONFIGURAR REFERÊNCIA DO BITCOIN STREAMER =====
        # Fazer isso APÓS criar bitcoin_streamer E trading_analyzer
        self.trading_analyzer.set_bitcoin_streamer_reference(self.bitcoin_streamer)
        
        # ===== NOVO: INICIAR SIGNAL MONITOR =====
        if self.trading_analyzer.start_signal_monitoring():
            logger.info("[CTRL] Signal Monitor iniciado ✅")
        else:
            logger.warning("[CTRL] Signal Monitor não pôde ser iniciado")

        # ===== INICIALIZAR SISTEMA TRADING SIGNALS =====
        if TRADING_SIGNALS_AVAILABLE:
            try:
                logger.info("[CTRL] Inicializando sistema Trading Signals...")
                
                # Inicializar sistema de sinais
                signals_db_path = os.path.join(app_config.DATA_DIR, 'trading_signals.db')
                init_signal_system(signals_db_path)
                
                # Armazenar instâncias
                self.signal_generator = signal_generator
                self.signal_manager = signal_manager
                
                logger.info("[CTRL] Sistema Trading Signals inicializado ✅")
                
            except Exception as e:
                logger.error(f"[CTRL] Erro ao inicializar Trading Signals: {e}")
                self.signal_generator = None
                self.signal_manager = None
        else:
            self.signal_generator = None
            self.signal_manager = None

        # ===== INICIALIZAR SISTEMA MULTI-TIMEFRAME =====
        if MULTI_TIMEFRAME_AVAILABLE:
            try:
                logger.info("[CTRL] Inicializando sistema Multi-Timeframe...")
                
                # 1. Criar manager multi-timeframe
                self.multi_manager = MultiTimeframeManager(db_path=app_config.BITCOIN_STREAM_DB)
                
                # 2. Criar adaptador WebSocket
                self.multi_adapter = WebSocketMultiAdapter(self.multi_manager, self.app)
                
                # 3. Criar integração com sistema atual
                self.multi_integration = ExistingSystemIntegration(self.multi_manager, self.multi_adapter)
                
                # 4. Configurar integração com BitcoinStreamer atual
                self._setup_multi_timeframe_integration()
                
                logger.info("[CTRL] Sistema Multi-Timeframe inicializado ✅")
                
            except Exception as e:
                logger.error(f"[CTRL] Erro ao inicializar Multi-Timeframe: {e}")
                self.multi_manager = None
                self.multi_adapter = None
                self.multi_integration = None
        else:
            self.multi_manager = None
            self.multi_adapter = None  
            self.multi_integration = None
        
        # Multi-Asset Manager (se disponível)
        if MULTI_ASSET_AVAILABLE:
            try:
                self.multi_asset_manager = MultiAssetManager()
                logger.info("[CTRL] MultiAssetManager criado")
            except Exception as e:
                logger.error(f"[CTRL] Erro ao criar MultiAssetManager: {e}")
                self.multi_asset_manager = None
        else:
            self.multi_asset_manager = None
        
        # ===== ATTACH INSTANCES TO FLASK APP =====
        self.app.bitcoin_streamer = self.bitcoin_streamer
        self.app.bitcoin_processor = self.bitcoin_processor
        self.app.bitcoin_analytics = self.bitcoin_analytics
        self.app.trading_analyzer = self.trading_analyzer
        
        # ===== ATTACH NOVOS SISTEMAS =====
        self.app.config_manager = self.config_manager
        self.app.config_middleware = self.config_middleware
        self.app.notification_service = self.notification_service
        self.app.backup_service = self.backup_service
        
        # ===== ATTACH SISTEMA TRADING SIGNALS =====
        if self.signal_generator:
            self.app.signal_generator = self.signal_generator
            self.app.signal_manager = self.signal_manager
        
        # ===== ATTACH SISTEMA MULTI-TIMEFRAME =====
        if self.multi_manager:
            self.app.multi_manager = self.multi_manager
            self.app.multi_adapter = self.multi_adapter
            self.app.multi_integration = self.multi_integration
        
        if self.multi_asset_manager:
            self.app.multi_asset_manager = self.multi_asset_manager

        self.last_trading_update = 0
        self.trading_update_interval = app_config.TRADING_ANALYZER_UPDATE_INTERVAL_SECONDS
        
        # ===== CONFIGURAR INTEGRAÇÃO ENTRE SISTEMAS =====
        logger.info("[CTRL] Configurando integrações...")
        self._setup_system_integration()
        
        # Register subscribers for Bitcoin data stream
        logger.info("[CTRL] Registrando subscribers...")
        self.bitcoin_streamer.add_subscriber(self.bitcoin_processor.process_stream_data)
        self.bitcoin_streamer.add_subscriber(self._feed_trading_analyzer_debounced)
        
        # ===== REGISTRAR SUBSCRIBER TRADING SIGNALS =====
        if self.signal_generator:
            self.bitcoin_streamer.add_subscriber(self._feed_trading_signals_system)
            logger.info("[CTRL] Trading Signals subscriber registrado ✅")
        
        # ===== REGISTRAR SUBSCRIBER MULTI-TIMEFRAME =====
        if self.multi_integration:
            self.bitcoin_streamer.add_subscriber(self._feed_multi_timeframe_system)
            logger.info("[CTRL] Multi-Timeframe subscriber registrado ✅")
        
        logger.info("[CTRL] Configurando routes e error handlers...")
        self.setup_routes()
        self.setup_error_handlers()
        
        
        logger.info("[CTRL] IntegratedController COMPLETO + MULTI-TIMEFRAME + TRADING SIGNALS + SIGNAL MONITOR inicializado com sucesso ✅")

    def _feed_trading_signals_system(self, bitcoin_data: BitcoinData):
        """
        Alimenta o sistema de trading signals com dados do BitcoinStreamer
        """
        if not self.signal_generator:
            return
        
        try:
            # Preparar dados de análise técnica básica
            technical_analysis = {
                'price': bitcoin_data.price,
                'volume': bitcoin_data.volume_24h,
                'price_change_24h': bitcoin_data.price_change_24h,
                'market_cap': bitcoin_data.market_cap,
                'timestamp': bitcoin_data.timestamp
            }
            
            # Tentar gerar sinal usando análise técnica do trading_analyzer
            try:
                trading_status = self.trading_analyzer.get_system_status()
                if 'analysis' in trading_status:
                    analysis = trading_status['analysis']
                    
                    # Enriquecer com dados do trading analyzer
                    technical_analysis.update({
                        'RSI': analysis.get('rsi', 50),
                        'MACD': analysis.get('macd', {}).get('macd', 0),
                        'MACD_Signal': analysis.get('macd', {}).get('signal', 0),
                        'BB_Position': analysis.get('bollinger', {}).get('position', 0.5),
                        'Volume_Ratio': analysis.get('volume_analysis', {}).get('volume_ratio', 1.0),
                        'Trend': analysis.get('trend_analysis', {}).get('trend', 'NEUTRAL')
                    })
            except Exception as e:
                logger.debug(f"[TRADING-SIGNALS] Erro ao obter análise técnica: {e}")
            
            # Gerar sinal se condições forem atendidas
            signal = self.signal_generator.generate_signal_from_analysis(
                asset_symbol='BTC',
                technical_analysis=technical_analysis,
                current_price=bitcoin_data.price
            )
            
            if signal:
                logger.info(f"[TRADING-SIGNALS] Novo sinal gerado: {signal.signal_type.value} - Confiança: {signal.confidence:.1f}%")
                
                # Enviar notificação para sinais de alta confiança
                if signal.confidence >= 75:
                    self.notification_service.send_notification(
                        'TRADING_SIGNAL',
                        f'Sinal de Trading - {signal.signal_type.value}',
                        f'BTC: {signal.signal_type.value} com {signal.confidence:.1f}% confiança',
                        {
                            'asset': 'BTC',
                            'signal_type': signal.signal_type.value,
                            'entry_price': signal.entry_price,
                            'target_1': signal.target_1,
                            'stop_loss': signal.stop_loss,
                            'confidence': signal.confidence,
                            'reasons': signal.reasons
                        },
                        'high' if signal.confidence >= 85 else 'medium'
                    )
                
                # Atualizar preço dos sinais ativos
                if self.signal_manager:
                    self.signal_manager.update_signals_with_price('BTC', bitcoin_data.price)
            
        except Exception as e:
            logger.error(f"[TRADING-SIGNALS] Erro ao alimentar sistema de sinais: {e}")

    def _setup_multi_timeframe_integration(self):
        """Configura integração específica do sistema multi-timeframe"""
        try:
            logger.info("[MULTI-TF] Configurando integração Multi-Timeframe...")
            
            # Configurar callback para sinais multi-timeframe
            def on_multi_timeframe_signal(signal_data):
                """Callback para novos sinais multi-timeframe"""
                try:
                    if signal_data.get('new_signals'):
                        asset = signal_data.get('asset', 'UNKNOWN')
                        new_signals = signal_data['new_signals']
                        
                        # Log dos sinais
                        logger.info(f"[MULTI-TF] {asset}: {len(new_signals)} novos sinais")
                        
                        for strategy, signal in new_signals.items():
                            action = signal.get('action', 'HOLD')
                            confidence = signal.get('confidence', 0)
                            timeframe = signal.get('timeframe', '?')
                            
                            logger.info(f"[MULTI-TF]   {strategy.upper()} ({timeframe}): {action} - {confidence:.1f}%")
                            
                            # Enviar notificação para sinais importantes
                            if confidence >= 70 and action != 'HOLD':
                                self.notification_service.send_notification(
                                    'TRADING_SIGNAL',
                                    f'{asset} - Sinal {strategy.upper()}',
                                    f'{action} com {confidence:.1f}% confiança ({timeframe})',
                                    {
                                        'asset': asset,
                                        'strategy': strategy,
                                        'action': action,
                                        'confidence': confidence,
                                        'timeframe': timeframe,
                                        'reasons': signal.get('reasons', [])[:3]
                                    },
                                    'high' if confidence >= 80 else 'medium'
                                )
                        
                        # Backup automático para sinais de alta confiança
                        high_confidence_signals = [
                            s for s in new_signals.values() 
                            if s.get('confidence', 0) >= 75 and s.get('action') != 'HOLD'
                        ]
                        
                        if high_confidence_signals:
                            self.backup_service.create_backup(
                                backup_type='high_confidence_multi_signal',
                                auto_cleanup=True
                            )
                
                except Exception as e:
                    logger.error(f"[MULTI-TF] Erro no callback de sinal: {e}")
            
            # Registrar callback
            if hasattr(self.multi_adapter, 'register_signal_callback'):
                self.multi_adapter.register_signal_callback(on_multi_timeframe_signal)
            
            logger.info("[MULTI-TF] Integração Multi-Timeframe configurada ✅")
            
        except Exception as e:
            logger.error(f"[MULTI-TF] Erro na configuração Multi-Timeframe: {e}")

    def _feed_multi_timeframe_system(self, bitcoin_data: BitcoinData):
        """
        Alimenta o sistema multi-timeframe com dados do BitcoinStreamer atual
        """
        if not self.multi_adapter:
            return
        
        try:
            # Converter BitcoinData para formato do multi-timeframe
            price_data = {
                'price': bitcoin_data.price,
                'volume': bitcoin_data.volume_24h,
                'timestamp': bitcoin_data.timestamp,
                'market_cap': bitcoin_data.market_cap,
                'price_change_24h': bitcoin_data.price_change_24h
            }
            
            # Processar com multi-timeframe (para BTC)
            result = self.multi_adapter.on_price_update('BTC', price_data)
            
            # Debug opcional
            if result.get('new_signals'):
                logger.debug(f"[MULTI-TF] BTC: {len(result['new_signals'])} novos sinais gerados")
            
        except Exception as e:
            logger.error(f"[MULTI-TF] Erro ao alimentar sistema multi-timeframe: {e}")
    
    def _setup_system_integration(self):
        """Configura integração entre todos os sistemas"""
        try:
            # ===== INTEGRAÇÃO CONFIGURAÇÃO + MIDDLEWARE =====
            
            # Registrar callback para notificar sobre mudanças de configuração
            def on_config_change_notify(old_config, new_config):
                try:
                    # Calcular mudanças
                    changes = self._calculate_config_changes(old_config, new_config)
                    
                    if changes:
                        self.notification_service.send_notification(
                            'CONFIG_CHANGED',
                            f'Configuração Alterada ({len(changes)} mudanças)',
                            f'Sistema teve {len(changes)} configurações modificadas',
                            {'changes': changes[:5], 'total_changes': len(changes)}
                        )
                        
                        # Criar backup automático após mudanças críticas
                        critical_changes = [c for c in changes if any(
                            keyword in c.lower() for keyword in ['trading', 'signal', 'indicator', 'timeframe']
                        )]
                        
                        if critical_changes:
                             logger.info("[INTEGRATION] Agendando backup (assíncrono)")
                             def async_backup():
                                 time.sleep(10)  # Aguardar sistema estabilizar
                                 try:
                                     self.backup_service.create_backup(
                                     backup_type='config_change',
                                     auto_cleanup=True
                                    )
                
                                 except Exception as e:
                                        logger.debug(f"[BACKUP] Erro: {e}")
    
                    threading.Thread(target=async_backup, daemon=True).start()
                except Exception as e:
                    logger.error(f"[INTEGRATION] Erro no callback de mudança: {e}")
            self.config_middleware.add_config_change_callback(on_config_change_notify)
            
            # ===== INTEGRAÇÃO NOTIFICAÇÕES + CONFIG =====
            setup_notification_integration()
            
            # ===== CONFIGURAR BACKUP AUTOMÁTICO =====
            
            # Callback para backup após sinais importantes
            def on_trading_signal_backup(signal_data):
                """Backup automático quando sinais importantes são gerados"""
                try:
                    if signal_data.get('confidence', 0) > 80:  # Alta confiança
                        self.backup_service.create_backup(
                            backup_type='high_confidence_signal',
                            include_logs=True
                        )
                except Exception as e:
                    logger.error(f"[INTEGRATION] Erro no backup de sinal: {e}")
            
            # Registrar callback no trading analyzer se possível
            if hasattr(self.trading_analyzer, 'add_signal_callback'):
                self.trading_analyzer.add_signal_callback(on_trading_signal_backup)
            
            # ===== MONITORAMENTO DE SAÚDE DO SISTEMA =====
            
            def monitor_system_health():
                """Monitora saúde geral do sistema"""
                while True:
                    try:
                        time.sleep(300)  # A cada 5 minutos
                        
                        # Verificar saúde dos componentes
                        health_issues = []
                        
                        # Bitcoin Streamer
                        btc_stats = self.bitcoin_streamer.get_stream_statistics()
                        if btc_stats.get('api_errors', 0) > 10:
                            health_issues.append('Bitcoin Streamer: muitos erros de API')
                        
                        # Trading Analyzer
                        trading_status = self.trading_analyzer.get_system_status()
                        if 'error' in trading_status:
                            health_issues.append('Trading Analyzer: erro no sistema')
                        
                        # Config Middleware
                        middleware_status = self.config_middleware.get_middleware_status()
                        if not middleware_status.get('auto_refresh_enabled', True):
                            health_issues.append('Config Middleware: auto-refresh desabilitado')
                        
                        # Trading Signals System
                        if self.signal_manager:
                            try:
                                active_signals = self.signal_manager.get_active_signals('BTC')
                                # Se há muitos sinais ativos pode indicar problema
                                if len(active_signals) > 20:
                                    health_issues.append('Trading Signals: muitos sinais ativos')
                            except Exception as e:
                                health_issues.append(f'Trading Signals: erro - {str(e)[:50]}')
                        
                        # Multi-Timeframe System
                        if self.multi_manager:
                            try:
                                summary = self.multi_manager.get_timeframe_data_summary('BTC')
                                if not summary or all(info['data_points'] == 0 for info in summary.values()):
                                    health_issues.append('Multi-Timeframe: sem dados')
                            except Exception as e:
                                health_issues.append(f'Multi-Timeframe: erro - {str(e)[:50]}')
                        
                        # Enviar notificação se houver problemas
                        if health_issues:
                            self.notification_service.send_notification(
                                'SYSTEM_HEALTH',
                                f'Problemas de Saúde Detectados ({len(health_issues)})',
                                'Sistema apresenta alguns problemas que precisam de atenção',
                                {'issues': health_issues},
                                'high'
                            )
                    
                    except Exception as e:
                        logger.error(f"[INTEGRATION] Erro no monitor de saúde: {e}")
            
            # Iniciar monitor em thread separada
            health_thread = threading.Thread(target=monitor_system_health, daemon=True)
            health_thread.start()
            
            logger.info("[INTEGRATION] Integração entre sistemas configurada ✅")
            
        except Exception as e:
            logger.error(f"[INTEGRATION] Erro na configuração de integração: {e}")
    
    def _calculate_config_changes(self, old_config, new_config):
        """Calcula mudanças entre configurações"""
        changes = []
        
        def compare_dicts(old_dict, new_dict, path=""):
            for key, new_value in new_dict.items():
                current_path = f"{path}.{key}" if path else key
                
                if key not in old_dict:
                    changes.append(f"Adicionado {current_path}")
                elif isinstance(new_value, dict) and isinstance(old_dict[key], dict):
                    compare_dicts(old_dict[key], new_value, current_path)
                elif old_dict[key] != new_value:
                    changes.append(f"Alterado {current_path}")
        
        compare_dicts(old_config, new_config)
        return changes
        
    def _feed_trading_analyzer_debounced(self, bitcoin_data: BitcoinData):
        """
        A debounced callback function to feed Bitcoin data to the trading analyzer.
        Agora com integração do Signal Monitor.
        """
        current_time = time.time()
    
        if current_time - self.last_trading_update < self.trading_update_interval:
            logger.debug("[CTRL] Debouncing trading analyzer update.")
            return
    
        try:
            self.trading_analyzer.add_price_data(
                 timestamp=bitcoin_data.timestamp,
                 price=bitcoin_data.price,
                 volume=bitcoin_data.volume_24h
            )
            self.last_trading_update = current_time
            logger.debug(f"[CTRL] Trading analyzer atualizado com preço: ${bitcoin_data.price:.2f}")
        
            # ===== NOVO: VERIFICAR SE PRECISA LIMPAR DUPLICADOS =====
            # Fazer isso ocasionalmente para manter sistema limpo
            if current_time % 300 < self.trading_update_interval:  # A cada 5 minutos
                self.trading_analyzer.cleanup_duplicate_signals()
        
        except Exception as e:
           logger.error(f"[CTRL] Erro ao alimentar trading analyzer: {e}")


    def setup_routes(self):
        """
        Registers all Flask blueprints containing the application's routes.
        """
        logger.info("[CTRL] Registrando blueprints...")
        
        self.app.register_blueprint(main_bp)
        self.app.register_blueprint(bitcoin_bp)
        self.app.register_blueprint(trading_bp)
        self.app.register_blueprint(settings_bp)
        
        # Trading Signals Blueprint (se disponível)
        if TRADING_SIGNALS_AVAILABLE:
            self.app.register_blueprint(signals_bp)
            logger.info("[CTRL] Trading Signals blueprint registrado")
        
        # Multi-Asset Routes (se disponíveis)
        if MULTI_ASSET_ROUTES_AVAILABLE:
            self.app.register_blueprint(multi_asset_bp)
            logger.info("[CTRL] Multi-Asset blueprint registrado")

        # ===== REGISTRAR ROTAS MULTI-TIMEFRAME =====
        if MULTI_TIMEFRAME_AVAILABLE and self.multi_adapter:
            try:
                setup_multi_strategy_routes(self.app, self.multi_adapter)
                logger.info("[CTRL] Multi-Timeframe routes registradas ✅")
            except Exception as e:
                logger.error(f"[CTRL] Erro ao registrar rotas Multi-Timeframe: {e}")

        # ===== NOVAS ROTAS PARA SISTEMAS COMPLETOS =====
        
        @self.app.route('/api/system/health')
        def get_system_health():
            """Status completo de saúde do sistema"""
            try:
                health_data = {
                    'timestamp': datetime.now().isoformat(),
                    'overall_status': 'healthy',
                    'components': {},
                    'alerts': [],
                    'statistics': {}
                }
                
                # Bitcoin Streamer
                btc_stats = self.bitcoin_streamer.get_stream_statistics()
                health_data['components']['bitcoin_streamer'] = {
                    'status': 'running' if btc_stats['is_running'] else 'stopped',
                    'errors': btc_stats.get('api_errors', 0),
                    'data_points': btc_stats.get('total_data_points', 0)
                }
                
                # ===== NOVO: SIGNAL MONITOR STATUS =====
                if hasattr(self.trading_analyzer, 'signal_monitor') and self.trading_analyzer.signal_monitor:
                    monitor_stats = self.trading_analyzer.get_monitor_status()
                    health_data['components']['signal_monitor'] = {
                        'status': 'running' if monitor_stats.get('is_running', False) else 'stopped',
                        'check_interval': monitor_stats.get('check_interval', 0),
                        'tracked_signals': monitor_stats.get('tracked_signals_count', 0),
                        'active_signals': monitor_stats.get('active_signals_in_analyzer', 0)
                    }
                    
                    # Adicionar alerta se monitor parado
                    if not monitor_stats.get('is_running', False):
                        health_data['alerts'].append('Signal Monitor está parado')
                
                # Trading Analyzer (modificar o existente)
                trading_status = self.trading_analyzer.get_system_status()
                health_data['components']['trading_analyzer'] = {
                    'status': 'active' if 'error' not in trading_status else 'error',
                    'active_signals': len([s for s in self.trading_analyzer.signals if s.get('status') == 'ACTIVE']),
                    'total_signals': len(self.trading_analyzer.signals),
                    'analysis_count': trading_status.get('system_info', {}).get('total_analysis', 0),
                    'signal_monitor_active': trading_status.get('system_info', {}).get('signal_monitor_running', False)
                }
                
                # Config Middleware
                middleware_status = self.config_middleware.get_middleware_status()
                health_data['components']['config_middleware'] = {
                    'status': 'active',
                    'auto_refresh': middleware_status.get('auto_refresh_enabled', False),
                    'callbacks': middleware_status.get('callbacks_registered', 0)
                }
                
                # Notification Service
                notif_stats = self.notification_service.get_notification_stats()
                health_data['components']['notifications'] = {
                    'status': 'active',
                    'total_sent': notif_stats.get('total_notifications', 0),
                    'recent_count': len(self.notification_service.get_notification_history(10))
                }
                
                # Backup Service
                backup_stats = self.backup_service.get_backup_stats()
                health_data['components']['backup_service'] = {
                    'status': 'running' if backup_stats['service_running'] else 'stopped',
                    'total_backups': backup_stats['total_backups'],
                    'success_rate': backup_stats['success_rate']
                }
                
                # Trading Signals System
                if self.signal_manager:
                    try:
                        active_signals = self.signal_manager.get_active_signals('BTC')
                        stats = self.signal_manager.get_signal_stats()
                        
                        health_data['components']['trading_signals'] = {
                            'status': 'active',
                            'active_signals': len(active_signals),
                            'total_signals': stats.get('total_signals', 0),
                            'success_rate': stats.get('success_rate', 0)
                        }
                    except Exception as e:
                        health_data['components']['trading_signals'] = {
                            'status': 'error',
                            'error': str(e)
                        }
                
                # Multi-Timeframe System
                if self.multi_manager:
                    try:
                        data_summary = self.multi_manager.get_timeframe_data_summary('BTC')
                        total_data_points = sum(info['data_points'] for info in data_summary.values())
                        
                        health_data['components']['multi_timeframe'] = {
                            'status': 'active' if total_data_points > 0 else 'no_data',
                            'timeframes_active': len([tf for tf, info in data_summary.items() if info['data_points'] > 0]),
                            'total_data_points': total_data_points,
                            'timeframes': data_summary
                        }
                    except Exception as e:
                        health_data['components']['multi_timeframe'] = {
                            'status': 'error',
                            'error': str(e)
                        }
                
                # Multi-Asset (se disponível)
                if self.multi_asset_manager:
                    multi_health = self.multi_asset_manager.get_system_health()
                    health_data['components']['multi_asset'] = {
                        'status': multi_health.get('overall_status', 'unknown'),
                        'active_streamers': multi_health.get('summary', {}).get('active_streamers', 0)
                    }
                
                # Determinar status geral
                component_statuses = [comp.get('status', 'unknown') for comp in health_data['components'].values()]
                
                if any('error' in status for status in component_statuses):
                    health_data['overall_status'] = 'degraded'
                elif any('stopped' in status for status in component_statuses):
                    health_data['overall_status'] = 'partial'
                
                return jsonify(health_data)
                
            except Exception as e:
                logger.error(f"[SYSTEM] Erro ao obter saúde do sistema: {e}")
                return jsonify({'error': str(e)}), 500

        # ===== NOVAS ROTAS PARA SIGNAL MONITOR =====
        
        @self.app.route('/api/signals/monitor/status')
        def get_signal_monitor_status():
            """Status do Signal Monitor"""
            try:
                if hasattr(self.trading_analyzer, 'get_monitor_status'):
                    status = self.trading_analyzer.get_monitor_status()
                    return jsonify({
                        'success': True,
                        'monitor_status': status
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Signal Monitor não disponível'
                    })
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/signals/force-check', methods=['POST'])
        def force_signal_check():
            """Força verificação dos sinais"""
            try:
                if hasattr(self.trading_analyzer, 'force_signal_check'):
                    self.trading_analyzer.force_signal_check()
                    return jsonify({
                        'success': True,
                        'message': 'Verificação de sinais forçada'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Signal Monitor não disponível'
                    })
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/signals/cleanup-duplicates', methods=['POST'])
        def cleanup_duplicates():
            """Remove sinais duplicados"""
            try:
                if hasattr(self.trading_analyzer, 'cleanup_duplicate_signals'):
                    self.trading_analyzer.cleanup_duplicate_signals()
                    return jsonify({
                        'success': True,
                        'message': 'Sinais duplicados removidos'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Função de limpeza não disponível'
                    })
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/signals/dashboard-data')
        def get_signals_dashboard_data():
            """Dados consolidados para o dashboard"""
            try:
                # Obter análise completa
                analysis = self.trading_analyzer.get_comprehensive_analysis()
                
                # Obter status do monitor
                monitor_status = {}
                if hasattr(self.trading_analyzer, 'get_monitor_status'):
                    monitor_status = self.trading_analyzer.get_monitor_status()
                
                # Dados consolidados
                dashboard_data = {
                    'current_price': analysis.get('current_price', 0),
                    'active_signals': analysis.get('active_signals', []),
                    'technical_indicators': analysis.get('technical_indicators', {}),
                    'signal_analysis': analysis.get('signal_analysis', {}),
                    'performance_summary': analysis.get('performance_summary', {}),
                    'system_health': analysis.get('system_health', {}),
                    'monitor_status': monitor_status,
                    'timestamp': datetime.now().isoformat()
                }
                
                return jsonify({
                    'success': True,
                    'data': dashboard_data
                })
                
            except Exception as e:
                logger.error(f"Error getting dashboard data: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/test-signal-monitor')
        def test_signal_monitor():
            """Testa o Signal Monitor"""
            try:
                if not hasattr(self.trading_analyzer, 'signal_monitor') or not self.trading_analyzer.signal_monitor:
                    return jsonify({
                        'status': 'error',
                        'message': 'Signal Monitor não disponível'
                    })
                
                # Obter estatísticas do monitor
                monitor_stats = self.trading_analyzer.get_monitor_status()
                
                # Forçar verificação de teste
                self.trading_analyzer.force_signal_check()
                
                # Obter sinais ativos
                analysis = self.trading_analyzer.get_comprehensive_analysis()
                active_signals = analysis.get('active_signals', [])
                
                return jsonify({
                    'status': 'success',
                    'message': 'Signal Monitor funcionando!',
                    'test_result': {
                        'monitor_running': monitor_stats.get('is_running', False),
                        'check_interval': monitor_stats.get('check_interval', 0),
                        'active_signals_count': len(active_signals),
                        'tracked_signals': monitor_stats.get('tracked_signals_count', 0),
                        'last_cleanup': monitor_stats.get('last_cleanup'),
                        'signals_in_memory': monitor_stats.get('total_signals_in_analyzer', 0)
                    }
                })
                
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': f'Erro no teste: {str(e)}'
                })

        # ===== NOVAS ROTAS TRADING SIGNALS =====
        
        @self.app.route('/api/trading/analyze-and-signal', methods=['POST'])
        def analyze_and_generate_signal():
            """
            Endpoint para receber análise técnica e gerar sinais
            Integra com sistema existente de análise
            """
            if not self.signal_generator:
                return jsonify({'error': 'Sistema de sinais não disponível'}), 503
            
            try:
                data = request.get_json()
                
                asset_symbol = data.get('asset_symbol', 'BTC')
                current_price = data.get('current_price', 0)
                technical_analysis = data.get('technical_analysis', {})
                pattern_type = data.get('pattern_type')
                
                if not current_price or not technical_analysis:
                    return jsonify({
                        'success': False,
                        'error': 'Missing current_price or technical_analysis'
                    }), 400
                
                # Gerar sinal usando o novo sistema
                signal = self.signal_generator.generate_signal_from_analysis(
                    asset_symbol=asset_symbol,
                    technical_analysis=technical_analysis,
                    current_price=current_price,
                    pattern_type=pattern_type
                )
                
                if signal:
                    return jsonify({
                        'success': True,
                        'message': f'Signal generated for {asset_symbol}',
                        'signal': signal.to_dict()
                    })
                else:
                    return jsonify({
                        'success': True,
                        'message': 'No signal generated (conditions not met)',
                        'signal': None
                    })
            
            except Exception as e:
                logger.error(f"Error in analyze_and_signal: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        # ===== ROTAS DE API PARA SIGNALS DASHBOARD =====
        
        @self.app.route('/api/signals/active')
        def get_active_signals():
            """Retorna sinais ativos"""
            if not self.signal_manager:
                return jsonify({'error': 'Sistema de sinais não disponível'}), 503
            
            try:
                asset = request.args.get('asset', 'BTC')
                active_signals = self.signal_manager.get_active_signals(asset)
                
                return jsonify({
                    'success': True,
                    'data': [signal.to_dict() for signal in active_signals],
                    'count': len(active_signals)
                })
                
            except Exception as e:
                logger.error(f"Error getting active signals: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/signals/recent')
        def get_recent_signals():
            """Retorna sinais recentes"""
            if not self.signal_manager:
                return jsonify({'error': 'Sistema de sinais não disponível'}), 503
            
            try:
                limit = request.args.get('limit', 20, type=int)
                asset = request.args.get('asset')
                
                recent_signals = self.signal_manager.get_recent_signals(limit, asset)
                
                return jsonify({
                    'success': True,
                    'data': [signal.to_dict() for signal in recent_signals],
                    'count': len(recent_signals)
                })
                
            except Exception as e:
                logger.error(f"Error getting recent signals: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/signals/stats')
        def get_signals_statistics():
            """Retorna estatísticas dos sinais"""
            if not self.signal_manager:
                return jsonify({'error': 'Sistema de sinais não disponível'}), 503
            
            try:
                days = request.args.get('days', 30, type=int)
                asset = request.args.get('asset')
                
                stats = self.signal_manager.get_signal_statistics(days, asset)
                
                return jsonify({
                    'success': True,
                    'data': stats
                })
                
            except Exception as e:
                logger.error(f"Error getting signal statistics: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/signals/generate-test', methods=['POST'])
        def generate_test_signal():
            """Gera sinal de teste"""
            if not self.signal_generator:
                return jsonify({'error': 'Sistema de sinais não disponível'}), 503
            
            try:
                data = request.get_json() or {}
                asset = data.get('asset', 'BTC')
                signal_type = data.get('type', 'BUY')
                
                # Simular análise técnica para teste
                test_analysis = {
                    'RSI': 35 if signal_type == 'BUY' else 75,
                    'MACD': 0.125 if signal_type == 'BUY' else -0.125,
                    'Volume_Ratio': 1.8,
                    'Trend': 'BULLISH' if signal_type == 'BUY' else 'BEARISH'
                }
                
                # Obter preço atual
                current_price = self.signal_generator._fetch_current_price(asset)
                if not current_price:
                    current_price = 67543.21  # Preço de fallback
                
                # Gerar sinal
                signal = self.signal_generator.generate_signal_from_analysis(
                    asset_symbol=asset,
                    technical_analysis=test_analysis,
                    current_price=current_price,
                    pattern_type='TEST_PATTERN'
                )
                
                if signal:
                    return jsonify({
                        'success': True,
                        'message': f'Sinal de teste {signal_type} gerado para {asset}',
                        'signal': signal.to_dict()
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Não foi possível gerar sinal de teste'
                    })
                
            except Exception as e:
                logger.error(f"Error generating test signal: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/signals/cleanup', methods=['POST'])
        def cleanup_old_signals():
            """Remove sinais antigos"""
            if not self.signal_manager:
                return jsonify({'error': 'Sistema de sinais não disponível'}), 503
            
            try:
                data = request.get_json() or {}
                days = data.get('days', 30)
                
                removed_count = self.signal_manager.cleanup_old_signals(days)
                
                return jsonify({
                    'success': True,
                    'message': f'{removed_count} sinais antigos removidos',
                    'removed_count': removed_count
                })
                
            except Exception as e:
                logger.error(f"Error cleaning up signals: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
            
        @self.app.route('/api/trading/update-signals-price', methods=['POST'])
        def update_signals_with_new_price():
            """
            Endpoint para sistema de streaming atualizar preços dos sinais
            """
            if not self.signal_manager:
                return jsonify({'error': 'Sistema de sinais não disponível'}), 503
            
            try:
                data = request.get_json()
                
                asset_symbol = data.get('asset_symbol', 'BTC')
                current_price = data.get('current_price', 0)
                
                if not current_price:
                    return jsonify({
                        'success': False,
                        'error': 'Missing current_price'
                    }), 400
                
                # Atualizar sinais com novo preço
                self.signal_manager.update_signals_with_price(asset_symbol, current_price)
                
                # Retornar sinais ativos atualizados
                active_signals = self.signal_manager.get_active_signals(asset_symbol)
                
                return jsonify({
                    'success': True,
                    'message': f'Signals updated for {asset_symbol}',
                    'active_signals': [s.to_dict() for s in active_signals],
                    'updated_count': len(active_signals)
                })
            
            except Exception as e:
                logger.error(f"Error updating signals price: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        # ===== WEBHOOK PARA INTEGRAÇÃO EXTERNA =====

        @self.app.route('/webhook/trading-signal', methods=['POST'])
        def receive_external_signal():
            """
            Webhook para receber sinais de sistemas externos
            """
            if not self.signal_manager:
                return jsonify({'error': 'Sistema de sinais não disponível'}), 503
                
            try:
                data = request.get_json()
                
                # Validar dados obrigatórios
                required_fields = ['asset_symbol', 'signal_type', 'entry_price', 'confidence']
                for field in required_fields:
                    if field not in data:
                        return jsonify({
                            'success': False,
                            'error': f'Missing required field: {field}'
                        }), 400
                
                # Criar sinal
                signal = TradingSignal(
                    asset_symbol=data['asset_symbol'],
                    signal_type=SignalType(data['signal_type'].upper()),
                    source=SignalSource.MANUAL,
                    pattern_type=data.get('pattern_type'),
                    entry_price=data['entry_price'],
                    current_price=data['entry_price'],
                    target_1=data.get('target_1', data['entry_price'] * 1.02),
                    target_2=data.get('target_2', data['entry_price'] * 1.035),
                    target_3=data.get('target_3', data['entry_price'] * 1.05),
                    stop_loss=data.get('stop_loss', data['entry_price'] * 0.98),
                    confidence=data['confidence'],
                    reasons=data.get('reasons', ['External signal']),
                    technical_indicators=data.get('technical_indicators', {}),
                    volume_confirmation=data.get('volume_confirmation', False),
                    risk_reward_ratio=data.get('risk_reward_ratio', 2.0)
                )
                
                created_signal = self.signal_manager.create_signal(signal)
                
                if created_signal:
                    return jsonify({
                        'success': True,
                        'message': 'External signal received and created',
                        'signal_id': created_signal.id
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Signal not created (duplicate or validation failed)'
                    })
            
            except Exception as e:
                logger.error(f"Error receiving external signal: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        # ===== NOVA ROTA: DASHBOARD MULTI-TIMEFRAME =====
        @self.app.route('/multi-dashboard')
        def multi_strategy_dashboard():
            """Dashboard Multi-Estratégias"""
            if not MULTI_TIMEFRAME_AVAILABLE:
                return jsonify({'error': 'Sistema Multi-Timeframe não disponível'}), 503
            return render_template('multi_strategy_dashboard.html')

        @self.app.route('/dashboard-multi')  # Rota alternativa
        def dashboard_multi():
            """Rota alternativa para dashboard"""
            return redirect('/multi-dashboard')

        # ===== NOVA ROTA: DASHBOARD TRADING SIGNALS =====
        @self.app.route('/signals')
        def signals_page():
            """Página dedicada aos sinais de trading"""
            if not TRADING_SIGNALS_AVAILABLE:
                return jsonify({'error': 'Sistema Trading Signals não disponível'}), 503
            return render_template('signals_dashboard.html')

        # ===== NOVA ROTA: DASHBOARD INTEGRADO =====
        @self.app.route('/integrated-dashboard')
        def integrated_dashboard():
            """Dashboard integrado com todos os sistemas"""
            return render_template('integrated_dashboard.html')

        # ===== NOVA ROTA: TESTE MULTI-TIMEFRAME =====
        @self.app.route('/test-multi')
        def test_multi_integration():
            """Testa integração multi-timeframe"""
            
            if not self.multi_adapter:
                return jsonify({
                    'status': 'error',
                    'message': 'Sistema multi-timeframe não inicializado'
                })
            
            # Teste com dados simulados
            test_data = {
                'price': 67543.21,
                'volume': 1.5,
                'timestamp': datetime.now()
            }
            
            try:
                result = self.multi_adapter.on_price_update('BTC', test_data)
                
                return jsonify({
                    'status': 'success',
                    'message': 'Sistema multi-timeframe funcionando!',
                    'test_result': {
                        'asset': result.get('asset'),
                        'timeframes_analyzed': result.get('timeframes_analyzed'),
                        'signals_generated': len(result.get('signals', {})),
                        'new_signals': len(result.get('new_signals', {}))
                    }
                })
                
            except Exception as e:
                return jsonify({
                    'status': 'error', 
                    'message': f'Erro no teste: {str(e)}'
                })

        # ===== NOVA ROTA: TESTE TRADING SIGNALS =====
        @self.app.route('/test-signals')
        def test_signals_integration():
            """Testa integração trading signals"""
            
            if not self.signal_generator:
                return jsonify({
                    'status': 'error',
                    'message': 'Sistema trading signals não inicializado'
                })
            
            try:
                # Simular análise técnica
                test_analysis = {
                    'RSI': 35,  # Oversold
                    'MACD': 0.125,
                    'MACD_Signal': 0.100,
                    'Volume_Ratio': 1.8,
                    'Trend': 'BULLISH'
                }
                
                # Tentar gerar sinal
                signal = self.signal_generator.generate_signal_from_analysis(
                    asset_symbol='BTC',
                    technical_analysis=test_analysis,
                    current_price=67543.21
                )
                
                if signal:
                    return jsonify({
                        'status': 'success',
                        'message': 'Sistema trading signals funcionando!',
                        'test_result': {
                            'signal_generated': True,
                            'signal_type': signal.signal_type.value,
                            'confidence': signal.confidence,
                            'entry_price': signal.entry_price,
                            'targets': [signal.target_1, signal.target_2, signal.target_3],
                            'stop_loss': signal.stop_loss
                        }
                    })
                else:
                    return jsonify({
                        'status': 'success',
                        'message': 'Sistema funcionando, mas nenhum sinal gerado',
                        'test_result': {
                            'signal_generated': False,
                            'reason': 'Condições não atendidas'
                        }
                    })
                
            except Exception as e:
                return jsonify({
                    'status': 'error', 
                    'message': f'Erro no teste: {str(e)}'
                })
        
        @self.app.route('/api/system/notifications', methods=['GET', 'POST'])
        def handle_notifications():
            """Endpoint para gerenciar notificações"""
            if request.method == 'GET':
                # Listar notificações recentes
                limit = request.args.get('limit', 20, type=int)
                history = self.notification_service.get_notification_history(limit)
                stats = self.notification_service.get_notification_stats()
                
                return jsonify({
                    'notifications': history,
                    'statistics': stats,
                    'total_count': len(history)
                })
            
            elif request.method == 'POST':
                # Enviar notificação manual
                data = request.get_json()
                
                if not data or 'title' not in data or 'message' not in data:
                    return jsonify({'error': 'título e mensagem são obrigatórios'}), 400
                
                result = self.notification_service.send_notification(
                    notification_type=data.get('type', 'MANUAL'),
                    title=data['title'],
                    message=data['message'],
                    details=data.get('details'),
                    priority=data.get('priority', 'medium')
                )
                
                return jsonify(result)
        
        @self.app.route('/api/system/backup', methods=['GET', 'POST'])
        def handle_backup():
            """Endpoint para gerenciar backups"""
            if request.method == 'GET':
                # Listar backups
                backup_type = request.args.get('type')
                limit = request.args.get('limit', 20, type=int)
                
                backups = self.backup_service.list_backups(backup_type, limit)
                stats = self.backup_service.get_backup_stats()
                
                return jsonify({
                    'backups': backups,
                    'statistics': stats,
                    'total_count': len(backups)
                })
            
            elif request.method == 'POST':
                # Criar backup manual
                data = request.get_json() or {}
                
                result = self.backup_service.create_backup(
                    backup_type=data.get('backup_type', 'manual'),
                    include_databases=data.get('include_databases', True),
                    include_configs=data.get('include_configs', True),
                    include_logs=data.get('include_logs', False),
                    auto_cleanup=data.get('auto_cleanup', False)
                )
                
                return jsonify(result)
        
        @self.app.route('/api/system/backup/<backup_id>/restore', methods=['POST'])
        def restore_backup(backup_id):
            """Restaurar backup específico"""
            try:
                data = request.get_json() or {}
                restore_path = data.get('restore_path')
                
                result = self.backup_service.restore_backup(backup_id, restore_path)
                return jsonify(result)
                
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/system/config-middleware/status')
        def get_middleware_status():
            """Status detalhado do middleware de configuração"""
            try:
                status = self.config_middleware.get_middleware_status()
                history = self.config_middleware.get_application_history(10)
                cached_config = self.config_middleware.get_cached_config()
                
                return jsonify({
                    'middleware_status': status,
                    'recent_applications': history,
                    'cached_config_size': len(str(cached_config)),
                    'integration_healthy': True
                })
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/system/config-middleware/sync', methods=['POST'])
        def force_config_sync():
            """Força sincronização do middleware"""
            try:
                result = self.config_middleware.force_config_sync()
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        # ===== ROTAS ORIGINAIS MANTIDAS =====
        @self.app.route('/settings')
        def settings_page():
            """Renders the settings page"""
            return render_template('settings.html')

        # Global API routes
        @self.app.route('/api/bitcoin/current')
        def get_current_bitcoin_price():
            try:
                recent_bitcoin = self.bitcoin_streamer.get_recent_data(1)
                if recent_bitcoin:
                    return jsonify({'current_price': recent_bitcoin[0].price, 'timestamp': recent_bitcoin[0].timestamp.isoformat()})
                else:
                    return jsonify({'message': 'No current Bitcoin data available'}), 404
            except Exception as e:
                logger.error(f"Erro ao obter preço atual do Bitcoin: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/bitcoin/start-stream', methods=['POST'])
        def start_bitcoin_stream():
            try:
                self.bitcoin_streamer.start_streaming()
                logger.info("[OK] Bitcoin streaming iniciado via API.")
                
                # Enviar notificação
                self.notification_service.send_notification(
                    'SYSTEM_STATUS',
                    'Bitcoin Streaming Iniciado',
                    'O streaming de dados do Bitcoin foi iniciado com sucesso',
                    {'interval': f"{self.bitcoin_streamer.fetch_interval}s"}
                )
                
                return jsonify({'status': 'started', 'message': 'Bitcoin streaming iniciado (5 min intervals)'})
            except Exception as e:
                logger.error(f"Erro ao iniciar streaming: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500

        @self.app.route('/api/bitcoin/stop-stream', methods=['POST'])
        def stop_bitcoin_stream():
            try:
                self.bitcoin_streamer.stop_streaming()
                logger.info("[STOP] Bitcoin streaming parado via API.")
                
                # Enviar notificação
                self.notification_service.send_notification(
                    'SYSTEM_STATUS',
                    'Bitcoin Streaming Parado',
                    'O streaming de dados do Bitcoin foi parado',
                    priority='low'
                )
                
                return jsonify({'status': 'stopped', 'message': 'Bitcoin streaming parado'})
            except Exception as e:
                logger.error(f"Erro ao parar streaming: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500

        @self.app.route('/api/bitcoin/status')
        def get_bitcoin_status():
            try:
                stats = self.bitcoin_streamer.get_stream_statistics()
                return jsonify(stats)
            except Exception as e:
                logger.error(f"Erro ao obter status: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/bitcoin/metrics')
        def get_bitcoin_metrics():
            try:
                time_window_minutes = request.args.get('time_window_minutes', 30, type=int)
                metrics = self.bitcoin_analytics.get_real_time_metrics(time_window_minutes)
                return jsonify(metrics)
            except Exception as e:
                logger.error(f"Erro ao obter métricas: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/bitcoin/api/recent-data')
        def get_bitcoin_recent_data():
            try:
                limit = request.args.get('limit', 50, type=int)
                limit = min(limit, 1000)
                recent_data = self.bitcoin_streamer.get_recent_data(limit)
                return jsonify([data.to_dict() for data in recent_data])
            except Exception as e:
                logger.error(f"Erro ao obter dados recentes: {e}")
                return jsonify({'error': str(e)}), 500

        # Multi-Asset Global Routes (se disponível)
        if self.multi_asset_manager:
            @self.app.route('/api/multi-asset/overview')
            def get_multi_asset_overview():
                try:
                    overview = self.multi_asset_manager.get_overview_data()
                    return jsonify(overview)
                except Exception as e:
                    logger.error(f"Erro ao obter overview multi-asset: {e}")
                    return jsonify({'error': str(e)}), 500

            @self.app.route('/api/multi-asset/health')
            def get_multi_asset_health():
                try:
                    health = self.multi_asset_manager.get_system_health()
                    return jsonify(health)
                except Exception as e:
                    logger.error(f"Erro ao obter saúde do sistema: {e}")
                    return jsonify({'error': str(e)}), 500

            @self.app.route('/api/multi-asset/start', methods=['POST'])
            def start_multi_asset_streaming():
                try:
                    assets = request.json.get('assets') if request.json else None
                    self.multi_asset_manager.start_streaming(assets)
                    assets_str = ', '.join(assets) if assets else 'todos os assets'
                    logger.info(f"[OK] Multi-asset streaming iniciado para: {assets_str}")
                    
                    # Enviar notificação
                    self.notification_service.send_notification(
                        'SYSTEM_STATUS',
                        'Multi-Asset Streaming Iniciado',
                        f'Streaming iniciado para: {assets_str}',
                        {'assets': assets or app_config.get_supported_asset_symbols()}
                    )
                    
                    return jsonify({
                        'status': 'started', 
                        'message': f'Multi-asset streaming iniciado para: {assets_str}',
                        'assets': assets or app_config.get_supported_asset_symbols()
                    })
                except Exception as e:
                    logger.error(f"Erro ao iniciar multi-asset streaming: {e}")
                    return jsonify({'status': 'error', 'message': str(e)}), 500

            @self.app.route('/api/multi-asset/stop', methods=['POST'])
            def stop_multi_asset_streaming():
                try:
                    assets = request.json.get('assets') if request.json else None
                    self.multi_asset_manager.stop_streaming(assets)
                    assets_str = ', '.join(assets) if assets else 'todos os assets'
                    logger.info(f"[STOP] Multi-asset streaming parado para: {assets_str}")
                    
                    # Enviar notificação
                    self.notification_service.send_notification(
                        'SYSTEM_STATUS',
                        'Multi-Asset Streaming Parado',
                        f'Streaming parado para: {assets_str}',
                        {'assets': assets or app_config.get_supported_asset_symbols()},
                        'low'
                    )
                    
                    return jsonify({
                        'status': 'stopped', 
                        'message': f'Multi-asset streaming parado para: {assets_str}',
                        'assets': assets or app_config.get_supported_asset_symbols()
                    })
                except Exception as e:
                    logger.error(f"Erro ao parar multi-asset streaming: {e}")
                    return jsonify({'status': 'error', 'message': str(e)}), 500

        logger.info("[CTRL] Rotas registradas com sucesso.")

    def setup_error_handlers(self):
        """
        Sets up custom error handlers for Flask application.
        """
        @self.app.errorhandler(404)
        def not_found(error):
            logger.warning(f"404 Not Found: {request.path}")
            return jsonify({'error': 'Endpoint não encontrado', 'path': request.path}), 404
        
        @self.app.errorhandler(500)
        def internal_error(error):
            logger.exception(f"Erro interno do servidor: {error}")
            
            # Enviar notificação sobre erro crítico
            try:
                self.notification_service.send_notification(
                    'SYSTEM_ERROR',
                    'Erro Interno do Servidor',
                    f'Erro 500 detectado: {str(error)}',
                    {'path': request.path, 'method': request.method},
                    'critical'
                )
            except:
                pass
            
            return jsonify({'error': 'Erro interno do servidor', 'message': str(error)}), 500
        
        logger.info("[CTRL] Manipuladores de erro configurados.")
    
    def run(self, debug: bool = False, port: int = 5000, host: str = '0.0.0.0'):
        """
        Starts the Flask development server and initiates all services.
        """
        logger.info("=" * 90)
        logger.info("[START] SISTEMA INTEGRADO TRADING COMPLETO + MULTI-TIMEFRAME + TRADING SIGNALS + SIGNAL MONITOR")
        logger.info("=" * 90)
        logger.info(f"[DATA] Dashboard Principal: http://localhost:{port}")
        logger.info(f"[BTC] Dashboard Bitcoin: http://localhost:{port}/bitcoin")
        logger.info(f"[TRADE] Dashboard Trading: http://localhost:{port}/trading")
        logger.info(f"[SETTINGS] Configurações: http://localhost:{port}/settings")
        logger.info(f"[INTEGRATED] Dashboard Integrado: http://localhost:{port}/integrated-dashboard")
        
        if TRADING_SIGNALS_AVAILABLE:
            logger.info(f"[SIGNALS] Dashboard Trading Signals: http://localhost:{port}/signals")
        
        if MULTI_TIMEFRAME_AVAILABLE:
            logger.info(f"[MULTI-TF] Dashboard Multi-Timeframe: http://localhost:{port}/multi-dashboard")
        
        if self.multi_asset_manager:
            logger.info(f"[MULTI] Dashboard Multi-Asset: http://localhost:{port}/multi-asset")
        
        logger.info("")
        logger.info("[API] APIs PRINCIPAIS:")
        logger.info(f"   - Status Integrado: http://localhost:{port}/api/integrated/status")
        logger.info(f"   - Dashboard Data: http://localhost:{port}/api/integrated/dashboard-data")
        logger.info(f"   - Config Status: http://localhost:{port}/api/integrated/config-status")
        logger.info(f"   - Bitcoin Métricas: http://localhost:{port}/api/bitcoin/metrics")
        logger.info(f"   - Trading Análise: http://localhost:{port}/trading/api/analysis")
        logger.info(f"   - Configurações: http://localhost:{port}/settings/api/get-config")
        
        logger.info("")
        logger.info("[API] NOVAS APIs AVANÇADAS:")
        logger.info(f"   - Saúde do Sistema: http://localhost:{port}/api/system/health")
        logger.info(f"   - Notificações: http://localhost:{port}/api/system/notifications")
        logger.info(f"   - Backups: http://localhost:{port}/api/system/backup")
        logger.info(f"   - Config Middleware: http://localhost:{port}/api/system/config-middleware/status")
        
        # ===== NOVO: ADICIONAR URLS DO SIGNAL MONITOR =====
        logger.info("")
        logger.info("[API] SIGNAL MONITOR:")
        logger.info(f"   - Signal Monitor Status: http://localhost:{port}/api/signals/monitor/status")
        logger.info(f"   - Test Signal Monitor: http://localhost:{port}/test-signal-monitor")
        logger.info(f"   - Force Signal Check: http://localhost:{port}/api/signals/force-check")
        logger.info(f"   - Cleanup Duplicates: http://localhost:{port}/api/signals/cleanup-duplicates")
        logger.info(f"   - Dashboard Data: http://localhost:{port}/api/signals/dashboard-data")
        
        if TRADING_SIGNALS_AVAILABLE:
            logger.info("")
            logger.info("[API] TRADING SIGNALS:")
            logger.info(f"   - Análise e Sinal: http://localhost:{port}/api/trading/analyze-and-signal")
            logger.info(f"   - Atualizar Preços: http://localhost:{port}/api/trading/update-signals-price")
            logger.info(f"   - Webhook Externo: http://localhost:{port}/webhook/trading-signal")
            logger.info(f"   - Sinais Ativos: http://localhost:{port}/api/signals/active")
            logger.info(f"   - Teste Signals: http://localhost:{port}/test-signals")
        
        if MULTI_TIMEFRAME_AVAILABLE:
            logger.info("")
            logger.info("[API] MULTI-TIMEFRAME:")
            logger.info(f"   - Multi-Timeframe Signals: http://localhost:{port}/api/multi/signals/BTC")
            logger.info(f"   - Multi-Timeframe Test: http://localhost:{port}/test-multi")
        
        if self.multi_asset_manager:
            logger.info("")
            logger.info("[API] MULTI-ASSET:")
            logger.info(f"   - Multi-Asset Overview: http://localhost:{port}/api/multi-asset/overview")
            logger.info(f"   - Multi-Asset Health: http://localhost:{port}/api/multi-asset/health")
        
        logger.info("")
        logger.info("[FEATURES] SISTEMAS HABILITADOS:")
        logger.info("   ✅ Bitcoin Streaming (Binance API)")
        logger.info("   ✅ Enhanced Trading Analyzer")
        logger.info("   ✅ Signal Monitor (Monitoramento Automático)")
        logger.info("   ✅ Dynamic Configuration Manager")
        logger.info("   ✅ Configuration Middleware")
        logger.info("   ✅ Notification System (Email/Webhook/Slack/Discord/Telegram)")
        logger.info("   ✅ Automated Backup System")
        logger.info("   ✅ Real-time Config Validation")
        logger.info("   ✅ Config History & Rollback")
        logger.info("   ✅ System Health Monitoring")
        logger.info("   ✅ CLI Configuration Tool")
        
        if TRADING_SIGNALS_AVAILABLE:
            logger.info("   ✅ Trading Signals System (Auto-generation + Manual)")
            logger.info("   📊 Features: Signal Generator + Signal Manager + Webhook Integration")
        
        if MULTI_TIMEFRAME_AVAILABLE:
            logger.info("   ✅ Multi-Timeframe Trading System (1m/5m/1h)")
            logger.info("   📊 Estratégias: Scalping + Day Trading + Swing Trading")
        
        if self.multi_asset_manager:
            logger.info("   ✅ Multi-Asset Support (BTC/ETH/SOL)")
            logger.info(f"   📊 Assets Suportados: {', '.join(app_config.get_supported_asset_symbols())}")
        
        logger.info("")
        logger.info("[PERSISTENCE] Persistência habilitada - dados preservados entre sessões")
        logger.info("[MONITORING] Monitoramento automático de saúde ativo")
        logger.info("[BACKUP] Backup automático configurado")
        logger.info("[INTEGRATION] Integração completa entre todos os sistemas")
        logger.info("[SIGNAL-MONITOR] Monitoramento contínuo de sinais em tempo real")
        logger.info("=" * 90)
        
        self.app.debug = debug
        
        try:
            # ===== INICIAR TODOS OS SERVIÇOS =====
            
            # 1. Iniciar serviços de backup
            logger.info("[INIT] Iniciando serviço de backup...")
            
            # 2. Iniciar Bitcoin streaming original
            logger.info("[INIT] Iniciando Bitcoin streamer...")
            self.bitcoin_streamer.start_streaming()

            def background_init():
                time.sleep(5)  # Aguardar Flask
                try:
                    logger.info("[BG] Iniciando backup service...")
                    self.backup_service.start_auto_backup()
        
                    if self.multi_asset_manager and app_config.AUTO_START_STREAM:
                         time.sleep(5)
                         logger.info("[BG] Iniciando Multi-Asset...")
                         self.multi_asset_manager.start_streaming(['BTC', 'ETH', 'SOL'])
                except Exception as e:
                       logger.error(f"[BG] Erro: {e}")

            threading.Thread(target=background_init, daemon=True).start()
            
            # 3. Aplicar configuração inicial via middleware
            logger.info("[INIT] Aplicando configuração inicial...")
            initial_config = self.config_manager.load_config()
            logger.info(f"[CONFIG] {len(initial_config)} itens carregados")
            self.config_middleware.intercept_config_change(
                initial_config, 
                'startup', 
                apply_immediately=True
            )
            
            # 4. Opcionalmente iniciar multi-asset
            if self.multi_asset_manager and app_config.AUTO_START_STREAM:
                logger.info("[INIT] Iniciando Multi-Asset streamers...")
                self.multi_asset_manager.start_streaming(['BTC', 'ETH', 'SOL'])
            
            # 5. Enviar notificação de startup
            components_list = [
                'Bitcoin Streamer', 'Trading Analyzer', 'Signal Monitor', 'Config Manager',
                'Notification Service', 'Backup Service'
            ]
            
            if TRADING_SIGNALS_AVAILABLE:
                components_list.append('Trading Signals System')
            if MULTI_TIMEFRAME_AVAILABLE:
                components_list.append('Multi-Timeframe System')
            if self.multi_asset_manager:
                components_list.append('Multi-Asset Manager')
            
            self.notification_service.send_notification(
                'SYSTEM_STATUS',
                'Sistema de Trading Iniciado',
                'Todos os componentes foram inicializados com sucesso',
                {
                    'version': '2.3.0',
                    'components': components_list,
                    'trading_signals_enabled': TRADING_SIGNALS_AVAILABLE,
                    'multi_timeframe_enabled': MULTI_TIMEFRAME_AVAILABLE,
                    'signal_monitor_enabled': True,
                    'startup_time': datetime.now().isoformat()
                }
            )
            
            logger.info("[READY] ✅ SISTEMA COMPLETO + MULTI-TIMEFRAME + TRADING SIGNALS + SIGNAL MONITOR PRONTO! Iniciando servidor Flask...")
            self.app.run(debug=debug, port=port, host=host, threaded=True)
            
        except KeyboardInterrupt:
            logger.info("[STOP] Aplicação interrompida pelo usuário (Ctrl+C).")
            self.shutdown()
        except Exception as e:
            logger.critical(f"[ERROR] Erro fatal ao iniciar aplicação: {e}")
            logger.critical(f"[ERROR] Traceback: {traceback.format_exc()}")
            
            # Enviar notificação de erro crítico
            try:
                self.notification_service.send_notification(
                    'SYSTEM_ERROR',
                    'Erro Fatal no Sistema',
                    f'Sistema falhou ao iniciar: {str(e)}',
                    {'error_type': type(e).__name__, 'traceback': traceback.format_exc()[:500]},
                    'critical'
                )
            except:
                pass
                
            self.shutdown()
            raise
    
    def shutdown(self):
        """
        Performs a graceful shutdown of the application.
        """
        logger.info("[FIX] Finalizando aplicação COMPLETA + SIGNAL MONITOR e salvando estado...")
        
        try:
            # Enviar notificação de shutdown
            try:
                self.notification_service.send_notification(
                    'SYSTEM_STATUS',
                    'Sistema Sendo Finalizado',
                    'Processo de shutdown iniciado - salvando todos os estados',
                    priority='low'
                )
            except:
                pass
            
            # ===== NOVO: PARAR SIGNAL MONITOR =====
            if hasattr(self.trading_analyzer, 'stop_signal_monitoring'):
                logger.info("[SHUTDOWN] Parando Signal Monitor...")
                self.trading_analyzer.stop_signal_monitoring()
            
            # 1. Parar streamers
            if self.bitcoin_streamer.is_running:
                self.bitcoin_streamer.stop_streaming()
            
            if self.multi_asset_manager:
                self.multi_asset_manager.shutdown()
            
            # 2. Salvar estados dos analyzers
            self.bitcoin_processor.force_process_batch()
            
            # ===== FORÇAR VERIFICAÇÃO FINAL DOS SINAIS =====
            if hasattr(self.trading_analyzer, 'force_signal_check'):
                logger.info("[SHUTDOWN] Verificação final dos sinais...")
                self.trading_analyzer.force_signal_check()
            
            self.trading_analyzer.save_analyzer_state()
            
            if self.trading_analyzer.price_history:
                last_price_data = self.trading_analyzer.price_history[-1]
                self.trading_analyzer.save_price_data(
                    last_price_data['timestamp'], 
                    last_price_data['price'], 
                    last_price_data['volume']
                )
            
            # 3. Salvar estado dos sistemas de trading signals
            if self.signal_manager:
                try:
                    # Salvar estado atual dos sinais ativos
                    active_signals = self.signal_manager.get_active_signals('BTC')
                    logger.info(f"[SHUTDOWN] Salvando {len(active_signals)} sinais ativos")
                except Exception as e:
                    logger.error(f"[SHUTDOWN] Erro ao salvar trading signals: {e}")
            
            # 4. Parar serviços avançados
            self.config_middleware.stop_auto_refresh()
            self.backup_service.stop_auto_backup()
            
            # 5. Criar backup final
            logger.info("[SHUTDOWN] Criando backup final...")
            final_backup = self.backup_service.create_backup(
                backup_type='shutdown',
                include_logs=True
            )
            
            if final_backup['success']:
                logger.info(f"[SHUTDOWN] Backup final criado: {final_backup['backup_file']}")
            
            # 6. Salvar configuração final
            final_config = self.config_manager.current_config
            self.config_manager.save_config(final_config, 'shutdown', 'Estado final do sistema')
            
            logger.info("[OK] ✅ Aplicação COMPLETA + SIGNAL MONITOR finalizada com sucesso - estado persistido.")
            
        except Exception as e:
            logger.error(f"[ERROR] Erro durante a finalização da aplicação: {e}")


# ==================== UTILITY FUNCTIONS EXPANDIDAS ====================

def validate_dependencies():
    """
    Checks if all required Python modules are installed.
    """
    logger.info("[VALIDATE] Verificando dependências Python...")
    
    required_modules = ['flask', 'requests', 'schedule', 'sqlite3', 'numpy']
    missing = []
    
    for module_name in required_modules:
        try:
            __import__(module_name)
            logger.debug(f"[VALIDATE] ✅ {module_name}")
        except ImportError:
            missing.append(module_name)
            logger.error(f"[VALIDATE] ❌ {module_name}")
    
    if missing:
        logger.error(f"[ERROR] Dependências em falta: {', '.join(missing)}")
        logger.error("[FIX] Instale com: pip install flask requests schedule numpy")
        return False
    
    logger.info("[OK] Todas as dependências Python estão disponíveis.")
    return True

def check_system_integration():
    """Verifica se todos os sistemas estão integrados corretamente"""
    logger.info("[VALIDATE] Verificando integração dos sistemas...")
    
    try:
        # Testar config manager
        config_manager = DynamicConfigManager()
        test_config = config_manager.load_config()
        assert isinstance(test_config, dict), "Config manager falhou"
        logger.debug("[VALIDATE] ✅ Config Manager")
        
        # Testar middleware
        middleware = ConfigurationMiddleware()
        middleware_status = middleware.get_middleware_status()
        assert isinstance(middleware_status, dict), "Middleware falhou"
        logger.debug("[VALIDATE] ✅ Config Middleware")
        
        # Testar notification service
        notif_service = NotificationService()
        notif_stats = notif_service.get_notification_stats()
        assert isinstance(notif_stats, dict), "Notification service falhou"
        logger.debug("[VALIDATE] ✅ Notification Service")
        
        # Testar backup service
        backup_service = BackupService()
        backup_stats = backup_service.get_backup_stats()
        assert isinstance(backup_stats, dict), "Backup service falhou"
        logger.debug("[VALIDATE] ✅ Backup Service")
        
        # Testar Trading Signals (se disponível)
        if TRADING_SIGNALS_AVAILABLE:
            try:
                # Tentar inicializar sistema de sinais de teste
                test_db_path = ':memory:'
                init_signal_system(test_db_path)
                logger.debug("[VALIDATE] ✅ Trading Signals System")
            except Exception as e:
                logger.warning(f"[VALIDATE] ⚠️ Trading Signals: {e}")
        
        # Testar Multi-Timeframe (se disponível)
        if MULTI_TIMEFRAME_AVAILABLE:
            try:
                multi_manager = MultiTimeframeManager()
                data_summary = multi_manager.get_timeframe_data_summary('BTC')
                assert isinstance(data_summary, dict), "Multi-Timeframe falhou"
                logger.debug("[VALIDATE] ✅ Multi-Timeframe System")
            except Exception as e:
                logger.warning(f"[VALIDATE] ⚠️ Multi-Timeframe: {e}")
        
        logger.info("[OK] Todos os sistemas integrados estão funcionando.")
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Falha na integração dos sistemas: {e}")
        return False

def check_trading_analyzer_initial_load():
    """
    Performs a basic check to ensure the Trading Analyzer can be initialized.
    """
    logger.info("[VALIDATE] Verificando Trading Analyzer...")
    
    try:
        analyzer = EnhancedTradingAnalyzer(db_path=app_config.TRADING_ANALYZER_DB)
        _ = analyzer.get_system_status()
        logger.info("[OK] Trading Analyzer (com persistência) carregado com sucesso.")
        return True
    except Exception as e:
        logger.error(f"[ERROR] Problema com trading_analyzer: {e}")
        logger.error(f"[ERROR] Traceback: {traceback.format_exc()}")
        return False

def create_sample_data():
    """
    Generates and inserts sample Bitcoin data and trading analysis data.
    """
    logger.info("[SAMPLE] Criando dados de exemplo...")
    
    try:
        processor = BitcoinStreamProcessor(db_path=app_config.BITCOIN_STREAM_DB)
        analyzer = EnhancedTradingAnalyzer(db_path=app_config.TRADING_ANALYZER_DB)
        
        base_price = 43000.0
        num_samples = 50
        
        for i in range(num_samples):
            timestamp = datetime.now() - timedelta(minutes=50 - i)
            price = base_price + (i * 10) + ((i * 17) % 100) - 50 
            
            bitcoin_data = BitcoinData(
                timestamp=timestamp,
                price=price,
                volume_24h=1_000_000_000 + (i * 10_000_000),
                market_cap=800_000_000_000 + (i * 5_000_000_000),
                price_change_24h=((price - base_price) / base_price) * 100,
                source='binance'
            )
            
            processor.process_stream_data(bitcoin_data)
            analyzer.add_price_data(timestamp, price, bitcoin_data.volume_24h)
        
        processor.force_process_batch()
        analyzer.save_analyzer_state()
        
        logger.info(f"[OK] {num_samples} registros de exemplo criados e processados.")
        
        analysis = analyzer.get_system_status()
        logger.info(f"[DATA] Trading analyzer inicializado com sucesso.")
        
    except Exception as e:
        logger.error(f"[ERROR] Erro ao criar dados de exemplo: {e}")
        logger.error(f"[ERROR] Traceback: {traceback.format_exc()}")

# ==================== INTEGRAÇÃO AUTOMÁTICA ENTRE SISTEMAS ====================

def integrate_with_existing_analyzer():
    """
    Exemplo de como integrar com sistema existente de análise técnica
    """
    
    # Supondo que você tenha uma função que faz análise técnica
    def get_technical_analysis(asset_symbol: str):
        """
        Função placeholder - substitua pela sua análise técnica real
        """
        # Exemplo de dados que sua análise técnica retornaria
        return {
            'RSI': 45.5,
            'MACD': 0.125,
            'MACD_Signal': 0.100,
            'MACD_Histogram': 0.025,
            'BB_Position': 0.3,
            'Stoch_K': 35.2,
            'Stoch_D': 38.1,
            'SMA_9': 65420.30,
            'SMA_21': 65380.15,
            'Volume_Ratio': 1.8,
            'ATR': 1250.50
        }
    
    # Integração periódica
    def periodic_analysis():
        """
        Função que roda periodicamente para gerar sinais
        """
        for asset in ['BTC', 'ETH', 'SOL']:
            try:
                # Obter análise técnica
                analysis = get_technical_analysis(asset)
                
                # Obter preço atual (integrar com seu sistema)
                if TRADING_SIGNALS_AVAILABLE and signal_generator:
                    current_price = signal_generator._fetch_current_price(asset)
                    
                    if current_price and analysis:
                        # Tentar gerar sinal
                        signal = signal_generator.generate_signal_from_analysis(
                            asset_symbol=asset,
                            technical_analysis=analysis,
                            current_price=current_price
                        )
                        
                        if signal:
                            logger.info(f"Generated signal for {asset}: {signal.signal_type.value}")
            
            except Exception as e:
                logger.error(f"Error in periodic analysis for {asset}: {e}")
    
    # Agendar análise periódica (usando threading ou celery em produção)
    import threading
    import time
    
    def analysis_loop():
        while True:
            try:
                periodic_analysis()
                time.sleep(300)  # A cada 5 minutos
            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")
                time.sleep(60)
    
    # Iniciar thread de análise
    analysis_thread = threading.Thread(target=analysis_loop, daemon=True)
    analysis_thread.start()

# ==================== MAIN APPLICATION ENTRY POINT ====================
def main():
    """
    Main function to run the Complete Bitcoin Trading System application.
    """
    print("[START] Inicializando Sistema Integrado Trading COMPLETO + MULTI-TIMEFRAME + TRADING SIGNALS + SIGNAL MONITOR com Persistência...")
    
    logger.info("[MAIN] Iniciando validações COMPLETAS...")
    
    if not validate_dependencies():
        return 1
    
    if not check_system_integration():
        return 1
    
    logger.info("[MAIN] Inicializando databases...")
    initialize_databases()

    if not check_trading_analyzer_initial_load():
        logger.critical("[ERROR] Falha na verificação inicial do Trading Analyzer. Encerrando.")
        return 1
    
    # Verificar se precisa criar dados de exemplo
    logger.info("[MAIN] Verificando dados existentes...")
    if not os.path.exists(app_config.BITCOIN_STREAM_DB) or os.path.getsize(app_config.BITCOIN_STREAM_DB) == 0:
        logger.info("[SAMPLE] Banco de dados de stream Bitcoin vazio. Criando dados de exemplo...")
        create_sample_data()
    else:
        conn = sqlite3.connect(app_config.BITCOIN_STREAM_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bitcoin_stream")
        count = cursor.fetchone()[0]
        conn.close()
        if count == 0:
            logger.info("[SAMPLE] Banco de dados existe mas está vazio. Criando dados de exemplo...")
            create_sample_data()
        else:
            logger.info(f"[DATA] Banco contém {count} registros. Usando dados existentes.")

    try:
        logger.info("[MAIN] Criando controller COMPLETO + MULTI-TIMEFRAME + TRADING SIGNALS + SIGNAL MONITOR...")
        controller = IntegratedController()
        
        # Iniciar integração automática se disponível
        if TRADING_SIGNALS_AVAILABLE:
            logger.info("[MAIN] Iniciando integração automática...")
            integrate_with_existing_analyzer()
        
        debug_mode = app_config.FLASK_DEBUG_MODE
        port = app_config.FLASK_PORT
        host = app_config.FLASK_HOST
        
        logger.info("[MAIN] Iniciando aplicação COMPLETA + MULTI-TIMEFRAME + TRADING SIGNALS + SIGNAL MONITOR...")
        controller.run(debug=debug_mode, port=port, host=host)
        return 0
        
    except KeyboardInterrupt:
        logger.info("[STOP] Aplicação interrompida pelo usuário.")
        return 0
    except Exception as e:
        logger.critical(f"[ERROR] Erro crítico na execução principal: {e}")
        logger.critical(f"[ERROR] Traceback: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
	