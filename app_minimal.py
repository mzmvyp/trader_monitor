#!/usr/bin/env python3
# app_minimal.py - Versão mínima para debug

import sys
import os
import traceback
from datetime import datetime

print("[INIT] Iniciando app mínima...")

try:
    # Teste 1: Imports básicos
    print("[INIT] Testando imports básicos...")
    import sqlite3
    import threading
    import time
    from flask import Flask, jsonify, render_template
    print("[OK] Imports básicos funcionando")

    # Teste 2: Config
    print("[INIT] Testando config...")
    try:
        from config import app_config
        print(f"[OK] Config carregado - DATA_DIR: {app_config.DATA_DIR}")
    except Exception as e:
        print(f"[ERROR] Config failed: {e}")
        # Criar config mínimo inline
        class MinimalConfig:
            DATA_DIR = 'data'
            FLASK_DEBUG_MODE = True
            FLASK_PORT = 5000
            FLASK_HOST = '0.0.0.0'
        app_config = MinimalConfig()
        print("[OK] Config mínimo criado")

    # Teste 3: Logging
    print("[INIT] Testando logging...")
    try:
        from utils.logging_config import logger
        print("[OK] Logger carregado")
    except Exception as e:
        print(f"[ERROR] Logger failed: {e}")
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        print("[OK] Logger mínimo criado")

    # Teste 4: Diretórios
    print("[INIT] Criando diretórios...")
    os.makedirs(app_config.DATA_DIR, exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    print("[OK] Diretórios criados")

    # Teste 5: Flask App
    print("[INIT] Criando Flask app...")
    app = Flask(__name__)
    app.config['DEBUG'] = app_config.FLASK_DEBUG_MODE
    print("[OK] Flask app criada")

    # Teste 6: Routes básicas
    print("[INIT] Configurando routes...")
    
    @app.route('/')
    def index():
        return jsonify({
            'status': 'OK',
            'message': 'Sistema funcionando!',
            'timestamp': datetime.now().isoformat(),
            'version': 'minimal-debug'
        })

    @app.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'python_version': sys.version,
            'working_directory': os.getcwd(),
            'data_dir_exists': os.path.exists(app_config.DATA_DIR)
        })

    @app.route('/test-db')
    def test_db():
        try:
            # Teste simples de SQLite
            conn = sqlite3.connect(':memory:')
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE test (id INTEGER, name TEXT)')
            cursor.execute('INSERT INTO test VALUES (1, "teste")')
            cursor.execute('SELECT * FROM test')
            result = cursor.fetchone()
            conn.close()
            
            return jsonify({
                'database_test': 'OK',
                'result': result
            })
        except Exception as e:
            return jsonify({
                'database_test': 'FAILED',
                'error': str(e)
            }), 500

    print("[OK] Routes configuradas")

    # Teste 7: Verificar imports avançados (opcional)
    advanced_status = {}
    
    try:
        from models.bitcoin_data import BitcoinData
        advanced_status['bitcoin_data'] = 'OK'
    except Exception as e:
        advanced_status['bitcoin_data'] = f'ERROR: {str(e)}'

    try:
        from services.bitcoin_streamer import BitcoinDataStreamer
        advanced_status['bitcoin_streamer'] = 'OK'
    except Exception as e:
        advanced_status['bitcoin_streamer'] = f'ERROR: {str(e)}'

    try:
        from services.trading_analyzer import EnhancedTradingAnalyzer
        advanced_status['trading_analyzer'] = 'OK'
    except Exception as e:
        advanced_status['trading_analyzer'] = f'ERROR: {str(e)}'

    @app.route('/advanced-status')
    def advanced_status_route():
        return jsonify(advanced_status)

    # Iniciar servidor
    print("\n" + "="*60)
    print("[START] SISTEMA MÍNIMO PRONTO!")
    print("="*60)
    print(f"[INFO] Acesse: http://localhost:{app_config.FLASK_PORT}")
    print("[INFO] Endpoints disponíveis:")
    print(f"   - http://localhost:{app_config.FLASK_PORT}/")
    print(f"   - http://localhost:{app_config.FLASK_PORT}/health")
    print(f"   - http://localhost:{app_config.FLASK_PORT}/test-db")
    print(f"   - http://localhost:{app_config.FLASK_PORT}/advanced-status")
    print("\n[INFO] Use Ctrl+C para parar")
    print("="*60)

    # Informações de debug
    logger.info("Sistema mínimo iniciado com sucesso")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Advanced components status: {advanced_status}")

    app.run(
        debug=app_config.FLASK_DEBUG_MODE,
        port=app_config.FLASK_PORT,
        host=app_config.FLASK_HOST,
        threaded=True
    )

except KeyboardInterrupt:
    print("\n[STOP] Aplicação parada pelo usuário")
    sys.exit(0)

except Exception as e:
    print(f"\n[CRITICAL ERROR] Erro fatal durante inicialização:")
    print(f"Erro: {e}")
    print(f"Tipo: {type(e).__name__}")
    print("\nTraceback completo:")
    traceback.print_exc()
    
    print(f"\n[DEBUG INFO]")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Arquivos no diretório atual:")
    for item in os.listdir('.'):
        print(f"  - {item}")
    
    sys.exit(1)