# app_fixed.py - Versão corrigida do app principal com Settings

import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta
import traceback

print("[START] Inicializando Sistema Integrado Multi-Asset Trading com Persistência...")

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
    from routes.settings_routes import settings_bp  # ===== NOVO: Settings Routes =====

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

# ==================== INTEGRATED CONTROLLER ====================
class IntegratedController:
    """
    The main application controller, responsible for initializing the Flask app,
    setting up all services (streamer, processor, analyzer, analytics),
    registering blueprints, and managing the application lifecycle.
    """
    def __init__(self):
        """
        Initializes the Flask application and all integrated components.
        """
        logger.info("[CTRL] Inicializando IntegratedController...")
        
        self.app = Flask(__name__)
        self.app.config.from_object(app_config)

        # Store datetime and timedelta directly on app for easy access in routes
        self.app.datetime = datetime
        self.app.timedelta = timedelta

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
        
        # Attach instances to Flask app context for access in routes
        self.app.bitcoin_streamer = self.bitcoin_streamer
        self.app.bitcoin_processor = self.bitcoin_processor
        self.app.bitcoin_analytics = self.bitcoin_analytics
        self.app.trading_analyzer = self.trading_analyzer
        
        if self.multi_asset_manager:
            self.app.multi_asset_manager = self.multi_asset_manager

        self.last_trading_update = 0
        self.trading_update_interval = app_config.TRADING_ANALYZER_UPDATE_INTERVAL_SECONDS
        
        # Register subscribers for Bitcoin data stream
        logger.info("[CTRL] Registrando subscribers...")
        self.bitcoin_streamer.add_subscriber(self.bitcoin_processor.process_stream_data)
        self.bitcoin_streamer.add_subscriber(self._feed_trading_analyzer_debounced)
        
        logger.info("[CTRL] Configurando routes e error handlers...")
        self.setup_routes()
        self.setup_error_handlers()
        
        logger.info("[CTRL] IntegratedController inicializado com sucesso")
        
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
        self.app.register_blueprint(settings_bp)  # ===== NOVO: Settings Blueprint =====
        
        # Multi-Asset Routes (se disponíveis)
        if MULTI_ASSET_ROUTES_AVAILABLE:
            self.app.register_blueprint(multi_asset_bp)
            logger.info("[CTRL] Multi-Asset blueprint registrado")

        # ===== NOVO: Settings Page Route =====
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
                return jsonify({'status': 'started', 'message': 'Bitcoin streaming iniciado (5 min intervals)'})
            except Exception as e:
                logger.error(f"Erro ao iniciar streaming: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500

        @self.app.route('/api/bitcoin/stop-stream', methods=['POST'])
        def stop_bitcoin_stream():
            try:
                self.bitcoin_streamer.stop_streaming()
                logger.info("[STOP] Bitcoin streaming parado via API.")
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
            return jsonify({'error': 'Erro interno do servidor', 'message': str(error)}), 500
        
        logger.info("[CTRL] Manipuladores de erro configurados.")
    
    def run(self, debug: bool = False, port: int = 5000, host: str = '0.0.0.0'):
        """
        Starts the Flask development server and initiates Bitcoin data streaming.
        """
        logger.info("=" * 60)
        if self.multi_asset_manager:
            logger.info("[START] SISTEMA INTEGRADO MULTI-ASSET TRADING COM PERSISTÊNCIA")
        else:
            logger.info("[START] SISTEMA INTEGRADO BITCOIN TRADING COM PERSISTÊNCIA")
        logger.info("=" * 60)
        logger.info(f"[DATA] Dashboard Principal: http://localhost:{port}")
        logger.info(f"[BTC] Dashboard Bitcoin: http://localhost:{port}/bitcoin")
        logger.info(f"[TRADE] Dashboard Trading: http://localhost:{port}/trading")
        logger.info(f"[SETTINGS] Configurações: http://localhost:{port}/settings")  # ===== NOVO =====
        
        if self.multi_asset_manager:
            logger.info(f"[MULTI] Dashboard Multi-Asset: http://localhost:{port}/multi-asset")
        
        logger.info("")
        logger.info("[API] APIs disponíveis:")
        logger.info(f"   - Status Geral: http://localhost:{port}/api/integrated/status")
        logger.info(f"   - Dados Dashboard: http://localhost:{port}/api/integrated/dashboard-data")
        logger.info(f"   - Bitcoin Métricas: http://localhost:{port}/api/bitcoin/metrics")
        logger.info(f"   - Trading Análise: http://localhost:{port}/trading/api/analysis")
        logger.info(f"   - Sinais Ativos: http://localhost:{port}/trading/api/active-signals")
        logger.info(f"   - Configurações: http://localhost:{port}/settings/api/get-config")  # ===== NOVO =====
        
        if self.multi_asset_manager:
            logger.info(f"   - Multi-Asset Overview: http://localhost:{port}/api/multi-asset/overview")
            logger.info(f"   - Multi-Asset Health: http://localhost:{port}/api/multi-asset/health")
        
        logger.info("")
        logger.info("[CTRL] Controles (POST):")
        logger.info(f"   - Iniciar Stream Bitcoin: http://localhost:{port}/api/bitcoin/start-stream")
        logger.info(f"   - Parar Stream Bitcoin: http://localhost:{port}/api/bitcoin/stop-stream")
        logger.info(f"   - Salvar Configurações: http://localhost:{port}/settings/api/save-config")  # ===== NOVO =====
        
        if self.multi_asset_manager:
            logger.info(f"   - Iniciar Multi-Asset: http://localhost:{port}/api/multi-asset/start")
            logger.info(f"   - Parar Multi-Asset: http://localhost:{port}/api/multi-asset/stop")
            logger.info(f"[ASSETS] Assets Suportados: {', '.join(app_config.get_supported_asset_symbols())}")
        
        logger.info("[BINANCE] Usando apenas API Binance (intervalo: 5 minutos)")
        logger.info("[PERSIST] Persistência habilitada - dados preservados entre sessões")
        logger.info("[SETTINGS] Sistema de configurações habilitado")  # ===== NOVO =====
        logger.info("=" * 60)
        
        self.app.debug = debug
        
        try:
            # Iniciar Bitcoin streaming original
            logger.info("[INIT] Iniciando Bitcoin streamer...")
            self.bitcoin_streamer.start_streaming()
            
            # Opcionalmente iniciar multi-asset
            if self.multi_asset_manager and app_config.AUTO_START_STREAM:
                logger.info("[INIT] Iniciando Multi-Asset streamers...")
                self.multi_asset_manager.start_streaming(['BTC', 'ETH', 'SOL'])
            
            logger.info("[READY] Sistema pronto! Iniciando servidor Flask...")
            self.app.run(debug=debug, port=port, host=host, threaded=True)
            
        except KeyboardInterrupt:
            logger.info("[STOP] Aplicação interrompida pelo usuário (Ctrl+C).")
            self.shutdown()
        except Exception as e:
            logger.critical(f"[ERROR] Erro fatal ao iniciar aplicação: {e}")
            logger.critical(f"[ERROR] Traceback: {traceback.format_exc()}")
            self.shutdown()
            raise
    
    def shutdown(self):
        """
        Performs a graceful shutdown of the application.
        """
        logger.info("[FIX] Finalizando aplicação e salvando estado...")
        
        try:
            if self.bitcoin_streamer.is_running:
                self.bitcoin_streamer.stop_streaming()
            
            self.bitcoin_processor.force_process_batch()
            self.trading_analyzer.save_analyzer_state()
            
            if self.trading_analyzer.price_history:
                last_price_data = self.trading_analyzer.price_history[-1]
                self.trading_analyzer.save_price_data(
                    last_price_data['timestamp'], 
                    last_price_data['price'], 
                    last_price_data['volume']
                )
            
            # Multi-Asset shutdown
            if self.multi_asset_manager:
                self.multi_asset_manager.shutdown()
            
            logger.info("[OK] Aplicação finalizada com sucesso - estado persistido.")
            
        except Exception as e:
            logger.error(f"[ERROR] Erro durante a finalização da aplicação: {e}")

# ==================== UTILITY FUNCTIONS ====================
def validate_dependencies():
    """
    Checks if all required Python modules are installed.
    """
    logger.info("[VALIDATE] Verificando dependências Python...")
    
    required_modules = ['flask', 'requests']
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
        logger.error("[FIX] Instale com: pip install flask requests")
        return False
    
    logger.info("[OK] Todas as dependências Python estão disponíveis.")
    return True

def check_trading_analyzer_initial_load():
    """
    Performs a basic check to ensure the Trading Analyzer can be initialized.
    """
    logger.info("[VALIDATE] Verificando Trading Analyzer...")
    
    try:
        analyzer = EnhancedTradingAnalyzer(db_path=app_config.TRADING_ANALYZER_DB)
        _ = analyzer.get_system_status()  # Método mais leve que get_current_analysis
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
    Main function to run the Bitcoin Trading System application.
    """
    print("[START] Inicializando Sistema Integrado Trading com Persistência...")
    
    logger.info("[MAIN] Iniciando validações...")
    
    if not validate_dependencies():
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
        logger.info("[MAIN] Criando controller...")
        controller = IntegratedController()
        
        debug_mode = app_config.FLASK_DEBUG_MODE
        port = app_config.FLASK_PORT
        host = app_config.FLASK_HOST
        
        logger.info("[MAIN] Iniciando aplicação...")
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