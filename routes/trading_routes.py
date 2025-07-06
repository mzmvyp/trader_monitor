# your_project/routes/trading_routes.py - Versão com Enhanced Features

import sqlite3
from flask import Blueprint, jsonify, request, current_app, render_template
from utils.logging_config import logger

# Create a Blueprint for Trading-related routes
trading_bp = Blueprint('trading_routes', __name__, url_prefix='/trading')

@trading_bp.route('/')
def trading_dashboard():
    """Renders the Trading dashboard page."""
    return render_template('trading_dashboard.html')

# ==================== ENHANCED ANALYSIS ROUTES ====================

@trading_bp.route('/api/analysis')
def get_trading_analysis():
    """API endpoint para análise técnica completa e robusta"""
    try:
        # Usar o método get_comprehensive_analysis() do Enhanced Analyzer
        analysis = current_app.trading_analyzer.get_comprehensive_analysis()
        return jsonify(analysis)
    except Exception as e:
        logger.error(f"Erro ao obter análise de trading: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/performance-report')
def get_performance_report():
    """API endpoint para relatório detalhado de performance"""
    try:
        days = request.args.get('days', 30, type=int)
        report = current_app.trading_analyzer.get_performance_report(days)
        return jsonify(report)
    except Exception as e:
        logger.error(f"Erro ao obter relatório de performance: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/market-scanner')
def get_market_scanner():
    """API endpoint para scanner de mercado em tempo real"""
    try:
        scanner_data = current_app.trading_analyzer.get_market_scanner()
        return jsonify(scanner_data)
    except Exception as e:
        logger.error(f"Erro ao obter scanner de mercado: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/signals')
def get_trading_signals():
    """API endpoint para sinais de trading de alta qualidade"""
    try:
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 100)
        
        analysis = current_app.trading_analyzer.get_comprehensive_analysis()
        
        # Extrair sinais ativos e recentes
        active_signals = analysis.get('active_signals', [])
        all_signals = current_app.trading_analyzer.signals
        
        # Ordenar por data de criação (mais recentes primeiro)
        sorted_signals = sorted(all_signals, key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Retornar os últimos N sinais
        return jsonify({
            'active_signals': active_signals,
            'recent_signals': sorted_signals[:limit],
            'total_signals': len(all_signals),
            'system_health': analysis.get('system_health', {})
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter sinais de trading: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/active-signals')
def get_active_signals():
    """API endpoint para sinais ativos com informações detalhadas"""
    try:
        analysis = current_app.trading_analyzer.get_comprehensive_analysis()
        active_signals = analysis.get('active_signals', [])
        
        # Adicionar preço atual para cada sinal
        current_price = analysis.get('current_price', 0)
        
        for signal in active_signals:
            signal['current_price'] = current_price
            
            # Calcular progresso para targets múltiplos
            if 'targets' in signal and len(signal['targets']) > 0:
                entry = signal.get('entry', 0)
                target1 = signal['targets'][0]
                
                if entry and target1:
                    progress = ((current_price - entry) / (target1 - entry)) * 100
                    signal['progress_to_target1'] = max(0, min(100, progress))
        
        return jsonify({
            'active_signals': active_signals,
            'current_price': current_price,
            'market_state': analysis.get('market_analysis', {}),
            'signal_analysis': analysis.get('signal_analysis', {})
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter sinais ativos: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/pattern-stats')
def get_pattern_statistics():
    """API endpoint para estatísticas detalhadas de padrões"""
    try:
        report = current_app.trading_analyzer.get_performance_report(30)
        pattern_stats = report.get('signal_type_breakdown', {})
        
        # Formatar para visualização
        formatted_stats = []
        for pattern_type, stats in pattern_stats.items():
            formatted_stats.append({
                'pattern_type': pattern_type,
                'total_signals': stats.get('total_signals', 0),
                'win_rate': stats.get('win_rate', 0),
                'total_pnl': stats.get('total_pnl', 0),
                'avg_pnl': stats.get('avg_pnl', 0)
            })
        
        return jsonify({
            'pattern_stats': formatted_stats,
            'overall_performance': report.get('overall_performance', {})
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de padrões: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/indicators')
def get_current_indicators():
    """API endpoint para indicadores técnicos detalhados"""
    try:
        analysis = current_app.trading_analyzer.get_comprehensive_analysis()
        indicators = analysis.get('technical_indicators', {})
        
        # Adicionar interpretação para cada indicador
        enhanced_indicators = {}
        
        for key, value in indicators.items():
            enhanced_indicators[key] = {
                'value': value,
                'interpretation': get_indicator_interpretation(key, value),
                'signal': get_indicator_signal(key, value)
            }
        
        return jsonify({
            'indicators': enhanced_indicators,
            'market_analysis': analysis.get('market_analysis', {}),
            'timestamp': analysis.get('timestamp', '')
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter indicadores: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/system-status')
def get_system_status():
    """API endpoint para status completo do sistema Enhanced"""
    try:
        status = current_app.trading_analyzer.get_system_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Erro ao obter status do sistema: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/export-signals', methods=['POST'])
def export_signals():
    """API endpoint para exportar sinais em CSV"""
    try:
        filename = current_app.trading_analyzer.export_signals_to_csv()
        if filename:
            return jsonify({
                'status': 'success',
                'filename': filename,
                'message': f'Sinais exportados para {filename}'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Erro ao exportar sinais'
            }), 500
            
    except Exception as e:
        logger.error(f"Erro ao exportar sinais: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== HELPER FUNCTIONS ====================

def get_indicator_interpretation(indicator_name: str, value) -> str:
    """Interpreta o valor do indicador"""
    interpretations = {
        'RSI': lambda v: 'Oversold' if v < 30 else 'Overbought' if v > 70 else 'Neutral',
        'MACD_Histogram': lambda v: 'Bullish' if v > 0 else 'Bearish',
        'BB_Position': lambda v: 'Near Lower Band' if v < 0.2 else 'Near Upper Band' if v > 0.8 else 'Middle Range',
        'Stoch_K': lambda v: 'Oversold' if v < 20 else 'Overbought' if v > 80 else 'Neutral',
        'Volume_Ratio': lambda v: 'High Volume' if v > 1.5 else 'Low Volume' if v < 0.7 else 'Normal Volume',
        'Trend_Strength': lambda v: 'Strong Trend' if v > 0.7 else 'Weak Trend' if v < 0.3 else 'Moderate Trend'
    }
    
    if indicator_name in interpretations and value is not None:
        return interpretations[indicator_name](value)
    return 'N/A'

def get_indicator_signal(indicator_name: str, value) -> str:
    """Determina o sinal do indicador (buy/sell/neutral)"""
    if value is None:
        return 'neutral'
    
    signals = {
        'RSI': lambda v: 'buy' if v < 30 else 'sell' if v > 70 else 'neutral',
        'MACD_Histogram': lambda v: 'buy' if v > 0 else 'sell',
        'BB_Position': lambda v: 'buy' if v < 0.2 else 'sell' if v > 0.8 else 'neutral',
        'Stoch_K': lambda v: 'buy' if v < 20 else 'sell' if v > 80 else 'neutral',
    }
    
    if indicator_name in signals:
        return signals[indicator_name](value)
    return 'neutral'

# ==================== GLOBAL API ROUTES (mantendo compatibilidade) ====================

@trading_bp.route('/api/trading/analysis')
def get_trading_analysis_global():
    """Global API endpoint for trading analysis"""
    return get_trading_analysis()

@trading_bp.route('/api/trading/signals')
def get_trading_signals_global():
    """Global API endpoint for trading signals"""
    return get_trading_signals()

@trading_bp.route('/api/trading/active-signals')
def get_active_signals_global():
    """Global API endpoint for active signals"""
    return get_active_signals()

@trading_bp.route('/api/trading/pattern-stats')
def get_pattern_statistics_global():
    """Global API endpoint for pattern statistics"""
    return get_pattern_statistics()

@trading_bp.route('/api/trading/indicators')
def get_current_indicators_global():
    """Global API endpoint for indicators"""
    return get_current_indicators()

@trading_bp.route('/api/trading/scanner')
def get_market_scanner_global():
    """Global API endpoint for market scanner"""
    return get_market_scanner()

@trading_bp.route('/api/trading/performance')
def get_performance_report_global():
    """Global API endpoint for performance report"""
    return get_performance_report()

# ==================== CONTROL ROUTES ====================

@trading_bp.route('/api/control/cleanup', methods=['POST'])
def cleanup_data():
    """API endpoint para limpar dados antigos"""
    try:
        from config import app_config
        
        days_to_keep = request.json.get('days_to_keep', app_config.DEFAULT_DAYS_TO_KEEP_DATA) if request.json else app_config.DEFAULT_DAYS_TO_KEEP_DATA
        
        # Limpar dados de ambos os bancos
        conn_bitcoin = sqlite3.connect(app_config.BITCOIN_STREAM_DB)
        cursor_bitcoin = conn_bitcoin.cursor()
        
        cutoff_date = (current_app.datetime.now() - current_app.timedelta(days=days_to_keep)).isoformat()
        
        cursor_bitcoin.execute('DELETE FROM bitcoin_stream WHERE timestamp < ?', (cutoff_date,))
        deleted_bitcoin = cursor_bitcoin.rowcount
        
        cursor_bitcoin.execute('DELETE FROM bitcoin_analytics WHERE created_at < ?', (cutoff_date,))
        deleted_analytics = cursor_bitcoin.rowcount
        conn_bitcoin.commit()
        conn_bitcoin.close()
        
        # Limpar dados do trading analyzer
        conn_trading = sqlite3.connect(app_config.TRADING_ANALYZER_DB)
        cursor_trading = conn_trading.cursor()
        
        cursor_trading.execute('DELETE FROM price_history WHERE timestamp < ?', (cutoff_date,))
        deleted_price_history = cursor_trading.rowcount
        
        cursor_trading.execute('DELETE FROM trading_signals WHERE created_at < ? AND status != "ACTIVE"', (cutoff_date,))
        deleted_signals = cursor_trading.rowcount
        
        # Limpar também tabelas enhanced se existirem
        try:
            cursor_trading.execute('DELETE FROM enhanced_signals WHERE created_at < ? AND status != "ACTIVE"', (cutoff_date,))
            deleted_enhanced_signals = cursor_trading.rowcount
        except:
            deleted_enhanced_signals = 0
        
        conn_trading.commit()
        conn_trading.close()
        
        logger.info(f"[CLEAN] Limpeza concluída: {deleted_bitcoin} bitcoin, {deleted_analytics} analytics, "
                   f"{deleted_price_history} preços, {deleted_signals} sinais, {deleted_enhanced_signals} enhanced sinais.")
        
        return jsonify({
            'status': 'success',
            'deleted_bitcoin_records': deleted_bitcoin,
            'deleted_analytics_records': deleted_analytics,
            'deleted_price_history': deleted_price_history,
            'deleted_signals': deleted_signals,
            'deleted_enhanced_signals': deleted_enhanced_signals,
            'message': f'Dados anteriores a {days_to_keep} dias removidos.'
        })
        
    except Exception as e:
        logger.error(f"Erro na limpeza de dados: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@trading_bp.route('/api/control/reset-signals', methods=['POST'])
def reset_signals():
    """API endpoint para resetar todos os sinais"""
    try:
        current_app.trading_analyzer.reset_signals_and_state()
        logger.info("[FIX] Sistema de sinais resetado via API.")
        return jsonify({'status': 'success', 'message': 'Sistema de sinais resetado'})
        
    except Exception as e:
        logger.error(f"Erro ao resetar sinais: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@trading_bp.route('/api/control/force-save', methods=['POST'])
def force_save():
    """API endpoint para forçar salvamento do estado"""
    try:
        current_app.trading_analyzer.save_analyzer_state()
        current_app.bitcoin_processor.force_process_batch()
        
        logger.info("[FIX] Estado salvo manualmente via API.")
        return jsonify({'status': 'success', 'message': 'Estado salvo com sucesso'})
        
    except Exception as e:
        logger.error(f"Erro ao salvar estado: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500