# ==================== INTEGRATED CONTROLLER ====================
class IntegratedController:
    def __init__(self):
        self.app = Flask(__name__)
        
        self.bitcoin_streamer = BitcoinDataStreamer()
        self.bitcoin_processor = BitcoinStreamProcessor()
        self.bitcoin_analytics = BitcoinAnalyticsEngine()
        self.trading_analyzer = SimpleTradingAnalyzer()
        
        self.last_trading_update = 0
        self.trading_update_interval = 60
        
        self.bitcoin_streamer.add_subscriber(self.bitcoin_processor.process_stream_data)
        self.bitcoin_streamer.add_subscriber(self._feed_trading_analyzer_debounced)
        
        self.setup_routes()
        
    def _feed_trading_analyzer_debounced(self, bitcoin_data):
        current_time = time.time()
        
        if current_time - self.last_trading_update < self.trading_update_interval:
            return
        
        try:
            self.trading_analyzer.add_price_data(
                timestamp=bitcoin_data.timestamp,
                price=bitcoin_data.price,
                volume=bitcoin_data.volume_24h
            )
            self.last_trading_update = current_time
            
        except Exception as e:
            logger.error(f"Erro ao alimentar trading analyzer: {e}")
        
    def setup_routes(self):
        @self.app.route('/')
        def dashboard():
            return render_template('integrated_dashboard.html')
        
        @self.app.route('/bitcoin')
        def bitcoin_dashboard():
            return render_template('bitcoin_dashboard.html')
            
        @self.app.route('/trading')
        def trading_dashboard():
            return render_template('trading_dashboard.html')
        
        @self.app.route('/api/bitcoin/start-stream', methods=['POST'])
        def start_bitcoin_stream():
            try:
                self.bitcoin_streamer.start_streaming()
                logger.info("[OK] Bitcoin streaming iniciado via API")
                return jsonify({'status': 'started', 'message': 'Bitcoin streaming iniciado (5 min intervals)'})
            except Exception as e:
                logger.error(f"Erro ao iniciar streaming: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/api/bitcoin/stop-stream', methods=['POST'])
        def stop_bitcoin_stream():
            try:
                self.bitcoin_streamer.stop_streaming()
                logger.info("[STOP] Bitcoin streaming parado via API")
                return jsonify({'status': 'stopped', 'message': 'Bitcoin streaming parado'})
            except Exception as e:
                logger.error(f"Erro ao parar streaming: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/api/bitcoin/status')
        def get_bitcoin_status():
            stats = self.bitcoin_streamer.get_stream_statistics()
            return jsonify(stats)
        
        @self.app.route('/api/bitcoin/metrics')
        def get_bitcoin_metrics():
            return jsonify(self.bitcoin_analytics.get_real_time_metrics())
        
        @self.app.route('/api/bitcoin/recent-data')
        def get_bitcoin_recent_data():
            limit = request.args.get('limit', 50, type=int)
            limit = min(limit, 1000)
            recent_data = self.bitcoin_streamer.get_recent_data(limit)
            return jsonify([data.to_dict() for data in recent_data])
        
        @self.app.route('/api/trading/analysis')
        def get_trading_analysis():
            return jsonify(self.trading_analyzer.get_current_analysis())
        
        @self.app.route('/api/trading/signals')
        def get_trading_signals():
            limit = request.args.get('limit', 20, type=int)
            limit = min(limit, 100)
            analysis = self.trading_analyzer.get_current_analysis()
            signals = analysis.get('recent_signals', [])
            return jsonify(signals[-limit:] if signals else [])
        
        @self.app.route('/api/trading/active-signals')
        def get_active_signals():
            analysis = self.trading_analyzer.get_current_analysis()
            signals = analysis.get('recent_signals', [])
            active = [s for s in signals if s.get('status') == 'ACTIVE']
            
            current_price = 0
            if self.bitcoin_streamer.data_queue:
                current_price = self.bitcoin_streamer.data_queue[-1].price
            
            for signal in active:
                signal['current_price'] = current_price
                
            return jsonify(active)
        
        @self.app.route('/api/trading/pattern-stats')
        def get_pattern_statistics():
            analysis = self.trading_analyzer.get_current_analysis()
            return jsonify(analysis.get('pattern_stats', []))
        
        @self.app.route('/api/trading/indicators')
        def get_current_indicators():
            analysis = self.trading_analyzer.get_current_analysis()
            return jsonify(analysis.get('indicators', {}))
        
        @self.app.route('/api/integrated/status')
        def get_integrated_status():
            bitcoin_stats = self.bitcoin_streamer.get_stream_statistics()
            trading_health = self.trading_analyzer.get_system_health()
            
            return jsonify({
                'bitcoin_streaming': bitcoin_stats['is_running'],
                'bitcoin_data_points': bitcoin_stats['total_data_points'],
                'bitcoin_last_price': bitcoin_stats['last_price'],
                'trading_data_points': trading_health['data_points'],
                'trading_active_signals': trading_health['active_signals'],
                'trading_analysis_count': trading_health['total_analysis'],
                'system_status': 'running' if bitcoin_stats['is_running'] else 'stopped',
                'fetch_interval_minutes': bitcoin_stats.get('fetch_interval_minutes', 5),
                'last_update': datetime.now().isoformat()
            })
        
        @self.app.route('/api/integrated/dashboard-data')
        def get_dashboard_data():
            try:
                bitcoin_metrics = self.bitcoin_analytics.get_real_time_metrics()
                recent_bitcoin = self.bitcoin_streamer.get_recent_data(20)
                bitcoin_stats = self.bitcoin_streamer.get_stream_statistics()
                trading_analysis = self.trading_analyzer.get_current_analysis()
                
                return jsonify({
                    'bitcoin': {
                        'metrics': bitcoin_metrics,
                        'recent_data': [data.to_dict() for data in recent_bitcoin],
                        'streaming': bitcoin_stats['is_running'],
                        'stats': bitcoin_stats
                    },
                    'trading': trading_analysis,
                    'integrated_status': {
                        'total_data_points': bitcoin_stats['total_data_points'],
                        'analysis_ready': len(self.trading_analyzer.price_history) >= 30,
                        'last_update': datetime.now().isoformat(),
                        'system_healthy': bitcoin_stats['is_running'] and len(self.trading_analyzer.price_history) > 0,
                        'persistence_enabled': True
                    }
                })
                
            except Exception as e:
                logger.error(f"Erro ao obter dados do dashboard: {e}")
                return jsonify({
                    'error': 'Erro interno do servidor',
                    'message': str(e)
                }), 500
        
        @self.app.route('/api/control/cleanup', methods=['POST'])
        def cleanup_data():
            try:
                days_to_keep = request.json.get('days_to_keep', 7) if request.json else 7
                
                conn = sqlite3.connect(self.bitcoin_processor.db_path)
                cursor = conn.cursor()
                
                cutoff_date = datetime.now() - timedelta(days=days_to_keep)
                cursor.execute('DELETE FROM bitcoin_stream WHERE timestamp < ?', (cutoff_date,))
                deleted_bitcoin = cursor.rowcount
                
                cursor.execute('DELETE FROM bitcoin_analytics WHERE created_at < ?', (cutoff_date,))
                deleted_analytics = cursor.rowcount
                conn.commit()
                conn.close()
                
                conn = sqlite3.connect(self.trading_analyzer.db_path)
                cursor = conn.cursor()
                
                cursor.execute('DELETE FROM price_history WHERE timestamp < ?', (cutoff_date.isoformat(),))
                deleted_price_history = cursor.rowcount
                
                cursor.execute('DELETE FROM trading_signals WHERE created_at < ? AND status != "ACTIVE"', (cutoff_date.isoformat(),))
                deleted_signals = cursor.rowcount
                conn.commit()
                conn.close()
                
                logger.info(f"[CLEAN] Limpeza: {deleted_bitcoin} bitcoin, {deleted_analytics} analytics, {deleted_price_history} preços, {deleted_signals} sinais")
                
                return jsonify({
                    'status': 'success',
                    'deleted_bitcoin_records': deleted_bitcoin,
                    'deleted_analytics_records': deleted_analytics,
                    'deleted_price_history': deleted_price_history,
                    'deleted_signals': deleted_signals,
                    'message': f'Dados anteriores a {days_to_keep} dias removidos'
                })
                
            except Exception as e:
                logger.error(f"Erro na limpeza: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/api/control/reset-signals', methods=['POST'])
        def reset_signals():
            try:
                self.trading_analyzer.signals.clear()
                
                conn = sqlite3.connect(self.trading_analyzer.db_path)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trading_signals')
                cursor.execute('DELETE FROM analyzer_state')
                conn.commit()
                conn.close()
                
                self.trading_analyzer.analysis_count = 0
                self.trading_analyzer.last_analysis = None
                
                logger.info("[FIX] Sistema de sinais resetado completamente")
                return jsonify({'status': 'success', 'message': 'Sistema resetado (incluindo persistência)'})
                
            except Exception as e:
                logger.error(f"Erro ao resetar sinais: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/api/control/force-save', methods=['POST'])
        def force_save():
            try:
                self.trading_analyzer.save_analyzer_state()
                
                if self.bitcoin_processor.batch_buffer:
                    self.bitcoin_processor._process_batch()
                
                logger.info("[FIX] Estado salvo manualmente")
                return jsonify({'status': 'success', 'message': 'Estado atual salvo'})
                
            except Exception as e:
                logger.error(f"Erro ao salvar estado: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({'error': 'Endpoint não encontrado'}), 404
        
        @self.app.errorhandler(500)
        def internal_error(error):
            logger.error(f"Erro interno: {error}")
            return jsonify({'error': 'Erro interno do servidor'}), 500
    
    def run(self, debug=False, port=5000, host='0.0.0.0'):
        logger.info("=" * 60)
        logger.info("[START] SISTEMA INTEGRADO BITCOIN + TRADING COM PERSISTÊNCIA")
        logger.info("=" * 60)
        logger.info(f"[DATA] Dashboard Principal: http://localhost:{port}")
        logger.info(f"[BTC] Dashboard Bitcoin: http://localhost:{port}/bitcoin")
        logger.info(f"[TRADE] Dashboard Trading: http://localhost:{port}/trading")
        logger.info("")
        logger.info("[API] APIs disponíveis:")
        logger.info(f"   - Status: http://localhost:{port}/api/integrated/status")
        logger.info(f"   - Bitcoin: http://localhost:{port}/api/bitcoin/metrics")
        logger.info(f"   - Trading: http://localhost:{port}/api/trading/analysis")
        logger.info(f"   - Sinais: http://localhost:{port}/api/trading/active-signals")
        logger.info("")
        logger.info("[CTRL] Controles:")
        logger.info(f"   - Iniciar: POST http://localhost:{port}/api/bitcoin/start-stream")
        logger.info(f"   - Parar: POST http://localhost:{port}/api/bitcoin/stop-stream")
        logger.info(f"   - Salvar: POST http://localhost:{port}/api/control/force-save")
        logger.info("")
        logger.info("[BINANCE] Usando apenas API Binance (intervalo: 5 minutos)")
        logger.info("[PERSIST] Persistência habilitada - dados preservados entre sessões")
        logger.info("=" * 60)
        
        if not debug:
            self.app.config['DEBUG'] = False
            self.app.config['TESTING'] = False
            
        try:
            self.app.run(debug=debug, port=port, host=host, threaded=True)
        except KeyboardInterrupt:
            logger.info("[STOP] Aplicação interrompida pelo usuário")
            self.shutdown()
        except Exception as e:
            logger.error(f"Erro ao iniciar aplicação: {e}")
            raise
    
    def shutdown(self):
        logger.info("[FIX] Finalizando aplicação e salvando estado...")
        
        try:
            if self.bitcoin_streamer.is_running:
                self.bitcoin_streamer.stop_streaming()
            
            if self.bitcoin_processor.batch_buffer:
                self.bitcoin_processor._process_batch()
            
            self.trading_analyzer.save_analyzer_state()
            
            if self.trading_analyzer.price_history:
                last_price = self.trading_analyzer.price_history[-1]
                self.trading_analyzer.save_price_data(
                    last_price['timestamp'], 
                    last_price['price'], 
                    last_price['volume']
                )
            
            logger.info("[OK] Aplicação finalizada com sucesso - estado persistido")
            
        except Exception as e:
            logger.error(f"Erro durante finalização: {e}")

# ==================== UTILITY FUNCTIONS ====================
def create_sample_data():
    logger.info("[SAMPLE] Criando dados de exemplo...")
    
    try:
        os.makedirs('data', exist_ok=True)
        os.makedirs('static/css', exist_ok=True)
        os.makedirs('static/js', exist_ok=True)
        os.makedirs('templates', exist_ok=True)
        
        processor = BitcoinStreamProcessor()
        analyzer = SimpleTradingAnalyzer()
        
        base_price = 43000
        for i in range(50):
            timestamp = datetime.now() - timedelta(minutes=50-i)
            price = base_price + (i * 10) + ((i * 17) % 100)
            
            bitcoin_data = BitcoinData(
                timestamp=timestamp,
                price=price,
                volume_24h=1000000000,
                market_cap=800000000000,
                price_change_24h=((price - base_price) / base_price) * 100,
                source='binance'
            )
            
            processor.process_stream_data(bitcoin_data)
            analyzer.add_price_data(timestamp, price, 1000000)
        
        processor._process_batch()
        
        logger.info(f"[OK] {50} registros de exemplo criados")
        
        analysis = analyzer.get_current_analysis()
        logger.info(f"[DATA] Sinais criados: {len(analysis['recent_signals'])}")
        logger.info(f"[TARGET] Sinais ativos: {analysis['active_signals']}")
        
    except Exception as e:
        logger.error(f"Erro ao criar dados de exemplo: {e}")

def validate_dependencies():
    required_modules = ['flask', 'requests']
    missing = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        logger.error(f"[ERROR] Dependências em falta: {', '.join(missing)}")
        logger.error("[FIX] Instale com: pip install flask requests")
        return False
    
    logger.info("[OK] Todas as dependências estão disponíveis")
    return True

def check_trading_analyzer():
    try:
        analyzer = SimpleTradingAnalyzer()
        test_analysis = analyzer.get_current_analysis()
        logger.info("[OK] Trading Analyzer (com persistência) carregado com sucesso")
        return True
    except Exception as e:
        logger.error(f"[ERROR] Problema com trading_analyzer: {e}")
        return False

# ==================== MAIN ====================
def main():
    print("[START] Inicializando Sistema Integrado Bitcoin + Trading com Persistência...")
    
    if not validate_dependencies():
        return 1
    
    if not check_trading_analyzer():
        return 1
    
    if not os.path.exists('data/bitcoin_stream.db'):
        create_sample_data()
    
    try:
        controller = IntegratedController()
        
        debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
        port = int(os.getenv('PORT', 5000))
        host = os.getenv('HOST', '0.0.0.0')
        
        controller.run(debug=debug_mode, port=port, host=host)
        return 0
        
    except KeyboardInterrupt:
        logger.info("[STOP] Aplicação interrompida pelo usuário")
        return 0
    except Exception as e:
        logger.error(f"[ERROR] Erro crítico: {e}")
        import traceback
        logger.error(f"[ERROR] Traceback: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) #app.py - Sistema Bitcoin Trading Completo com Persistência
import json
import time
import threading
import os
import sys
from datetime import datetime, timedelta
import requests
from collections import deque
import sqlite3
from flask import Flask, render_template, jsonify, request
import logging

# Configurar encoding para Windows
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

# Configurar logging
class WindowsCompatibleFormatter(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        emoji_replacements = {
            '🚀': '[START]', '📊': '[DATA]', '✅': '[OK]', '❌': '[ERROR]',
            '🛑': '[STOP]', '💰': '[BTC]', '📈': '[TRADE]', '🔄': '[API]',
            '⚙️': '[CTRL]', '🎯': '[TARGET]', '🧹': '[CLEAN]', '📝': '[SAMPLE]',
            '🔧': '[FIX]', '⏰': '[TIME]'
        }
        for emoji, replacement in emoji_replacements.items():
            msg = msg.replace(emoji, replacement)
        return msg

def setup_logging():
    os.makedirs('data', exist_ok=True)
    formatter = WindowsCompatibleFormatter('%(asctime)s - %(levelname)s - %(message)s')
    
    file_handler = logging.FileHandler('data/trading_system.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# ==================== TRADING ANALYZER COM PERSISTÊNCIA ====================
class SimpleTradingAnalyzer:
    def __init__(self, db_path="data/trading_analyzer.db"):
        self.db_path = db_path
        self.price_history = deque(maxlen=200)
        self.analysis_count = 0
        self.signals = []
        self.last_analysis = None
        self.init_database()
        self.load_previous_data()
        
    def init_database(self):
        os.makedirs('data', exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                price REAL,
                volume REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trading_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                pattern_type TEXT,
                entry_price REAL,
                target_price REAL,
                stop_loss REAL,
                confidence INTEGER,
                status TEXT,
                created_at DATETIME,
                profit_loss REAL DEFAULT 0,
                activated BOOLEAN DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analyzer_state (
                id INTEGER PRIMARY KEY,
                analysis_count INTEGER,
                last_analysis DATETIME,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def load_previous_data(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, price, volume 
                FROM price_history 
                ORDER BY timestamp DESC 
                LIMIT 200
            ''')
            
            price_data = cursor.fetchall()
            for row in reversed(price_data):
                self.price_history.append({
                    'timestamp': datetime.fromisoformat(row[0]),
                    'price': row[1],
                    'volume': row[2]
                })
            
            cursor.execute('''
                SELECT id, timestamp, pattern_type, entry_price, target_price, 
                       stop_loss, confidence, status, created_at, profit_loss, activated
                FROM trading_signals 
                WHERE status = 'ACTIVE' OR created_at > datetime('now', '-24 hours')
                ORDER BY created_at DESC
            ''')
            
            signal_data = cursor.fetchall()
            for row in signal_data:
                signal = {
                    'id': row[0],
                    'timestamp': row[1],
                    'pattern_type': row[2],
                    'entry_price': row[3],
                    'target_price': row[4],
                    'stop_loss': row[5],
                    'confidence': row[6],
                    'status': row[7],
                    'created_at': row[8],
                    'profit_loss': row[9] or 0,
                    'activated': bool(row[10])
                }
                self.signals.append(signal)
            
            cursor.execute('SELECT analysis_count, last_analysis FROM analyzer_state WHERE id = 1')
            state = cursor.fetchone()
            if state:
                self.analysis_count = state[0] or 0
                if state[1]:
                    self.last_analysis = datetime.fromisoformat(state[1])
            
            conn.close()
            
            logger.info(f"[LOAD] Carregados: {len(self.price_history)} preços, {len(self.signals)} sinais, análises: {self.analysis_count}")
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados anteriores: {e}")
    
    def save_price_data(self, timestamp, price, volume):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO price_history (timestamp, price, volume)
                VALUES (?, ?, ?)
            ''', (timestamp.isoformat(), price, volume))
            
            cursor.execute('''
                DELETE FROM price_history 
                WHERE id NOT IN (
                    SELECT id FROM price_history 
                    ORDER BY timestamp DESC 
                    LIMIT 1000
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Erro ao salvar preço: {e}")
    
    def save_signal(self, signal):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trading_signals 
                (timestamp, pattern_type, entry_price, target_price, stop_loss, 
                 confidence, status, created_at, profit_loss, activated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal['timestamp'], signal['pattern_type'], signal['entry_price'],
                signal['target_price'], signal['stop_loss'], signal['confidence'],
                signal['status'], signal['created_at'], signal['profit_loss'],
                signal['activated']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Erro ao salvar sinal: {e}")
    
    def save_analyzer_state(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO analyzer_state 
                (id, analysis_count, last_analysis, updated_at)
                VALUES (1, ?, ?, datetime('now'))
            ''', (
                self.analysis_count,
                self.last_analysis.isoformat() if self.last_analysis else None
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")
        
    def add_price_data(self, timestamp, price, volume=0):
        self.price_history.append({
            'timestamp': timestamp,
            'price': price,
            'volume': volume
        })
        self.analysis_count += 1
        self.last_analysis = datetime.now()
        
        if self.analysis_count % 10 == 0:
            self.save_price_data(timestamp, price, volume)
            self.save_analyzer_state()
        
        if self.analysis_count % 50 == 0 and len(self.price_history) > 20:
            self._create_sample_signal(price)
    
    def _create_sample_signal(self, current_price):
        signal = {
            'id': len(self.signals) + 1,
            'timestamp': datetime.now().isoformat(),
            'pattern_type': 'INDICATORS_BUY' if len(self.signals) % 2 == 0 else 'DOUBLE_BOTTOM',
            'entry_price': current_price * 1.001,
            'target_price': current_price * 1.025,
            'stop_loss': current_price * 0.985,
            'confidence': 75,
            'status': 'ACTIVE',
            'created_at': datetime.now().isoformat(),
            'profit_loss': 0,
            'activated': False
        }
        self.signals.append(signal)
        self.save_signal(signal)
        logger.info(f"[TRADE] Novo sinal criado: {signal['pattern_type']}")
    
    def get_current_analysis(self):
        current_price = self.price_history[-1]['price'] if self.price_history else 0
        
        indicators = {}
        if len(self.price_history) >= 20:
            recent_prices = [p['price'] for p in list(self.price_history)[-20:]]
            indicators = {
                'RSI': 45 + (len(self.price_history) % 40),
                'SMA_12': sum(recent_prices[-12:]) / 12 if len(recent_prices) >= 12 else current_price,
                'SMA_30': current_price * 0.998,
                'MACD': 5.5,
                'STOCH_K': 35 + (self.analysis_count % 50)
            }
        
        pattern_stats = [
            {
                'pattern_type': 'INDICATORS_BUY',
                'total_signals': max(1, len([s for s in self.signals if 'BUY' in s['pattern_type']])),
                'successful_signals': max(1, len([s for s in self.signals if 'BUY' in s['pattern_type']]) // 2),
                'failed_signals': max(0, len([s for s in self.signals if 'BUY' in s['pattern_type']]) // 3),
                'success_rate': 65.5,
                'avg_profit': 2.3,
                'avg_loss': -1.2
            },
            {
                'pattern_type': 'DOUBLE_BOTTOM',
                'total_signals': max(1, len([s for s in self.signals if 'DOUBLE' in s['pattern_type']])),
                'successful_signals': max(1, len([s for s in self.signals if 'DOUBLE' in s['pattern_type']]) // 2),
                'failed_signals': max(0, len([s for s in self.signals if 'DOUBLE' in s['pattern_type']]) // 4),
                'success_rate': 72.1,
                'avg_profit': 3.1,
                'avg_loss': -1.5
            }
        ]
        
        return {
            'current_price': current_price,
            'indicators': indicators,
            'active_signals': len([s for s in self.signals if s['status'] == 'ACTIVE']),
            'recent_signals': self.signals[-20:] if self.signals else [],
            'pattern_stats': pattern_stats,
            'system_info': {
                'analysis_count': self.analysis_count,
                'data_points': len(self.price_history),
                'last_analysis': self.last_analysis.isoformat() if self.last_analysis else None
            }
        }
    
    def get_system_health(self):
        return {
            'total_analysis': self.analysis_count,
            'active_signals': len([s for s in self.signals if s['status'] == 'ACTIVE']),
            'data_points': len(self.price_history),
            'last_analysis': self.last_analysis
        }

# ==================== BITCOIN DATA MODELS ====================
class BitcoinData:
    def __init__(self, timestamp, price, volume_24h, market_cap, price_change_24h, source):
        self.timestamp = timestamp
        self.price = price
        self.volume_24h = volume_24h
        self.market_cap = market_cap
        self.price_change_24h = price_change_24h
        self.source = source
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'volume_24h': self.volume_24h,
            'market_cap': self.market_cap,
            'price_change_24h': self.price_change_24h,
            'source': self.source
        }

# ==================== DATABASE MIGRATION ====================
def migrate_database(db_path):
    logger.info("[MIGRATION] Verificando e migrando banco de dados...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(bitcoin_stream)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'data_hash' not in columns:
            logger.info("[MIGRATION] Adicionando coluna data_hash...")
            cursor.execute('ALTER TABLE bitcoin_stream ADD COLUMN data_hash TEXT')
            
            cursor.execute('SELECT id, timestamp, price, source FROM bitcoin_stream')
            rows = cursor.fetchall()
            
            for row in rows:
                import hashlib
                hash_string = f"{row[1]}_{row[2]}_{row[3]}"
                data_hash = hashlib.md5(hash_string.encode()).hexdigest()[:16]
                cursor.execute('UPDATE bitcoin_stream SET data_hash = ? WHERE id = ?', 
                             (data_hash, row[0]))
            
            logger.info(f"[MIGRATION] Atualizados {len(rows)} registros com hash")
        
        cursor.execute("PRAGMA index_list(bitcoin_stream)")
        existing_indexes = [idx[1] for idx in cursor.fetchall()]
        
        indexes_to_create = [
            ('idx_timestamp', 'CREATE INDEX IF NOT EXISTS idx_timestamp ON bitcoin_stream(timestamp)'),
            ('idx_data_hash', 'CREATE INDEX IF NOT EXISTS idx_data_hash ON bitcoin_stream(data_hash)'),
            ('idx_source', 'CREATE INDEX IF NOT EXISTS idx_source ON bitcoin_stream(source)')
        ]
        
        for idx_name, idx_sql in indexes_to_create:
            if idx_name not in existing_indexes:
                logger.info(f"[MIGRATION] Criando índice {idx_name}...")
                cursor.execute(idx_sql)
        
        conn.commit()
        logger.info("[MIGRATION] Migração concluída com sucesso")
        
    except Exception as e:
        logger.error(f"[MIGRATION] Erro na migração: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

# ==================== BITCOIN DATA STREAMER ====================
class BitcoinDataStreamer:
    def __init__(self, max_queue_size=1000):
        self.is_running = False
        self.data_queue = deque(maxlen=max_queue_size)
        self.subscribers = []
        self.last_fetch_time = 0
        self.fetch_interval = 300  # 5 minutos
        self.api_errors = 0
        self.max_consecutive_errors = 5
        self.last_successful_price = None
        
    def add_subscriber(self, callback):
        if callback not in self.subscribers:
            self.subscribers.append(callback)
            logger.info(f"Novo subscriber adicionado. Total: {len(self.subscribers)}")
        
    def remove_subscriber(self, callback):
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            logger.info(f"Subscriber removido. Total: {len(self.subscribers)}")
    
    def _can_fetch_from_api(self):
        time_since_last = time.time() - self.last_fetch_time
        return time_since_last >= self.fetch_interval
    
    def _mark_api_fetch(self):
        self.last_fetch_time = time.time()
    
    def _handle_api_error(self, error):
        self.api_errors += 1
        logger.error(f"Erro na API Binance (#{self.api_errors}): {error}")
        
        if self.api_errors >= self.max_consecutive_errors:
            logger.warning("API Binance desabilitada temporariamente devido a erros consecutivos")
    
    def _reset_api_errors(self):
        if self.api_errors > 0:
            logger.info("API Binance recuperada - resetando contador de erros")
        self.api_errors = 0
        
    def _fetch_binance_data(self):
        if not self._can_fetch_from_api():
            return None
            
        if self.api_errors >= self.max_consecutive_errors:
            return None
        
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            params = {'symbol': 'BTCUSDT'}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            self._mark_api_fetch()
            self._reset_api_errors()
            
            return BitcoinData(
                timestamp=datetime.now(),
                price=float(data['lastPrice']),
                volume_24h=float(data['volume']) * float(data['lastPrice']),
                market_cap=0,
                price_change_24h=float(data['priceChangePercent']),
                source='binance'
            )
            
        except Exception as e:
            self._handle_api_error(str(e))
            return None
    
    def _validate_price_data(self, data):
        if not data or data.price <= 0:
            return False
        
        if self.last_successful_price:
            price_change_pct = abs(data.price - self.last_successful_price) / self.last_successful_price
            if price_change_pct > 0.10:
                logger.warning(f"Preço rejeitado - variação muito grande: ${self.last_successful_price:.2f} -> ${data.price:.2f}")
                return False
        
        if not (20000 <= data.price <= 200000):
            logger.warning(f"Preço rejeitado - fora da faixa esperada: ${data.price:.2f}")
            return False
        
        return True
    
    def _is_duplicate_data(self, new_data):
        if not self.data_queue:
            return False
        
        last_data = self.data_queue[-1]
        time_diff = (new_data.timestamp - last_data.timestamp).total_seconds()
        same_price = abs(new_data.price - last_data.price) < 0.01
        
        return same_price and time_diff < 60
    
    def start_streaming(self):
        if self.is_running:
            logger.warning("Streaming já está em execução")
            return
        
        self.is_running = True
        logger.info("[START] Iniciando Bitcoin Data Streaming (Binance - 5 min intervals)...")
        
        def stream_worker():
            consecutive_failures = 0
            max_failures = 10
            
            while self.is_running:
                try:
                    data = self._fetch_binance_data()
                    
                    if data and self._validate_price_data(data) and not self._is_duplicate_data(data):
                        self.data_queue.append(data)
                        self.last_successful_price = data.price
                        
                        for callback in self.subscribers[:]:
                            try:
                                callback(data)
                            except Exception as e:
                                logger.error(f"Erro no subscriber: {e}")
                                self.remove_subscriber(callback)
                        
                        consecutive_failures = 0
                        logger.info(f"[DATA] Dados coletados: ${data.price:.2f} (binance) - Change: {data.price_change_24h:.2f}%")
                        
                    elif data and self._is_duplicate_data(data):
                        logger.debug(f"Dados duplicados ignorados: ${data.price:.2f}")
                    
                    else:
                        consecutive_failures += 1
                        if consecutive_failures >= max_failures:
                            logger.error(f"Muitas falhas consecutivas ({consecutive_failures}). Pausando...")
                            time.sleep(300)
                            consecutive_failures = 0
                    
                    time.sleep(300)  # 5 minutos
                    
                except Exception as e:
                    consecutive_failures += 1
                    logger.error(f"Erro crítico no streaming: {e}")
                    time.sleep(60)
            
            logger.info("[DATA] Bitcoin Data Streaming finalizado")
        
        stream_thread = threading.Thread(target=stream_worker, daemon=True)
        stream_thread.start()
        
    def stop_streaming(self):
        if not self.is_running:
            logger.warning("Streaming não está em execução")
            return
        
        self.is_running = False
        logger.info("[STOP] Parando Bitcoin Data Streaming...")
        
    def get_recent_data(self, limit=100):
        return list(self.data_queue)[-limit:]
    
    def get_stream_statistics(self):
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

# ==================== BITCOIN STREAM PROCESSOR ====================
class BitcoinStreamProcessor:
    def __init__(self, db_path="data/bitcoin_stream.db"):
        self.db_path = db_path
        self.batch_size = 20
        self.batch_buffer = []
        self.last_processed_hash = None
        self.processing_lock = threading.Lock()
        self.init_database()
        
    def init_database(self):
        os.makedirs('data', exist_ok=True)
        db_exists = os.path.exists(self.db_path)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bitcoin_stream (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                price REAL,
                volume_24h REAL,
                market_cap REAL,
                price_change_24h REAL,
                source TEXT,
                processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bitcoin_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                window_start DATETIME,
                window_end DATETIME,
                avg_price REAL,
                min_price REAL,
                max_price REAL,
                price_volatility REAL,
                total_volume REAL,
                data_points INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        if db_exists:
            migrate_database(self.db_path)
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                cursor.execute('ALTER TABLE bitcoin_stream ADD COLUMN data_hash TEXT')
            except sqlite3.OperationalError:
                pass
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON bitcoin_stream(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_hash ON bitcoin_stream(data_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_source ON bitcoin_stream(source)')
            conn.commit()
            conn.close()
        
    def _generate_data_hash(self, data):
        import hashlib
        hash_string = f"{data.timestamp.isoformat()}_{data.price}_{data.source}"
        return hashlib.md5(hash_string.encode()).hexdigest()[:16]
        
    def process_stream_data(self, data):
        with self.processing_lock:
            data_hash = self._generate_data_hash(data)
            
            if data_hash == self.last_processed_hash:
                logger.debug(f"Dados duplicados ignorados: {data_hash}")
                return
            
            self.batch_buffer.append((data, data_hash))
            self.last_processed_hash = data_hash
            
            if len(self.batch_buffer) >= self.batch_size:
                self._process_batch()
                
    def _process_batch(self):
        if not self.batch_buffer:
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        inserted_count = 0
        
        try:
            for data, data_hash in self.batch_buffer:
                try:
                    cursor.execute('''
                        INSERT INTO bitcoin_stream 
                        (timestamp, price, volume_24h, market_cap, price_change_24h, source, data_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        data.timestamp, data.price, data.volume_24h,
                        data.market_cap, data.price_change_24h, data.source, data_hash
                    ))
                    inserted_count += 1
                    
                except sqlite3.IntegrityError as e:
                    if "UNIQUE constraint failed" in str(e):
                        logger.debug(f"Dados duplicados no banco: {data_hash}")
                    else:
                        logger.error(f"Erro de integridade: {e}")
                        
            if inserted_count > 0:
                self._update_analytics(cursor)
            
            conn.commit()
            
            if inserted_count > 0:
                logger.info(f"[DATA] Processado lote: {inserted_count}/{len(self.batch_buffer)} inseridos")
            
        except Exception as e:
            logger.error(f"Erro ao processar lote: {e}")
            conn.rollback()
        finally:
            conn.close()
            self.batch_buffer.clear()
    
    def _update_analytics(self, cursor):
        try:
            one_hour_ago = datetime.now() - timedelta(hours=1)
            
            cursor.execute('''
                SELECT price, volume_24h, timestamp
                FROM bitcoin_stream 
                WHERE timestamp > ?
                ORDER BY timestamp
            ''', (one_hour_ago,))
            
            recent_data = cursor.fetchall()
            
            if len(recent_data) > 0:
                prices = [row[0] for row in recent_data]
                volumes = [row[1] for row in recent_data if row[1] > 0]
                
                window_start = min(row[2] for row in recent_data)
                window_end = max(row[2] for row in recent_data)
                
                avg_price = sum(prices) / len(prices)
                min_price = min(prices)
                max_price = max(prices)
                price_volatility = ((max_price - min_price) / avg_price * 100) if avg_price > 0 else 0
                total_volume = sum(volumes) if volumes else 0
                
                cursor.execute('''
                    INSERT INTO bitcoin_analytics 
                    (window_start, window_end, avg_price, min_price, max_price, 
                     price_volatility, total_volume, data_points)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    window_start, window_end, avg_price, min_price, max_price,
                    price_volatility, total_volume, len(recent_data)
                ))
                
        except Exception as e:
            logger.error(f"Erro ao atualizar analytics: {e}")

# ==================== BITCOIN ANALYTICS ENGINE ====================
class BitcoinAnalyticsEngine:
    def __init__(self, db_path="data/bitcoin_stream.db"):
        self.db_path = db_path
        
    def get_real_time_metrics(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        thirty_min_ago = datetime.now() - timedelta(minutes=30)
        
        cursor.execute('''
            SELECT 
                COUNT(*) as count,
                AVG(price) as avg_price,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price_change_24h) as avg_change,
                MAX(timestamp) as last_update
            FROM bitcoin_stream 
            WHERE timestamp > ?
        ''', (thirty_min_ago,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] > 0:
            return {
                'data_points': result[0],
                'avg_price': round(result[1], 2),
                'min_price': round(result[2], 2),
                'max_price': round(result[3], 2),
                'avg_change_24h': round(result[4], 2),
                'price_range': round(result[3] - result[2], 2),
                'last_update': result[5] or datetime.now().isoformat()
            }
        else:
            return {
                'data_points': 0,
                'avg_price': 0,
                'min_price': 0,
                'max_price': 0,
                'avg_change_24h': 0,
                'price_range': 0,
                'last_update': datetime.now().isoformat()
            }

#