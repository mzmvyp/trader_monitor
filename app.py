# your_project/app.py

import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta
import traceback

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

# Import blueprints for routes
from routes.main_routes import main_bp
from routes.bitcoin_routes import bitcoin_bp
from routes.trading_routes import trading_bp

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
        self.app = Flask(__name__)
        self.app.config.from_object(app_config)

        # Store datetime and timedelta directly on app for easy access in routes
        self.app.datetime = datetime
        self.app.timedelta = timedelta

        # Initialize services
        self.bitcoin_streamer = BitcoinDataStreamer(
            max_queue_size=app_config.BITCOIN_STREAM_MAX_QUEUE_SIZE,
            fetch_interval=app_config.BITCOIN_STREAM_FETCH_INTERVAL_SECONDS
        )
        self.bitcoin_processor = BitcoinStreamProcessor(
            db_path=app_config.BITCOIN_STREAM_DB
        )
        self.bitcoin_analytics = BitcoinAnalyticsEngine(
            db_path=app_config.BITCOIN_STREAM_DB
        )
        self.trading_analyzer = EnhancedTradingAnalyzer(
            db_path=app_config.TRADING_ANALYZER_DB
        )
        
        # Attach instances to Flask app context for access in routes
        self.app.bitcoin_streamer = self.bitcoin_streamer
        self.app.bitcoin_processor = self.bitcoin_processor
        self.app.bitcoin_analytics = self.bitcoin_analytics
        self.app.trading_analyzer = self.trading_analyzer

        self.last_trading_update = 0
        self.trading_update_interval = app_config.TRADING_ANALYZER_UPDATE_INTERVAL_SECONDS
        
        # Register subscribers for Bitcoin data stream
        self.bitcoin_streamer.add_subscriber(self.bitcoin_processor.process_stream_data)
        self.bitcoin_streamer.add_subscriber(self._feed_trading_analyzer_debounced)
        
        self.setup_routes()
        self.setup_error_handlers()
        
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
        self.app.register_blueprint(main_bp)
        self.app.register_blueprint(bitcoin_bp)
        self.app.register_blueprint(trading_bp)

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
        logger.info("[CTRL] Rotas registradas.")
        
        # Add global API routes for compatibility (ONLY non-duplicated ones)
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

        @self.app.route('/api/bitcoin/recent-data')
        def get_bitcoin_recent_data():
            try:
                limit = request.args.get('limit', 50, type=int)
                limit = min(limit, 1000)
                recent_data = self.bitcoin_streamer.get_recent_data(limit)
                return jsonify([data.to_dict() for data in recent_data])
            except Exception as e:
                logger.error(f"Erro ao obter dados recentes: {e}")
                return jsonify({'error': str(e)}), 500

        # Removed duplicated trading routes.
        # These routes are now exclusively handled by the trading_bp blueprint
        # from routes.trading_routes.
        #
        # @self.app.route('/api/trading/analysis')
        # def get_trading_analysis():
        #     try:
        #         analysis = self.trading_analyzer.get_current_analysis()
        #         return jsonify(analysis)
        #     except Exception as e:
        #         logger.error(f"Erro ao obter análise de trading: {e}")
        #         return jsonify({'error': str(e)}), 500
        #
        # @self.app.route('/api/trading/signals')
        # def get_trading_signals():
        #     try:
        #         limit = request.args.get('limit', 20, type=int)
        #         limit = min(limit, 100)
        #         analysis = self.trading_analyzer.get_current_analysis()
        #         signals = analysis.get('recent_signals', [])
        #         return jsonify(signals[-limit:] if signals else [])
        #     except Exception as e:
        #         logger.error(f"Erro ao obter sinais de trading: {e}")
        #         return jsonify({'error': str(e)}), 500

        logger.info("[CTRL] Rotas registradas.")

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
        logger.info("[START] SISTEMA INTEGRADO BITCOIN + TRADING COM PERSISTÊNCIA")
        logger.info("=" * 60)
        logger.info(f"[DATA] Dashboard Principal: http://localhost:{port}")
        logger.info(f"[BTC] Dashboard Bitcoin: http://localhost:{port}/bitcoin")
        logger.info(f"[TRADE] Dashboard Trading: http://localhost:{port}/trading")
        logger.info("")
        logger.info("[API] APIs disponíveis:")
        logger.info(f"   - Status Geral: http://localhost:{port}/api/integrated/status")
        logger.info(f"   - Dados Dashboard: http://localhost:{port}/api/integrated/dashboard-data")
        logger.info(f"   - Bitcoin Métricas: http://localhost:{port}/api/bitcoin/metrics")
        # Update these API routes to reflect the trading_bp prefix
        logger.info(f"   - Trading Análise: http://localhost:{port}/trading/api/analysis")
        logger.info(f"   - Sinais Ativos: http://localhost:{port}/trading/api/active-signals")
        logger.info("")
        logger.info("[CTRL] Controles (POST):")
        logger.info(f"   - Iniciar Stream: http://localhost:{port}/api/bitcoin/start-stream")
        logger.info(f"   - Parar Stream: http://localhost:{port}/api/bitcoin/stop-stream")
        logger.info(f"   - Forçar Salvar Estado: http://localhost:{port}/api/control/force-save")
        logger.info(f"   - Limpar Dados: http://localhost:{port}/api/control/cleanup")
        logger.info(f"   - Resetar Sinais: http://localhost:{port}/api/control/reset-signals")
        logger.info("")
        logger.info("[BINANCE] Usando apenas API Binance (intervalo: 5 minutos)")
        logger.info("[PERSIST] Persistência habilitada - dados preservados entre sessões")
        logger.info("=" * 60)
        
        self.app.debug = debug
        
        try:
            self.bitcoin_streamer.start_streaming()
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
            
            logger.info("[OK] Aplicação finalizada com sucesso - estado persistido.")
            
        except Exception as e:
            logger.error(f"[ERROR] Erro durante a finalização da aplicação: {e}")

# ==================== UTILITY FUNCTIONS ====================
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
        
        analysis = analyzer.get_current_analysis()
        logger.info(f"[DATA] Sinais de trading de exemplo criados: {len(analysis['recent_signals'])}")
        logger.info(f"[TARGET] Sinais ativos de exemplo: {analysis['active_signals']}")
        
    except Exception as e:
        logger.error(f"[ERROR] Erro ao criar dados de exemplo: {e}")
        logger.error(f"[ERROR] Traceback: {traceback.format_exc()}")

def validate_dependencies():
    """
    Checks if all required Python modules are installed.
    """
    required_modules = ['flask', 'requests', 'collections', 'sqlite3', 'threading', 'datetime', 'os', 'sys', 'time']
    missing = []
    
    for module_name in required_modules:
        try:
            __import__(module_name)
        except ImportError:
            missing.append(module_name)
    
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
    try:
        analyzer = EnhancedTradingAnalyzer(db_path=app_config.TRADING_ANALYZER_DB)
        _ = analyzer.get_current_analysis()
        logger.info("[OK] Trading Analyzer (com persistência) carregado com sucesso para verificação.")
        return True
    except Exception as e:
        logger.error(f"[ERROR] Problema com trading_analyzer durante a verificação inicial: {e}")
        logger.error(f"[ERROR] Traceback: {traceback.format_exc()}")
        return False

# ==================== MAIN APPLICATION ENTRY POINT ====================
def main():
    """
    Main function to run the Bitcoin Trading System application.
    """
    print("[START] Inicializando Sistema Integrado Bitcoin + Trading com Persistência...")
    
    if not validate_dependencies():
        return 1
    
    initialize_databases()

    if not check_trading_analyzer_initial_load():
        logger.critical("[ERROR] Falha na verificação inicial do Trading Analyzer. Encerrando.")
        return 1
    
    if not os.path.exists(app_config.BITCOIN_STREAM_DB) or os.path.getsize(app_config.BITCOIN_STREAM_DB) == 0:
        logger.info("[SAMPLE] Banco de dados de stream Bitcoin vazio ou não encontrado. Criando dados de exemplo...")
        create_sample_data()
    else:
        conn = sqlite3.connect(app_config.BITCOIN_STREAM_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bitcoin_stream")
        count = cursor.fetchone()[0]
        conn.close()
        if count == 0:
            logger.info("[SAMPLE] Banco de dados de stream Bitcoin existe mas está vazio. Criando dados de exemplo...")
            create_sample_data()
        else:
            logger.info(f"[DATA] Banco de dados de stream Bitcoin contém {count} registros. Usando dados existentes.")

    try:
        controller = IntegratedController()
        
        debug_mode = app_config.FLASK_DEBUG_MODE
        port = app_config.FLASK_PORT
        host = app_config.FLASK_HOST
        
        controller.run(debug=debug_mode, port=port, host=host)
        return 0
        
    except KeyboardInterrupt:
        logger.info("[STOP] Aplicação interrompida pelo usuário.")
        return 0
    except Exception as e:
        logger.critical(f"[ERROR] Erro crítico na execução principal da aplicação: {e}")
        logger.critical(f"[ERROR] Traceback: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    sys.exit(main())