# debug_multi_asset.py - Script de Diagnóstico para Multi-Asset

import os
import sys
import sqlite3
import threading
import time
from datetime import datetime
from utils.logging_config import logger

def test_config():
    """Testa a configuração"""
    print("=== TESTE DE CONFIGURAÇÃO ===")
    
    try:
        from config import app_config
        
        print(f"✅ Config carregado com sucesso")
        print(f"DATA_DIR: {app_config.DATA_DIR}")
        print(f"AUTO_START_STREAM: {app_config.AUTO_START_STREAM}")
        
        # Testar assets suportados
        assets = app_config.get_supported_asset_symbols()
        print(f"Assets suportados: {assets}")
        
        # Testar caminhos de banco para cada asset
        for asset in assets:
            try:
                stream_db = app_config.get_asset_db_path(asset, 'stream')
                trading_db = app_config.get_asset_db_path(asset, 'trading')
                print(f"  {asset}:")
                print(f"    Stream DB: {stream_db}")
                print(f"    Trading DB: {trading_db}")
                print(f"    Stream DB existe: {os.path.exists(stream_db)}")
                print(f"    Trading DB existe: {os.path.exists(trading_db)}")
                
                # Verificar se diretório existe
                os.makedirs(os.path.dirname(stream_db), exist_ok=True)
                os.makedirs(os.path.dirname(trading_db), exist_ok=True)
                
            except Exception as e:
                print(f"  ❌ Erro para {asset}: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no config: {e}")
        return False

def test_imports():
    """Testa imports necessários"""
    print("\n=== TESTE DE IMPORTS ===")
    
    imports_ok = True
    
    # Testar GenericAssetStreamer
    try:
        from services.generic_asset_streamer import GenericAssetStreamer
        print("✅ GenericAssetStreamer importado")
    except ImportError as e:
        print(f"❌ GenericAssetStreamer: {e}")
        imports_ok = False
    
    # Testar MultiAssetManager
    try:
        from services.multi_asset_manager import MultiAssetManager
        print("✅ MultiAssetManager importado")
    except ImportError as e:
        print(f"❌ MultiAssetManager: {e}")
        imports_ok = False
    
    # Testar EnhancedTradingAnalyzer
    try:
        from services.trading_analyzer import EnhancedTradingAnalyzer
        print("✅ EnhancedTradingAnalyzer importado")
    except ImportError as e:
        print(f"❌ EnhancedTradingAnalyzer: {e}")
        imports_ok = False
    
    return imports_ok

def test_database_creation():
    """Testa criação de bancos de dados"""
    print("\n=== TESTE DE CRIAÇÃO DE BANCOS ===")
    
    try:
        from config import app_config
        from database.setup import setup_bitcoin_stream_db, setup_trading_analyzer_db
        
        assets = app_config.get_supported_asset_symbols()
        
        for asset in assets:
            try:
                print(f"Testando {asset}...")
                
                # Setup stream database
                stream_db_path = app_config.get_asset_db_path(asset, 'stream')
                setup_bitcoin_stream_db(stream_db_path)
                print(f"  ✅ Stream DB criado: {stream_db_path}")
                
                # Setup trading database
                trading_db_path = app_config.get_asset_db_path(asset, 'trading')
                setup_trading_analyzer_db(trading_db_path)
                print(f"  ✅ Trading DB criado: {trading_db_path}")
                
                # Verificar se bancos foram criados corretamente
                if os.path.exists(stream_db_path) and os.path.exists(trading_db_path):
                    print(f"  ✅ {asset} bancos verificados")
                else:
                    print(f"  ❌ {asset} bancos não encontrados após criação")
                
            except Exception as e:
                print(f"  ❌ Erro criando bancos para {asset}: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro geral na criação de bancos: {e}")
        return False

def test_streamer_creation():
    """Testa criação de streamers"""
    print("\n=== TESTE DE CRIAÇÃO DE STREAMERS ===")
    
    try:
        from config import app_config
        from services.generic_asset_streamer import GenericAssetStreamer
        
        assets = app_config.get_supported_asset_symbols()
        streamers = {}
        
        for asset in assets:
            try:
                print(f"Criando streamer para {asset}...")
                
                streamer = GenericAssetStreamer(
                    asset_symbol=asset,
                    max_queue_size=app_config.MULTI_ASSET_MAX_QUEUE_SIZE,
                    fetch_interval=app_config.ASSET_INTERVALS.get(asset, 300)
                )
                
                streamers[asset] = streamer
                
                # Testar configuração do streamer
                stats = streamer.get_stream_statistics()
                print(f"  ✅ {asset} streamer criado")
                print(f"    Symbol: {streamer.binance_symbol}")
                print(f"    Interval: {streamer.fetch_interval}s")
                print(f"    Min Price: ${streamer.min_price}")
                print(f"    Max Price: ${streamer.max_price}")
                
            except Exception as e:
                print(f"  ❌ Erro criando streamer para {asset}: {e}")
        
        return streamers
        
    except Exception as e:
        print(f"❌ Erro geral na criação de streamers: {e}")
        return {}

def test_multi_asset_manager():
    """Testa MultiAssetManager"""
    print("\n=== TESTE DE MULTI ASSET MANAGER ===")
    
    try:
        from services.multi_asset_manager import MultiAssetManager
        
        print("Criando MultiAssetManager...")
        manager = MultiAssetManager()
        
        print("✅ MultiAssetManager criado")
        
        # Testar health
        health = manager.get_system_health()
        print(f"Sistema health: {health['overall_status']}")
        print(f"Assets no manager: {len(manager.supported_assets)}")
        
        # Testar streamers
        print("Streamers disponíveis:")
        for asset in manager.supported_assets:
            if asset in manager.streamers:
                print(f"  ✅ {asset}: streamer disponível")
            else:
                print(f"  ❌ {asset}: streamer não encontrado")
        
        # Testar analyzers
        print("Analyzers disponíveis:")
        for asset in manager.supported_assets:
            if asset in manager.analyzers:
                print(f"  ✅ {asset}: analyzer disponível")
            else:
                print(f"  ❌ {asset}: analyzer não encontrado")
        
        return manager
        
    except Exception as e:
        print(f"❌ Erro no MultiAssetManager: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_streaming(manager, duration=30):
    """Testa streaming por alguns segundos"""
    print(f"\n=== TESTE DE STREAMING ({duration}s) ===")
    
    if not manager:
        print("❌ Manager não disponível")
        return False
    
    try:
        # Iniciar streaming para todos os assets
        print("Iniciando streaming...")
        manager.start_streaming()
        
        # Aguardar e verificar dados
        for i in range(duration):
            time.sleep(1)
            
            if i % 10 == 0:  # A cada 10 segundos
                print(f"\n--- Status após {i}s ---")
                
                for asset in manager.supported_assets:
                    streamer = manager.streamers.get(asset)
                    if streamer:
                        stats = streamer.get_stream_statistics()
                        print(f"{asset}: Running={stats['is_running']}, "
                              f"Data={stats['total_data_points']}, "
                              f"Errors={stats['api_errors']}, "
                              f"Price=${stats['last_price'] or 0:.2f}")
                    else:
                        print(f"{asset}: Streamer não encontrado")
        
        # Parar streaming
        print("\nParando streaming...")
        manager.stop_streaming()
        
        # Verificar dados finais
        print("\n--- Status Final ---")
        overview = manager.get_overview_data()
        
        for asset, data in overview['assets'].items():
            if 'error' not in data:
                streaming = data.get('streaming', {})
                print(f"{asset}: {streaming.get('data_points', 0)} dados coletados")
            else:
                print(f"{asset}: ERRO - {data['error']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de streaming: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_database_contents():
    """Verifica conteúdo dos bancos de dados"""
    print("\n=== VERIFICAÇÃO DE CONTEÚDO DOS BANCOS ===")
    
    try:
        from config import app_config
        
        for asset in app_config.get_supported_asset_symbols():
            print(f"\n{asset}:")
            
            # Verificar stream database
            stream_db = app_config.get_asset_db_path(asset, 'stream')
            if os.path.exists(stream_db):
                try:
                    conn = sqlite3.connect(stream_db)
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT COUNT(*) FROM bitcoin_stream")
                    count = cursor.fetchone()[0]
                    print(f"  Stream DB: {count} registros")
                    
                    if count > 0:
                        cursor.execute("SELECT timestamp, price, source FROM bitcoin_stream ORDER BY timestamp DESC LIMIT 1")
                        latest = cursor.fetchone()
                        print(f"    Último: {latest[0]} - ${latest[1]:.2f} ({latest[2]})")
                    
                    conn.close()
                    
                except Exception as e:
                    print(f"  Stream DB erro: {e}")
            else:
                print(f"  Stream DB: não existe")
            
            # Verificar trading database
            trading_db = app_config.get_asset_db_path(asset, 'trading')
            if os.path.exists(trading_db):
                try:
                    conn = sqlite3.connect(trading_db)
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT COUNT(*) FROM price_history")
                    count = cursor.fetchone()[0]
                    print(f"  Trading DB: {count} registros")
                    
                    conn.close()
                    
                except Exception as e:
                    print(f"  Trading DB erro: {e}")
            else:
                print(f"  Trading DB: não existe")
    
    except Exception as e:
        print(f"❌ Erro verificando bancos: {e}")

def main():
    """Função principal de diagnóstico"""
    print("DIAGNÓSTICO MULTI-ASSET TRADING SYSTEM")
    print("=" * 50)
    
    # Testes sequenciais
    config_ok = test_config()
    imports_ok = test_imports()
    
    if config_ok and imports_ok:
        db_ok = test_database_creation()
        streamers = test_streamer_creation()
        manager = test_multi_asset_manager()
        
        if manager:
            print("\n🎯 TUDO OK! Testando streaming real...")
            test_streaming(manager, duration=60)  # 1 minuto de teste
        
        check_database_contents()
    else:
        print("\n❌ PROBLEMAS BÁSICOS ENCONTRADOS!")
        print("Corrija os erros de config/imports antes de continuar.")
    
    print("\n" + "=" * 50)
    print("DIAGNÓSTICO CONCLUÍDO")

if __name__ == "__main__":
    main()