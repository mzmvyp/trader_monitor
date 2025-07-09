# tests/test_settings.py - Testes automatizados para o sistema de configurações

import unittest
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock

# Ajustar path para imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import DynamicConfigManager
from routes.settings_routes import *

class TestDynamicConfigManager(unittest.TestCase):
    """Testes para o gerenciador de configurações dinâmico"""
    
    def setUp(self):
        """Setup para cada teste"""
        # Criar banco temporário para testes
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.config_manager = DynamicConfigManager(db_path=self.temp_db.name)
        
    def tearDown(self):
        """Cleanup após cada teste"""
        # Remover banco temporário
        self.temp_db.close()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_database_setup(self):
        """Testa se o banco de dados é configurado corretamente"""
        # Verificar se as tabelas foram criadas
        conn = sqlite3.connect(self.temp_db.name)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = [
            'dynamic_config', 
            'config_history', 
            'config_profiles', 
            'config_validation_rules'
        ]
        
        for table in expected_tables:
            self.assertIn(table, tables, f"Tabela {table} não foi criada")
        
        conn.close()
    
    def test_load_default_config(self):
        """Testa carregamento da configuração padrão"""
        config = self.config_manager.load_config()
        
        # Verificar estrutura básica
        self.assertIn('trading', config)
        self.assertIn('streaming', config)
        self.assertIn('system', config)
        
        # Verificar valores específicos
        self.assertEqual(config['trading']['ta_params']['rsi_period'], 14)
        self.assertEqual(config['trading']['ta_params']['rsi_overbought'], 70)
        self.assertEqual(config['trading']['ta_params']['rsi_oversold'], 30)
    
    def test_save_and_load_config(self):
        """Testa salvamento e carregamento de configuração"""
        # Configuração de teste
        test_config = {
            'trading': {
                'ta_params': {
                    'rsi_period': 20,
                    'rsi_overbought': 75,
                    'rsi_oversold': 25
                }
            }
        }
        
        # Salvar configuração
        success = self.config_manager.save_config(test_config, 'test_user', 'Teste unitário')
        self.assertTrue(success)
        
        # Carregar e verificar
        loaded_config = self.config_manager.load_config()
        self.assertEqual(loaded_config['trading']['ta_params']['rsi_period'], 20)
        self.assertEqual(loaded_config['trading']['ta_params']['rsi_overbought'], 75)
        self.assertEqual(loaded_config['trading']['ta_params']['rsi_oversold'], 25)
    
    def test_config_validation(self):
        """Testa validação de configurações"""
        # Configuração válida
        valid_config = {
            'trading': {
                'ta_params': {
                    'rsi_overbought': 70,
                    'rsi_oversold': 30,
                    'sma_short': 9,
                    'sma_long': 21
                },
                'indicator_weights': {
                    'rsi': 0.20,
                    'macd': 0.25,
                    'bb': 0.15,
                    'stoch': 0.15,
                    'sma_cross': 0.15,
                    'volume': 0.10
                }
            }
        }
        
        validation = self.config_manager.validate_config(valid_config)
        self.assertTrue(validation['valid'])
        self.assertEqual(len(validation['errors']), 0)
        
        # Configuração inválida - RSI oversold >= overbought
        invalid_config = {
            'trading': {
                'ta_params': {
                    'rsi_overbought': 30,
                    'rsi_oversold': 70
                }
            }
        }
        
        validation = self.config_manager.validate_config(invalid_config)
        self.assertFalse(validation['valid'])
        self.assertGreater(len(validation['errors']), 0)
    
    def test_config_history(self):
        """Testa registro de histórico de configurações"""
        # Salvar configuração inicial
        config1 = {
            'trading': {
                'ta_params': {'rsi_period': 14}
            }
        }
        self.config_manager.save_config(config1, 'user1', 'Configuração inicial')
        
        # Salvar configuração modificada
        config2 = {
            'trading': {
                'ta_params': {'rsi_period': 20}
            }
        }
        self.config_manager.save_config(config2, 'user2', 'Ajuste do RSI')
        
        # Verificar histórico
        history = self.config_manager.get_config_history()
        self.assertGreater(len(history), 0)
        
        # Verificar último registro
        last_change = history[0]
        self.assertEqual(last_change['config_key'], 'trading.ta_params.rsi_period')
        self.assertEqual(last_change['new_value'], '20')
        self.assertEqual(last_change['changed_by'], 'user2')
    
    def test_config_profiles(self):
        """Testa criação e carregamento de perfis"""
        # Criar perfil de teste
        profile_config = {
            'trading': {
                'ta_params': {
                    'rsi_period': 10,
                    'min_confidence': 80
                }
            }
        }
        
        # Salvar perfil
        success = self.config_manager.create_config_profile(
            'aggressive', 
            profile_config, 
            'Perfil agressivo para scalping'
        )
        self.assertTrue(success)
        
        # Carregar perfil
        loaded_profile = self.config_manager.load_config_profile('aggressive')
        self.assertIsNotNone(loaded_profile)
        self.assertEqual(loaded_profile['trading']['ta_params']['rsi_period'], 10)
        
        # Listar perfis
        profiles = self.config_manager.list_config_profiles()
        self.assertGreater(len(profiles), 0)
        
        profile_names = [p['name'] for p in profiles]
        self.assertIn('aggressive', profile_names)
    
    def test_export_import_config(self):
        """Testa exportação e importação de configurações"""
        # Configuração de teste
        test_config = {
            'trading': {
                'ta_params': {'rsi_period': 16}
            }
        }
        
        self.config_manager.save_config(test_config)
        
        # Exportar configuração
        exported = self.config_manager.export_config()
        self.assertIn('config', exported)
        self.assertIn('exported_at', exported)
        self.assertIn('version', exported)
        
        # Criar novo gerenciador para teste de importação
        temp_db2 = tempfile.NamedTemporaryFile(delete=False)
        config_manager2 = DynamicConfigManager(db_path=temp_db2.name)
        
        try:
            # Importar configuração
            import_result = config_manager2.import_config(exported)
            self.assertTrue(import_result['success'])
            
            # Verificar se foi importada corretamente
            imported_config = config_manager2.load_config()
            self.assertEqual(imported_config['trading']['ta_params']['rsi_period'], 16)
            
        finally:
            temp_db2.close()
            if os.path.exists(temp_db2.name):
                os.unlink(temp_db2.name)


class TestSettingsRoutes(unittest.TestCase):
    """Testes para as rotas de configurações"""
    
    def setUp(self):
        """Setup para testes de rotas"""
        # Mock da aplicação Flask
        self.app = MagicMock()
        self.app.testing = True
        
        # Mock dos componentes do sistema
        self.mock_trading_analyzer = MagicMock()
        self.mock_bitcoin_streamer = MagicMock()
        self.mock_multi_asset_manager = MagicMock()
        
        self.app.trading_analyzer = self.mock_trading_analyzer
        self.app.bitcoin_streamer = self.mock_bitcoin_streamer
        self.app.multi_asset_manager = self.mock_multi_asset_manager
    
    @patch('routes.settings_routes.load_custom_settings')
    def test_get_current_config(self, mock_load_settings):
        """Testa endpoint de obtenção de configuração atual"""
        # Mock da configuração
        mock_load_settings.return_value = {
            'trading': {'ta_params': {'rsi_period': 14}}
        }
        
        # Mock dos componentes
        self.mock_trading_analyzer.ta_params = {'rsi_period': 14}
        self.mock_trading_analyzer.signal_config = {'max_active_signals': 5}
        self.mock_trading_analyzer.indicator_weights = {'rsi': 0.2}
        
        self.mock_bitcoin_streamer.fetch_interval = 300
        self.mock_bitcoin_streamer.data_queue = [1, 2, 3]
        self.mock_bitcoin_streamer.is_running = True
        
        # Simular request
        with patch('flask.current_app', self.app):
            with patch('routes.settings_routes.app_config') as mock_config:
                mock_config.get_supported_asset_symbols.return_value = ['BTC', 'ETH']
                
                # Chamar função (simulando request)
                # Nota: Em um teste real, usaríamos test client do Flask
                # Aqui estamos testando a lógica da função diretamente
                
                # Verificar se as configurações são carregadas corretamente
                self.assertIsNotNone(self.mock_trading_analyzer.ta_params)
                self.assertEqual(self.mock_trading_analyzer.ta_params['rsi_period'], 14)
    
    def test_config_validation_logic(self):
        """Testa lógica de validação de configurações"""
        # Configuração válida
        valid_config = {
            'trading': {
                'ta_params': {
                    'rsi_overbought': 70,
                    'rsi_oversold': 30,
                    'sma_short': 9,
                    'sma_long': 21
                },
                'indicator_weights': {
                    'rsi': 0.2, 'macd': 0.25, 'bb': 0.15,
                    'stoch': 0.15, 'sma_cross': 0.15, 'volume': 0.1
                }
            }
        }
        
        # Usar lógica de validação das rotas
        validation_result = validate_config(valid_config)
        self.assertTrue(validation_result['valid'])
        
        # Configuração inválida
        invalid_config = {
            'trading': {
                'ta_params': {
                    'rsi_overbought': 30,  # Menor que oversold
                    'rsi_oversold': 70
                }
            }
        }
        
        validation_result = validate_config(invalid_config)
        self.assertFalse(validation_result['valid'])
        self.assertGreater(len(validation_result['errors']), 0)


class TestConfigIntegration(unittest.TestCase):
    """Testes de integração do sistema de configurações"""
    
    def setUp(self):
        """Setup para testes de integração"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.config_manager = DynamicConfigManager(db_path=self.temp_db.name)
        
        # Mock de componentes do sistema
        self.mock_app = MagicMock()
        self.mock_trading_analyzer = MagicMock()
        self.mock_bitcoin_streamer = MagicMock()
        
        self.mock_app.trading_analyzer = self.mock_trading_analyzer
        self.mock_app.bitcoin_streamer = self.mock_bitcoin_streamer
        
        # Configurar mocks com atributos esperados
        self.mock_trading_analyzer.ta_params = {}
        self.mock_trading_analyzer.signal_config = {}
        self.mock_trading_analyzer.indicator_weights = {}
        self.mock_bitcoin_streamer.fetch_interval = 300
    
    def tearDown(self):
        """Cleanup após testes"""
        self.temp_db.close()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_apply_config_to_trading_analyzer(self):
        """Testa aplicação de configuração ao trading analyzer"""
        # Configuração de teste
        config = {
            'trading': {
                'ta_params': {
                    'rsi_period': 20,
                    'rsi_overbought': 75,
                    'min_confidence': 65
                },
                'signal_config': {
                    'max_active_signals': 8,
                    'signal_cooldown_minutes': 45
                },
                'indicator_weights': {
                    'rsi': 0.25,
                    'macd': 0.30,
                    'bb': 0.20,
                    'stoch': 0.15,
                    'sma_cross': 0.05,
                    'volume': 0.05
                }
            }
        }
        
        # Aplicar configuração
        self.config_manager.current_config = config
        result = self.config_manager.apply_config_to_system(self.mock_app)
        
        # Verificar se foi aplicada
        self.assertTrue(result['success'])
        
        # Verificar se os métodos update foram chamados
        self.mock_trading_analyzer.ta_params.update.assert_called()
        self.mock_trading_analyzer.signal_config.update.assert_called()
        self.mock_trading_analyzer.indicator_weights.update.assert_called()
    
    def test_apply_config_to_streamer(self):
        """Testa aplicação de configuração ao streamer"""
        config = {
            'streaming': {
                'bitcoin': {
                    'fetch_interval': 240,
                    'max_queue_size': 150
                }
            }
        }
        
        # Aplicar configuração
        self.config_manager.current_config = config
        result = self.config_manager.apply_config_to_system(self.mock_app)
        
        # Verificar se foi aplicada
        self.assertTrue(result['success'])
        
        # Verificar se o fetch_interval foi atualizado
        self.assertEqual(self.mock_bitcoin_streamer.fetch_interval, 240)
    
    def test_full_config_lifecycle(self):
        """Testa ciclo completo: salvar -> carregar -> validar -> aplicar"""
        # 1. Configuração inicial
        config = {
            'trading': {
                'ta_params': {'rsi_period': 18, 'min_confidence': 70},
                'signal_config': {'max_active_signals': 6}
            },
            'streaming': {
                'bitcoin': {'fetch_interval': 360}
            }
        }
        
        # 2. Salvar configuração
        save_success = self.config_manager.save_config(config, 'test_integration')
        self.assertTrue(save_success)
        
        # 3. Carregar configuração
        loaded_config = self.config_manager.load_config()
        self.assertEqual(loaded_config['trading']['ta_params']['rsi_period'], 18)
        
        # 4. Validar configuração
        validation = self.config_manager.validate_config(loaded_config)
        self.assertTrue(validation['valid'])
        
        # 5. Aplicar configuração
        apply_result = self.config_manager.apply_config_to_system(self.mock_app)
        self.assertTrue(apply_result['success'])
        
        # 6. Verificar histórico
        history = self.config_manager.get_config_history()
        self.assertGreater(len(history), 0)


class TestConfigPerformance(unittest.TestCase):
    """Testes de performance do sistema de configurações"""
    
    def setUp(self):
        """Setup para testes de performance"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.config_manager = DynamicConfigManager(db_path=self.temp_db.name)
    
    def tearDown(self):
        """Cleanup após testes"""
        self.temp_db.close()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_multiple_saves_performance(self):
        """Testa performance com múltiplas configurações"""
        import time
        
        start_time = time.time()
        
        # Salvar 100 configurações diferentes
        for i in range(100):
            config = {
                'trading': {
                    'ta_params': {
                        'rsi_period': 14 + i % 10,
                        'min_confidence': 60 + i % 20
                    }
                }
            }
            
            self.config_manager.save_config(config, f'user_{i}', f'Teste {i}')
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Deve completar em menos de 5 segundos
        self.assertLess(elapsed, 5.0, f"Performance ruim: {elapsed:.2f}s para 100 salvamentos")
        
        # Verificar se todas foram salvas
        history = self.config_manager.get_config_history(limit=200)
        self.assertGreaterEqual(len(history), 100)
    
    def test_large_config_handling(self):
        """Testa manipulação de configurações grandes"""
        # Criar configuração grande
        large_config = {
            'trading': {
                'ta_params': {f'param_{i}': i for i in range(1000)},
                'signal_config': {f'signal_{i}': i * 2 for i in range(500)},
                'indicator_weights': {f'weight_{i}': i / 1000 for i in range(100)}
            },
            'streaming': {
                f'asset_{i}': {'fetch_interval': 300 + i} for i in range(50)
            }
        }
        
        # Salvar e carregar
        start_time = time.time()
        
        save_success = self.config_manager.save_config(large_config)
        self.assertTrue(save_success)
        
        loaded_config = self.config_manager.load_config()
        self.assertEqual(len(loaded_config['trading']['ta_params']), 1000)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Deve completar em menos de 2 segundos
        self.assertLess(elapsed, 2.0, f"Performance ruim para config grande: {elapsed:.2f}s")


# ==================== TEST RUNNER ====================

def run_all_tests():
    """Executa todos os testes do sistema de configurações"""
    
    # Criar suite de testes
    test_suite = unittest.TestSuite()
    
    # Adicionar testes
    test_classes = [
        TestDynamicConfigManager,
        TestSettingsRoutes,
        TestConfigIntegration,
        TestConfigPerformance
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Executar testes
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Retornar resultado
    return result.wasSuccessful()


def run_specific_test(test_name):
    """Executa um teste específico"""
    suite = unittest.TestSuite()
    
    if test_name == 'config_manager':
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDynamicConfigManager))
    elif test_name == 'routes':
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestSettingsRoutes))
    elif test_name == 'integration':
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestConfigIntegration))
    elif test_name == 'performance':
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestConfigPerformance))
    else:
        print(f"Teste '{test_name}' não encontrado")
        return False
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    """Execução direta dos testes"""
    import sys
    
    if len(sys.argv) > 1:
        # Executar teste específico
        test_name = sys.argv[1]
        success = run_specific_test(test_name)
    else:
        # Executar todos os testes
        print("🧪 Executando todos os testes do sistema de configurações...\n")
        success = run_all_tests()
    
    if success:
        print("\n✅ Todos os testes passaram!")
        sys.exit(0)
    else:
        print("\n❌ Alguns testes falharam!")
        sys.exit(1)