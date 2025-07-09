# app_fixed.py - Versão COMPLETA com todos os sistemas integrados

import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta
import traceback

print("[START] Inicializando Sistema Integrado Multi-Asset Trading com Persistência COMPLETA...")

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

# ==================== INTEGRATED CONTROLLER COMPLETO ====================
class IntegratedController:
    """
    Controlador principal COMPLETO da aplicação, responsável por inicializar
    todos os componentes incluindo os novos sistemas de configuração, 
    notificações e backup.
    """
    def __init__(self):
        """
        Initializes the Flask application and all integrated components.
        """
        logger.info("[CTRL] Inicializando IntegratedController COMPLETO...")
        
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
        
        logger.info("[CTRL] Configurando routes e error handlers...")
        self.setup_routes()
        self.setup_error_handlers()
        
        logger.info("[CTRL] IntegratedController COMPLETO inicializado com sucesso ✅")
    
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
                            keyword in c.lower() for keyword in ['trading', 'signal', 'indicator']
                        )]
                        
                        if critical_changes:
                            logger.info("[INTEGRATION] Criando backup devido a mudanças críticas")
                            self.backup_service.create_backup(
                                backup_type='config_change',
                                auto_cleanup=True
                            )
                
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
        
        # Multi-Asset Routes (se disponíveis)
        if MULTI_ASSET_ROUTES_AVAILABLE:
            self.app.register_blueprint(multi_asset_bp)
            logger.info("[CTRL] Multi-Asset blueprint registrado")

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
                
                # Trading Analyzer
                trading_status = self.trading_analyzer.get_system_status()
                health_data['components']['trading_analyzer'] = {
                    'status': 'active' if 'error' not in trading_status else 'error',
                    'active_signals': len(trading_status.get('signals', [])),
                    'analysis_count': trading_status.get('system_info', {}).get('total_analysis', 0)
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
        logger.info("=" * 80)
        logger.info("[START] SISTEMA INTEGRADO TRADING COMPLETO COM CONFIGURAÇÕES AVANÇADAS")
        logger.info("=" * 80)
        logger.info(f"[DATA] Dashboard Principal: http://localhost:{port}")
        logger.info(f"[BTC] Dashboard Bitcoin: http://localhost:{port}/bitcoin")
        logger.info(f"[TRADE] Dashboard Trading: http://localhost:{port}/trading")
        logger.info(f"[SETTINGS] Configurações: http://localhost:{port}/settings")
        
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
        
        if self.multi_asset_manager:
            logger.info(f"   - Multi-Asset Overview: http://localhost:{port}/api/multi-asset/overview")
            logger.info(f"   - Multi-Asset Health: http://localhost:{port}/api/multi-asset/health")
        
        logger.info("")
        logger.info("[FEATURES] SISTEMAS HABILITADOS:")
        logger.info("   ✅ Bitcoin Streaming (Binance API)")
        logger.info("   ✅ Enhanced Trading Analyzer")
        logger.info("   ✅ Dynamic Configuration Manager")
        logger.info("   ✅ Configuration Middleware")
        logger.info("   ✅ Notification System (Email/Webhook/Slack/Discord/Telegram)")
        logger.info("   ✅ Automated Backup System")
        logger.info("   ✅ Real-time Config Validation")
        logger.info("   ✅ Config History & Rollback")
        logger.info("   ✅ System Health Monitoring")
        logger.info("   ✅ CLI Configuration Tool")
        
        if self.multi_asset_manager:
            logger.info("   ✅ Multi-Asset Support (BTC/ETH/SOL)")
            logger.info(f"   📊 Assets Suportados: {', '.join(app_config.get_supported_asset_symbols())}")
        
        logger.info("")
        logger.info("[PERSISTENCE] Persistência habilitada - dados preservados entre sessões")
        logger.info("[MONITORING] Monitoramento automático de saúde ativo")
        logger.info("[BACKUP] Backup automático configurado")
        logger.info("=" * 80)
        
        self.app.debug = debug
        
        try:
            # ===== INICIAR TODOS OS SERVIÇOS =====
            
            # 1. Iniciar serviços de backup
            logger.info("[INIT] Iniciando serviço de backup...")
            self.backup_service.start_auto_backup()
            
            # 2. Iniciar Bitcoin streaming original
            logger.info("[INIT] Iniciando Bitcoin streamer...")
            self.bitcoin_streamer.start_streaming()
            
            # 3. Aplicar configuração inicial via middleware
            logger.info("[INIT] Aplicando configuração inicial...")
            initial_config = self.config_manager.load_config()
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
            self.notification_service.send_notification(
                'SYSTEM_STATUS',
                'Sistema de Trading Iniciado',
                'Todos os componentes foram inicializados com sucesso',
                {
                    'version': '2.0.0',
                    'components': [
                        'Bitcoin Streamer', 'Trading Analyzer', 'Config Manager',
                        'Notification Service', 'Backup Service'
                    ] + (['Multi-Asset Manager'] if self.multi_asset_manager else []),
                    'startup_time': datetime.now().isoformat()
                }
            )
            
            logger.info("[READY] ✅ SISTEMA COMPLETO PRONTO! Iniciando servidor Flask...")
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
        logger.info("[FIX] Finalizando aplicação COMPLETA e salvando estado...")
        
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
            
            # 1. Parar streamers
            if self.bitcoin_streamer.is_running:
                self.bitcoin_streamer.stop_streaming()
            
            if self.multi_asset_manager:
                self.multi_asset_manager.shutdown()
            
            # 2. Salvar estados dos analyzers
            self.bitcoin_processor.force_process_batch()
            self.trading_analyzer.save_analyzer_state()
            
            if self.trading_analyzer.price_history:
                last_price_data = self.trading_analyzer.price_history[-1]
                self.trading_analyzer.save_price_data(
                    last_price_data['timestamp'], 
                    last_price_data['price'], 
                    last_price_data['volume']
                )
            
            # 3. Parar serviços avançados
            self.config_middleware.stop_auto_refresh()
            self.backup_service.stop_auto_backup()
            
            # 4. Criar backup final
            logger.info("[SHUTDOWN] Criando backup final...")
            final_backup = self.backup_service.create_backup(
                backup_type='shutdown',
                include_logs=True
            )
            
            if final_backup['success']:
                logger.info(f"[SHUTDOWN] Backup final criado: {final_backup['backup_file']}")
            
            # 5. Salvar configuração final
            final_config = self.config_manager.current_config
            self.config_manager.save_config(final_config, 'shutdown', 'Estado final do sistema')
            
            logger.info("[OK] ✅ Aplicação COMPLETA finalizada com sucesso - estado persistido.")
            
        except Exception as e:
            logger.error(f"[ERROR] Erro durante a finalização da aplicação: {e}")


# ==================== UTILITY FUNCTIONS EXPANDIDAS ====================

def validate_dependencies():
    """
    Checks if all required Python modules are installed.
    """
    logger.info("[VALIDATE] Verificando dependências Python...")
    
    required_modules = ['flask', 'requests', 'schedule', 'sqlite3']
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
        logger.error("[FIX] Instale com: pip install flask requests schedule")
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

# ==================== MAIN APPLICATION ENTRY POINT ====================
def main():
    """
    Main function to run the Complete Bitcoin Trading System application.
    """
    print("[START] Inicializando Sistema Integrado Trading COMPLETO com Persistência...")
    
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
        logger.info("[MAIN] Criando controller COMPLETO...")
        controller = IntegratedController()
        
        debug_mode = app_config.FLASK_DEBUG_MODE
        port = app_config.FLASK_PORT
        host = app_config.FLASK_HOST
        
        logger.info("[MAIN] Iniciando aplicação COMPLETA...")
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