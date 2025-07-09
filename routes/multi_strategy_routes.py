# routes/multi_strategy_routes.py
from flask import Blueprint, request, jsonify, render_template
from datetime import datetime, timedelta
import json

# Criar blueprint
multi_strategy_bp = Blueprint('multi_strategy', __name__, url_prefix='/api/multi')

# Variáveis globais (adaptar para sua aplicação)
multi_adapter = None  # Será inicializado na aplicação principal

def init_multi_routes(adapter):
    """Inicializa as rotas com o adaptador multi-timeframe"""
    global multi_adapter
    multi_adapter = adapter

@multi_strategy_bp.route('/signals/<asset>', methods=['GET'])
def get_current_signals(asset):
    """Retorna sinais atuais para um asset específico"""
    try:
        if not multi_adapter:
            return jsonify({'error': 'Sistema multi-timeframe não inicializado'}), 500
        
        # Obter resumo dos sinais atuais
        summary = multi_adapter.get_current_signals_summary(asset.upper())
        
        return jsonify({
            'success': True,
            'data': summary,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@multi_strategy_bp.route('/signals/all', methods=['GET'])
def get_all_signals():
    """Retorna sinais para todos os assets"""
    try:
        if not multi_adapter:
            return jsonify({'error': 'Sistema multi-timeframe não inicializado'}), 500
        
        # Assets suportados (adaptar para sua configuração)
        assets = ['BTC', 'ETH', 'SOL']
        all_signals = {}
        
        for asset in assets:
            try:
                summary = multi_adapter.get_current_signals_summary(asset)
                all_signals[asset] = summary
            except Exception as e:
                all_signals[asset] = {'error': str(e)}
        
        return jsonify({
            'success': True,
            'data': all_signals,
            'assets_count': len(assets),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@multi_strategy_bp.route('/force-signal/<asset>', methods=['POST'])
def force_signal_generation(asset):
    """Força geração de sinal para debug/teste"""
    try:
        if not multi_adapter:
            return jsonify({'error': 'Sistema multi-timeframe não inicializado'}), 500
        
        data = request.get_json() or {}
        strategy = data.get('strategy')  # 'scalp', 'day_trade', 'swing_trade' ou None (todas)
        
        signals = multi_adapter.force_signal_generation(asset.upper(), strategy)
        
        return jsonify({
            'success': True,
            'data': signals,
            'asset': asset.upper(),
            'strategy': strategy,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@multi_strategy_bp.route('/timeframe-data/<asset>/<timeframe>', methods=['GET'])
def get_timeframe_data(asset, timeframe):
    """Retorna dados históricos para um timeframe específico"""
    try:
        if not multi_adapter or not multi_adapter.multi_manager:
            return jsonify({'error': 'Sistema multi-timeframe não inicializado'}), 500
        
        # Parâmetros opcionais
        limit = request.args.get('limit', type=int, default=100)
        
        # Obter dados
        data = multi_adapter.multi_manager.get_data(asset.upper(), timeframe, limit)
        
        # Calcular indicadores
        indicators = multi_adapter.multi_manager.calculate_indicators(asset.upper(), timeframe)
        
        return jsonify({
            'success': True,
            'data': {
                'candles': data,
                'indicators': indicators,
                'timeframe': timeframe,
                'asset': asset.upper(),
                'count': len(data)
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@multi_strategy_bp.route('/data-summary/<asset>', methods=['GET'])
def get_data_summary(asset):
    """Retorna resumo dos dados disponíveis por timeframe"""
    try:
        if not multi_adapter or not multi_adapter.multi_manager:
            return jsonify({'error': 'Sistema multi-timeframe não inicializado'}), 500
        
        summary = multi_adapter.multi_manager.get_timeframe_data_summary(asset.upper())
        
        return jsonify({
            'success': True,
            'data': summary,
            'asset': asset.upper(),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@multi_strategy_bp.route('/config', methods=['GET'])
def get_strategy_configs():
    """Retorna configurações das estratégias"""
    try:
        if not multi_adapter:
            return jsonify({'error': 'Sistema multi-timeframe não inicializado'}), 500
        
        configs = {}
        for strategy_name, strategy in multi_adapter.strategies.items():
            configs[strategy_name] = {
                'name': strategy.name,
                'timeframe': strategy.timeframe,
                'hold_time': strategy.hold_time,
                'config': strategy.config
            }
        
        return jsonify({
            'success': True,
            'data': configs,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@multi_strategy_bp.route('/config/<strategy>', methods=['PUT'])
def update_strategy_config(strategy):
    """Atualiza configuração de uma estratégia"""
    try:
        if not multi_adapter:
            return jsonify({'error': 'Sistema multi-timeframe não inicializado'}), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Dados de configuração necessários'}), 400
        
        if strategy not in multi_adapter.strategies:
            return jsonify({'error': f'Estratégia {strategy} não encontrada'}), 404
        
        # Atualizar configuração
        strategy_obj = multi_adapter.strategies[strategy]
        for key, value in data.items():
            if key in strategy_obj.config:
                strategy_obj.config[key] = value
        
        return jsonify({
            'success': True,
            'message': f'Configuração da estratégia {strategy} atualizada',
            'new_config': strategy_obj.config,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ROTAS PARA INTERFACE WEB
@multi_strategy_bp.route('/dashboard')
def multi_strategy_dashboard():
    """Página principal do dashboard multi-timeframe"""
    return render_template('multi_strategy_dashboard.html')

@multi_strategy_bp.route('/dashboard/<asset>')
def asset_dashboard(asset):
    """Dashboard específico para um asset"""
    return render_template('asset_dashboard.html', asset=asset.upper())

# ROTAS WEBSOCKET (se usando Flask-SocketIO)
def setup_socketio_events(socketio, multi_adapter):
    """Configura eventos WebSocket para tempo real"""
    
    @socketio.on('subscribe_multi_signals')
    def handle_subscribe(data):
        """Cliente se inscreve para receber sinais em tempo real"""
        asset = data.get('asset', 'BTC')
        
        # Enviar estado atual
        try:
            summary = multi_adapter.get_current_signals_summary(asset)
            socketio.emit('multi_strategy_update', {
                'type': 'initial_state',
                'asset': asset,
                'data': summary
            })
        except Exception as e:
            socketio.emit('error', {'message': str(e)})
    
    @socketio.on('request_force_signal')
    def handle_force_signal(data):
        """Força geração de sinal via WebSocket"""
        asset = data.get('asset', 'BTC')
        strategy = data.get('strategy')
        
        try:
            signals = multi_adapter.force_signal_generation(asset, strategy)
            socketio.emit('multi_strategy_update', {
                'type': 'forced_signal',
                'asset': asset,
                'signals': signals
            })
        except Exception as e:
            socketio.emit('error', {'message': str(e)})
    
    # Registrar callback para sinais automáticos
    def websocket_signal_callback(signal_data):
        """Callback para enviar sinais via WebSocket"""
        socketio.emit('multi_strategy_update', signal_data)
    
    multi_adapter.register_signal_callback(websocket_signal_callback)

# FUNÇÃO DE INICIALIZAÇÃO PRINCIPAL
def setup_multi_strategy_routes(app, multi_adapter, socketio=None):
    """
    Função principal para configurar todas as rotas multi-timeframe
    
    Args:
        app: Aplicação Flask
        multi_adapter: WebSocketMultiAdapter inicializado
        socketio: Flask-SocketIO instance (opcional)
    """
    
    # Inicializar rotas
    init_multi_routes(multi_adapter)
    
    # Registrar blueprint
    app.register_blueprint(multi_strategy_bp)
    
    # Configurar WebSocket se disponível
    if socketio:
        setup_socketio_events(socketio, multi_adapter)
    
    print("✅ Rotas multi-timeframe configuradas:")
    print("   - GET  /api/multi/signals/<asset>")
    print("   - GET  /api/multi/signals/all") 
    print("   - POST /api/multi/force-signal/<asset>")
    print("   - GET  /api/multi/timeframe-data/<asset>/<timeframe>")
    print("   - GET  /api/multi/data-summary/<asset>")
    print("   - GET  /api/multi/config")
    print("   - PUT  /api/multi/config/<strategy>")
    print("   - GET  /api/multi/dashboard")
    print("   - GET  /api/multi/dashboard/<asset>")
    
    return multi_strategy_bp

# EXEMPLO DE USO NO SEU APP.PY PRINCIPAL
"""
# app.py ou main.py
from flask import Flask
from flask_socketio import SocketIO

# Suas importações atuais...
from routes.multi_strategy_routes import setup_multi_strategy_routes
from services.websocket_multi_adapter import WebSocketMultiAdapter
from services.multi_timeframe_manager import MultiTimeframeManager

app = Flask(__name__)
socketio = SocketIO(app)

# Inicializar sistema multi-timeframe
multi_manager = MultiTimeframeManager()
multi_adapter = WebSocketMultiAdapter(multi_manager, app)

# Configurar rotas
setup_multi_strategy_routes(app, multi_adapter, socketio)

# Integrar com seu WebSocket atual
def on_binance_message(message):
    # Sua lógica atual...
    
    # NOVA LINHA: Processar com multi-timeframe
    result = multi_adapter.on_price_update(asset, price_data)
    
    return result
"""