# migration_and_test.py
# Script para migrar e testar os novos padrões avançados

import os
import sys
import sqlite3
import requests
import time
from datetime import datetime
import json

def create_backup():
    """Cria backup dos bancos de dados existentes"""
    print("🔄 Criando backup dos bancos de dados...")
    
    backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Backup dos bancos existentes
    db_files = [
        'data/trading_analyzer.db',
        'data/bitcoin_stream.db'
    ]
    
    for db_file in db_files:
        if os.path.exists(db_file):
            backup_path = os.path.join(backup_dir, os.path.basename(db_file))
            os.system(f"cp {db_file} {backup_path}")
            print(f"✅ Backup criado: {backup_path}")
    
    return backup_dir

def check_dependencies():
    """Verifica se todas as dependências estão instaladas"""
    print("🔍 Verificando dependências...")
    
    required_packages = ['numpy', 'flask', 'requests', 'sqlite3']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} - OK")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} - FALTANDO")
    
    if missing_packages:
        print(f"\n⚠️ Instale as dependências faltantes:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def create_advanced_pattern_files():
    """Cria os arquivos necessários para os padrões avançados"""
    print("📁 Criando arquivos de padrões avançados...")
    
    # Verificar se os diretórios existem
    os.makedirs('services', exist_ok=True)
    
    # Criar arquivo advanced_pattern_analyzer.py
    if not os.path.exists('services/advanced_pattern_analyzer.py'):
        print("✅ Arquivo advanced_pattern_analyzer.py deve ser criado manualmente")
        print("   Use o código fornecido no artifact 'advanced_pattern_analyzer'")
    else:
        print("✅ advanced_pattern_analyzer.py já existe")
    
    # Criar arquivo enhanced_trading_analyzer_v2.py
    if not os.path.exists('services/enhanced_trading_analyzer_v2.py'):
        print("✅ Arquivo enhanced_trading_analyzer_v2.py deve ser criado manualmente")
        print("   Use o código fornecido no artifact 'advanced_patterns_integration'")
    else:
        print("✅ enhanced_trading_analyzer_v2.py já existe")

def test_database_migration():
    """Testa se a migração do banco de dados funcionou"""
    print("🗄️ Testando migração do banco de dados...")
    
    try:
        # Verificar se as novas tabelas foram criadas
        conn = sqlite3.connect('data/trading_analyzer.db')
        cursor = conn.cursor()
        
        # Verificar tabelas existentes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = [
            'advanced_patterns',
            'method_performance', 
            'elliott_waves',
            'signal_methods_performance'
        ]
        
        for table in expected_tables:
            if table in tables:
                print(f"✅ Tabela {table} criada")
            else:
                print(f"❌ Tabela {table} FALTANDO")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro na verificação do banco: {e}")
        return False

def test_api_endpoints():
    """Testa os novos endpoints da API"""
    print("🌐 Testando novos endpoints da API...")
    
    base_url = "http://localhost:5000"
    
    endpoints = [
        "/trading/api/patterns/elliott-waves",
        "/trading/api/patterns/double-bottom", 
        "/trading/api/patterns/oco",
        "/trading/api/patterns/ocoi",
        "/trading/api/patterns/all-patterns",
        "/trading/api/patterns/performance",
        "/trading/api/patterns/comparison",
        "/trading/api/patterns/summary"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {endpoint} - OK")
            elif response.status_code == 503:
                print(f"⚠️ {endpoint} - Serviço não disponível (normal se sistema não estiver rodando)")
            else:
                print(f"❌ {endpoint} - Erro {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"🔌 {endpoint} - Servidor não conectado (normal se sistema parado)")
        except Exception as e:
            print(f"❌ {endpoint} - Erro: {e}")

def generate_test_data():
    """Gera dados de teste para verificar os padrões"""
    print("📊 Gerando dados de teste...")
    
    try:
        # Importar o analisador avançado
        sys.path.append('.')
        from services.advanced_pattern_analyzer import AdvancedPatternAnalyzer
        
        analyzer = AdvancedPatternAnalyzer()
        
        # Gerar série de preços simulando padrões
        base_price = 43000
        
        # Simular ondas de Elliott (5 ondas)
        elliott_prices = [
            43000,  # Início
            44000,  # Onda 1 alta
            43500,  # Onda 2 correção
            45000,  # Onda 3 alta (maior)
            44200,  # Onda 4 correção
            45500,  # Onda 5 alta
            44800,  # Início correção
            44000,  # Correção A
            44400,  # Correção B
            43600   # Correção C
        ]
        
        # Simular fundo duplo
        double_bottom_prices = [
            43000, 42800, 42500, 42500, 42800, 43200, 43000, 42600, 42500, 42900, 43400
        ]
        
        print("✅ Dados de teste preparados")
        print(f"   Elliott Wave pattern: {len(elliott_prices)} pontos")
        print(f"   Double Bottom pattern: {len(double_bottom_prices)} pontos")
        
        return True
        
    except ImportError as e:
        print(f"❌ Erro ao importar analisador: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro ao gerar dados: {e}")
        return False

def check_system_status():
    """Verifica se o sistema está rodando e funcionando"""
    print("⚡ Verificando status do sistema...")
    
    try:
        response = requests.get("http://localhost:5000/api/integrated/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Sistema rodando")
            
            # Verificar se há dados sendo coletados
            if data.get('bitcoin', {}).get('stats', {}).get('total_data_points', 0) > 0:
                print(f"✅ Coletando dados: {data['bitcoin']['stats']['total_data_points']} pontos")
            else:
                print("⚠️ Nenhum dado coletado ainda")
            
            # Verificar trading analyzer
            if data.get('trading', {}).get('system_info', {}).get('analysis_count', 0) > 0:
                print(f"✅ Analyzer ativo: {data['trading']['system_info']['analysis_count']} análises")
            else:
                print("⚠️ Analyzer não ativo")
            
            return True
            
    except requests.exceptions.ConnectionError:
        print("🔌 Sistema não está rodando")
        print("   Execute: python app.py")
        return False
    except Exception as e:
        print(f"❌ Erro ao verificar sistema: {e}")
        return False

def main():
    """Função principal do script de migração"""
    print("🚀 MIGRAÇÃO PARA PADRÕES AVANÇADOS")
    print("=" * 50)
    
    # 1. Criar backup
    backup_dir = create_backup()
    
    # 2. Verificar dependências
    if not check_dependencies():
        print("\n❌ Dependências faltando. Instale antes de continuar.")
        return
    
    # 3. Criar arquivos necessários
    create_advanced_pattern_files()
    
    # 4. Verificar se sistema está rodando
    system_running = check_system_status()
    
    if system_running:
        print("\n⚠️ Sistema está rodando. Pare o sistema antes de continuar a migração.")
        print("   Pressione Ctrl+C no terminal onde o sistema está rodando")
        input("   Pressione Enter quando o sistema estiver parado...")
    
    # 5. Testar migração do banco
    print("\n📋 CHECKLIST DE MIGRAÇÃO:")
    print("1. ✅ Backup criado")
    print("2. ✅ Dependências verificadas") 
    print("3. 📁 Arquivos criados (verifique manualmente)")
    print("4. 🗄️ Banco de dados (testar após reiniciar sistema)")
    
    print(f"\n📁 Backup salvo em: {backup_dir}")
    print("\n🔄 PRÓXIMOS PASSOS:")
    print("1. Copie o código dos artifacts para os arquivos mencionados")
    print("2. Modifique app.py para usar EnhancedTradingAnalyzerV2")
    print("3. Adicione as novas rotas ao trading_routes.py")
    print("4. Reinicie o sistema: python app.py")
    print("5. Execute este script novamente para testar: python migration_and_test.py --test")

def test_mode():
    """Modo de teste após migração"""
    print("🧪 MODO DE TESTE - PADRÕES AVANÇADOS")
    print("=" * 50)
    
    # Verificar sistema
    if not check_system_status():
        return
    
    # Testar banco de dados
    test_database_migration()
    
    # Testar APIs
    test_api_endpoints()
    
    # Gerar dados de teste
    generate_test_data()
    
    print("\n✅ TESTE CONCLUÍDO")
    print("Verifique os logs para ver se os padrões estão sendo detectados:")
    print("tail -f data/trading_system.log | grep -E '(ELLIOTT|DOUBLE_BOTTOM|OCO|OCOI)'")

if __name__ == "__main__":
    if "--test" in sys.argv:
        test_mode()
    else:
        main()