# your_project/routes/multi_asset_routes.py - ARQUIVO NOVO

from flask import Blueprint, jsonify, request, current_app, render_template
from utils.logging_config import logger
from config import app_config

# Create a Blueprint for Multi-Asset routes
multi_asset_bp = Blueprint('multi_asset_routes', __name__, url_prefix='/multi-asset')

@multi_asset_bp.route('/')
def multi_asset_dashboard():
    """Renders the Multi-Asset dashboard page."""
    return render_template('multi_asset_dashboard.html')

# ==================== OVERVIEW & STATUS ROUTES ====================

@multi_asset_bp.route('/api/overview')
def get_multi_asset_overview():
    """API endpoint para overview consolidado de todos os assets"""
    try:
        overview = current_app.multi_asset_manager.get_overview_data()
        return jsonify(overview)
    except Exception as e:
        logger.error(f"Erro ao obter overview multi-asset: {e}")
        return jsonify({'error': str(e)}), 500

@multi_asset_bp.route('/api/health')
def get_system_health():
    """API endpoint para saúde do sistema multi-asset"""
    try:
        health = current_app.multi_asset_manager.get_system_health()
        return jsonify(health)
    except Exception as e:
        logger.error(f"Erro ao obter saúde do sistema: {e}")
        return jsonify({'error': str(e)}), 500

@multi_asset_bp.route('/api/supported-assets')
def get_supported_assets():
    """API endpoint para lista de assets suportados"""
    try:
        assets = []
        for symbol in app_config.get_supported_asset_symbols():
            config = app_config.get_asset_config(symbol)
            assets.append({
                'symbol': symbol,
                'name': config['name'],
                'color': config['color'],
                'icon': config['icon'],
                'precision': config['precision']
            })
        
        return jsonify({
            'supported_assets': assets,
            'total_count': len(assets),
            'default_asset': app_config.DEFAULT_ASSET
        })
    except Exception as e:
        logger.error(f"Erro ao obter assets suportados: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== ASSET-SPECIFIC DATA ROUTES ====================

@multi_asset_bp.route('/api/asset/<asset_symbol>')
def get_asset_data(asset_symbol):
    """API endpoint para dados específicos de um asset"""
    try:
        limit = request.args.get('limit', 100, type=int)
        limit = min(limit, 1000)  # Cap the limit
        
        asset_data = current_app.multi_asset_manager.get_asset_data(asset_symbol, limit)
        return jsonify(asset_data)
    except Exception as e:
        logger.error(f"Erro ao obter dados do asset {asset_symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@multi_asset_bp.route('/api/asset/<asset_symbol>/recent-data')
def get_asset_recent_data(asset_symbol):
    """API endpoint para dados recentes de um asset específico"""
    try:
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 1000)
        
        streamer = current_app.multi_asset_manager.get_asset_streamer(asset_symbol)
        if not streamer:
            return jsonify({'error': f'Asset {asset_symbol} não encontrado'}), 404
        
        recent_data = streamer.get_recent_data(limit)
        return jsonify([data.to_dict() for data in recent_data])
    except Exception as e:
        logger.error(f"Erro ao obter dados recentes do {asset_symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@multi_asset_bp.route('/api/asset/<asset_symbol>/analysis')
def get_asset_analysis(asset_symbol):
    """API endpoint para análise técnica de um asset específico"""
    try:
        analyzer = current_app.multi_asset_manager.get_asset_analyzer(asset_symbol)
        if not analyzer:
            return jsonify({'error': f'Analyzer para {asset_symbol} não encontrado'}), 404
        
        analysis = analyzer.get_comprehensive_analysis()
        return jsonify(analysis)
    except Exception as e:
        logger.error(f"Erro ao obter análise do {asset_symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@multi_asset_bp.route('/api/asset/<asset_symbol>/signals')
def get_asset_signals(asset_symbol):
    """API endpoint para sinais de trading de um asset específico"""
    try:
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 100)
        
        analyzer = current_app.multi_asset_manager.get_asset_analyzer(asset_symbol)
        if not analyzer:
            return jsonify({'error': f'Analyzer para {asset_symbol} não encontrado'}), 404
        
        # Obter análise completa para sinais ativos
        analysis = analyzer.get_comprehensive_analysis()
        active_signals = analysis.get('active_signals', [])
        
        # Obter sinais recentes do histórico
        all_signals = analyzer.signals if hasattr(analyzer, 'signals') else []
        recent_signals = sorted(all_signals, key=lambda x: x.get('created_at', ''), reverse=True)[:limit]
        
        return jsonify({
            'asset_symbol': asset_symbol,
            'active_signals': active_signals,
            'recent_signals': recent_signals,
            'total_signals': len(all_signals),
            'system_health': analysis.get('system_health', {})
        })
    except Exception as e:
        logger.error(f"Erro ao obter sinais do {asset_symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@multi_asset_bp.route('/api/asset/<asset_symbol>/performance')
def get_asset_performance(asset_symbol):
    """API endpoint para performance de trading de um asset específico"""
    try:
        days = request.args.get('days', 30, type=int)
        days = min(days, 365)  # Cap at 1 year
        
        analyzer = current_app.multi_asset_manager.get_asset_analyzer(asset_symbol)
        if not analyzer:
            return jsonify({'error': f'Analyzer para {asset_symbol} não encontrado'}), 404
        
        performance = analyzer.get_performance_report(days)
        performance['asset_symbol'] = asset_symbol
        return jsonify(performance)
    except Exception as e:
        logger.error(f"Erro ao obter performance do {asset_symbol}: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== CONSOLIDATED DATA ROUTES ====================

@multi_asset_bp.route('/api/consolidated/signals')
def get_consolidated_signals():
    """API endpoint para sinais consolidados de todos os assets"""
    try:
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 200)
        
        consolidated_signals = current_app.multi_asset_manager.get_consolidated_signals(limit)
        return jsonify({
            'consolidated_signals': consolidated_signals,
            'total_count': len(consolidated_signals),
            'assets_included': list(set(signal.get('asset_symbol') for signal in consolidated_signals))
        })
    except Exception as e:
        logger.error(f"Erro ao obter sinais consolidados: {e}")
        return jsonify({'error': str(e)}), 500

@multi_asset_bp.route('/api/consolidated/performance')
def get_consolidated_performance():
    """API endpoint para comparação de performance entre assets"""
    try:
        days = request.args.get('days', 30, type=int)
        days = min(days, 365)
        
        performance_comparison = {}
        
        for asset_symbol in app_config.get_supported_asset_symbols():
            analyzer = current_app.multi_asset_manager.get_asset_analyzer(asset_symbol)
            if analyzer:
                try:
                    performance = analyzer.get_performance_report(days)
                    performance_comparison[asset_symbol] = {
                        'asset_name': app_config.get_asset_config(asset_symbol)['name'],
                        'win_rate': performance.get('overall_performance', {}).get('win_rate', 0),
                        'total_trades': performance.get('overall_performance', {}).get('closed_trades', 0),
                        'net_profit': performance.get('overall_performance', {}).get('net_profit_pct', 0),
                        'profit_factor': performance.get('overall_performance', {}).get('profit_factor', 0)
                    }
                except Exception as e:
                    logger.debug(f"Performance não disponível para {asset_symbol}: {e}")
                    performance_comparison[asset_symbol] = {
                        'asset_name': app_config.get_asset_config(asset_symbol)['name'],
                        'error': 'Dados insuficientes'
                    }
        
        return jsonify({
            'performance_comparison': performance_comparison,
            'period_days': days,
            'timestamp': current_app.datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Erro ao obter performance consolidada: {e}")
        return jsonify({'error': str(e)}), 500

@multi_asset_bp.route('/api/consolidated/prices')
def get_consolidated_prices():
    """API endpoint para preços atuais de todos os assets"""
    try:
        prices = {}
        
        for asset_symbol in app_config.get_supported_asset_symbols():
            streamer = current_app.multi_asset_manager.get_asset_streamer(asset_symbol)
            if streamer:
                stats = streamer.get_stream_statistics()
                prices[asset_symbol] = {
                    'current_price': stats['last_price'],
                    'is_streaming': stats['is_running'],
                    'last_update': stats['last_fetch_time_iso'],
                    'data_points': stats['total_data_points'],
                    'asset_config': stats['asset_config']
                }
        
        return jsonify({
            'prices': prices,
            'timestamp': current_app.datetime.now().isoformat(),
            'total_assets': len(prices)
        })
    except Exception as e:
        logger.error(f"Erro ao obter preços consolidados: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== CONTROL ROUTES ====================

@multi_asset_bp.route('/api/control/start', methods=['POST'])
def start_multi_asset_streaming():
    """API endpoint para iniciar streaming de assets específicos"""
    try:
        data = request.get_json() or {}
        assets = data.get('assets')  # Lista de assets ou None para todos
        
        # Validar assets se especificados
        if assets:
            invalid_assets = [asset for asset in assets if not app_config.is_asset_supported(asset)]
            if invalid_assets:
                return jsonify({
                    'status': 'error',
                    'message': f'Assets não suportados: {", ".join(invalid_assets)}',
                    'supported_assets': app_config.get_supported_asset_symbols()
                }), 400
        
        current_app.multi_asset_manager.start_streaming(assets)
        
        assets_str = ', '.join(assets) if assets else 'todos os assets'
        logger.info(f"[MULTI] Streaming iniciado para: {assets_str}")
        
        return jsonify({
            'status': 'started',
            'message': f'Multi-asset streaming iniciado para: {assets_str}',
            'assets': assets or app_config.get_supported_asset_symbols()
        })
    except Exception as e:
        logger.error(f"Erro ao iniciar multi-asset streaming: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@multi_asset_bp.route('/api/control/stop', methods=['POST'])
def stop_multi_asset_streaming():
    """API endpoint para parar streaming de assets específicos"""
    try:
        data = request.get_json() or {}
        assets = data.get('assets')  # Lista de assets ou None para todos
        
        current_app.multi_asset_manager.stop_streaming(assets)
        
        assets_str = ', '.join(assets) if assets else 'todos os assets'
        logger.info(f"[MULTI] Streaming parado para: {assets_str}")
        
        return jsonify({
            'status': 'stopped',
            'message': f'Multi-asset streaming parado para: {assets_str}',
            'assets': assets or app_config.get_supported_asset_symbols()
        })
    except Exception as e:
        logger.error(f"Erro ao parar multi-asset streaming: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@multi_asset_bp.route('/api/control/restart-asset', methods=['POST'])
def restart_asset_streaming():
    """API endpoint para reiniciar streaming de um asset específico"""
    try:
        data = request.get_json() or {}
        asset_symbol = data.get('asset_symbol')
        
        if not asset_symbol:
            return jsonify({'status': 'error', 'message': 'asset_symbol é obrigatório'}), 400
        
        if not app_config.is_asset_supported(asset_symbol):
            return jsonify({
                'status': 'error',
                'message': f'Asset {asset_symbol} não suportado',
                'supported_assets': app_config.get_supported_asset_symbols()
            }), 400
        
        # Parar e reiniciar
        current_app.multi_asset_manager.stop_streaming([asset_symbol])
        current_app.multi_asset_manager.start_streaming([asset_symbol])
        
        logger.info(f"[MULTI] Asset {asset_symbol} reiniciado")
        
        return jsonify({
            'status': 'restarted',
            'message': f'Asset {asset_symbol} reiniciado com sucesso',
            'asset_symbol': asset_symbol
        })
    except Exception as e:
        logger.error(f"Erro ao reiniciar asset {asset_symbol}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@multi_asset_bp.route('/api/control/save-state', methods=['POST'])
def save_multi_asset_state():
    """API endpoint para forçar salvamento de estado de todos os analyzers"""
    try:
        saved_assets = []
        errors = {}
        
        for asset_symbol in app_config.get_supported_asset_symbols():
            analyzer = current_app.multi_asset_manager.get_asset_analyzer(asset_symbol)
            if analyzer:
                try:
                    analyzer.save_analyzer_state()
                    saved_assets.append(asset_symbol)
                except Exception as e:
                    errors[asset_symbol] = str(e)
        
        logger.info(f"[MULTI] Estado salvo para assets: {', '.join(saved_assets)}")
        
        response = {
            'status': 'success',
            'message': f'Estado salvo para {len(saved_assets)} assets',
            'saved_assets': saved_assets
        }
        
        if errors:
            response['errors'] = errors
            response['status'] = 'partial'
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"Erro ao salvar estado multi-asset: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== ANALYTICS & COMPARISON ROUTES ====================

@multi_asset_bp.route('/api/analytics/correlation')
def get_correlation_analysis():
    """API endpoint para análise de correlação entre assets"""
    try:
        overview = current_app.multi_asset_manager.get_overview_data()
        correlations = overview.get('performance_comparison', {}).get('correlation_matrix', {})
        
        # Formatar correlações para visualização
        correlation_data = []
        for pair, correlation in correlations.items():
            asset1, asset2 = pair.split('_')
            correlation_data.append({
                'asset1': asset1,
                'asset2': asset2,
                'correlation': correlation,
                'correlation_strength': 'Strong' if abs(correlation) > 0.7 else 'Moderate' if abs(correlation) > 0.3 else 'Weak',
                'correlation_direction': 'Positive' if correlation > 0 else 'Negative'
            })
        
        return jsonify({
            'correlation_analysis': correlation_data,
            'timestamp': current_app.datetime.now().isoformat(),
            'total_pairs': len(correlation_data)
        })
    except Exception as e:
        logger.error(f"Erro ao obter análise de correlação: {e}")
        return jsonify({'error': str(e)}), 500

@multi_asset_bp.route('/api/analytics/market-overview')
def get_market_overview():
    """API endpoint para overview geral do mercado multi-asset"""
    try:
        overview = current_app.multi_asset_manager.get_overview_data()
        
        # Extrair dados principais para overview de mercado
        market_data = {
            'total_market_value': 0,
            'total_volume_24h': 0,
            'assets_performance': {},
            'market_sentiment': 'NEUTRAL',
            'active_opportunities': 0
        }
        
        total_positive_change = 0
        total_assets_with_data = 0
        
        for asset_symbol, asset_data in overview.get('assets', {}).items():
            if 'error' not in asset_data:
                streaming = asset_data.get('streaming', {})
                current_price = streaming.get('current_price', 0)
                
                if current_price > 0:
                    # Simular volume baseado no preço (dados reais viriam da API)
                    estimated_volume = current_price * 1000000  # Volume estimado
                    market_data['total_market_value'] += current_price
                    market_data['total_volume_24h'] += estimated_volume
                    
                    # Performance do asset
                    trading = asset_data.get('trading', {})
                    market_data['assets_performance'][asset_symbol] = {
                        'current_price': current_price,
                        'active_signals': trading.get('active_signals', 0),
                        'win_rate': trading.get('win_rate', 0),
                        'recommended_action': trading.get('current_analysis', {}).get('recommended_action', 'HOLD')
                    }
                    
                    # Para sentimento geral
                    action = trading.get('current_analysis', {}).get('recommended_action', 'HOLD')
                    if action == 'BUY':
                        total_positive_change += 1
                    elif action == 'SELL':
                        total_positive_change -= 1
                    
                    total_assets_with_data += 1
        
        # Determinar sentimento geral do mercado
        if total_assets_with_data > 0:
            sentiment_ratio = total_positive_change / total_assets_with_data
            if sentiment_ratio > 0.3:
                market_data['market_sentiment'] = 'BULLISH'
            elif sentiment_ratio < -0.3:
                market_data['market_sentiment'] = 'BEARISH'
            else:
                market_data['market_sentiment'] = 'NEUTRAL'
        
        # Contar oportunidades ativas (sinais ativos)
        market_data['active_opportunities'] = sum(
            asset.get('trading', {}).get('active_signals', 0) 
            for asset in overview.get('assets', {}).values() 
            if 'error' not in asset
        )
        
        return jsonify({
            'market_overview': market_data,
            'timestamp': overview.get('timestamp'),
            'data_quality': 'GOOD' if total_assets_with_data >= 2 else 'LIMITED'
        })
    except Exception as e:
        logger.error(f"Erro ao obter overview de mercado: {e}")
        return jsonify({'error': str(e)}), 500