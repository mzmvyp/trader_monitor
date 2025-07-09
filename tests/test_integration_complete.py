# tests/test_integration_complete.py - Testes de integração do sistema completo

import unittest
import json
import os
import tempfile
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, Mock
import sqlite3

# Ajustar path para imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Imports do sistema
from config_manager import DynamicConfigManager
from middleware.config_middleware import ConfigurationMiddleware
from services.notification_service import NotificationService
from services.backup_service import BackupService


class TestCompleteSystemIntegration(unittest.TestCase):
    """Testes de integração do sistema completo"""
    
    def setUp(self):
        """Setup completo para testes de integração"""
        # Criar diretórios temporários
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.temp_dir, 'data')
        self.backup_dir = os.path.join(self.temp_dir, 'backups')
        
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Inicializar componentes
        self.config_manager = DynamicConfigManager(
            db_path=os.path.join(self.data_dir, 'test_config.db')
        )
        
        self.config_middleware = ConfigurationMiddleware()
        
        self.notification_service = NotificationService()
        self.notification_service.config = {
            'email': {'enabled': False},
            'webhook': {'enabled': False},
            'slack': {'enabled': False},
            'discord': {'enabled': False},
            'telegram': {'enabled': False}
        }
        
        self.backup_service = BackupService(backup_dir=self.backup_dir)
        self.backup_service.config['auto_backup_enabled'] = False  # Não queremos backups automáticos nos testes
        
        # Mock da aplicação
        self.mock_app = self._create_mock_app()
        self.config_middleware.register_app_instance(self.mock_app)
        
        # Lista para capturar notificações
        self.sent_notifications = []
        
        # Override do método de envio para capturar notificações
        original_send = self.notification_service.send_notification
        def capture_notification(*args, **kwargs):
            result = original_send(*args, **kwargs)
            self.sent_notifications.append({
                'args': args,
                'kwargs': kwargs,
                'result': result
            })
            return result
        
        self.notification_service.send_notification = capture_notification
    
    def tearDown(self):
        """Cleanup após testes"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_mock_app(self):
        """Cria mock da aplicação Flask"""
        mock_app = Mock()
        
        # Mock trading analyzer
        mock_trading_analyzer = Mock()
        mock_trading_analyzer.ta_params = {}
        mock_trading_analyzer.signal_config = {}
        mock_trading_analyzer.indicator_weights = {}
        mock_trading_analyzer.get_system_status.return_value = {'status': 'ok'}
        
        # Mock bitcoin streamer
        mock_bitcoin_streamer = Mock()
        mock_bitcoin_streamer.fetch_interval = 300
        mock_bitcoin_streamer.get_stream_statistics.return_value = {
            'is_running': True,
            'api_errors': 0,
            'total_data_points': 100
        }
        
        mock_app.trading_analyzer = mock_trading_analyzer
        mock_app.bitcoin_streamer = mock_bitcoin_streamer
        
        return mock_app
    
    def test_config_change_flow_complete(self):
        """Testa fluxo completo de mudança de configuração"""
        print("\n=== Testando Fluxo Completo de Mudança de Configuração ===")
        
        # 1. Configuração inicial
        initial_config = {
            'trading': {
                'ta_params': {
                    'rsi_period': 14,
                    'rsi_overbought': 70,
                    'rsi_oversold': 30
                },
                'indicator_weights': {
                    'rsi': 0.2,
                    'macd': 0.25,
                    'bb': 0.15,
                    'stoch': 0.15,
                    'sma_cross': 0.15,
                    'volume': 0.1
                }
            }
        }
        
        # Salvar configuração inicial
        success = self.config_manager.save_config(initial_config, 'test_user', 'Configuração inicial')
        self.assertTrue(success)
        
        # 2. Modificar configuração via middleware
        modified_config = initial_config.copy()
        modified_config['trading']['ta_params']['rsi_period'] = 20
        modified_config['trading']['ta_params']['min_confidence'] = 65
        
        # Registrar callback para verificar notificação
        notification_received = threading.Event()
        
        def config_change_callback(old_config, new_config):
            notification_received.set()
        
        self.config_middleware.add_config_change_callback(config_change_callback)
        
        # Aplicar mudança via middleware
        result = self.config_middleware.intercept_config_change(
            modified_config,
            'integration_test',
            apply_immediately=True
        )
        
        # Verificar que mudança foi aplicada
        self.assertTrue(result['success'])
        self.assertIn('applied_components', result)
        
        # Verificar que callback foi chamado
        self.assertTrue(notification_received.wait(timeout=1))
        
        # 3. Verificar se configuração foi persistida
        loaded_config = self.config_manager.load_config()
        self.assertEqual(loaded_config['trading']['ta_params']['rsi_period'], 20)
        self.assertEqual(loaded_config['trading']['ta_params']['min_confidence'], 65)
        
        # 4. Verificar histórico de mudanças
        history = self.config_manager.get_config_history(limit=5)
        self.assertGreater(len(history), 0)
        
        # Verificar que mudanças específicas estão no histórico
        rsi_changes = [h for h in history if 'rsi_period' in h['config_key']]
        self.assertGreater(len(rsi_changes), 0)
        
        print("✅ Fluxo de mudança de configuração completado com sucesso")
    
    def test_notification_integration(self):
        """Testa integração do sistema de notificações"""
        print("\n=== Testando Integração de Notificações ===")
        
        # Limpar notificações anteriores
        self.sent_notifications.clear()
        
        # 1. Enviar notificação de teste
        result = self.notification_service.send_notification(
            'CONFIG_CHANGED',
            'Teste de Configuração',
            'Esta é uma notificação de teste',
            {'test_data': 'valor_teste'}
        )
        
        # Verificar que notificação foi "enviada" (capturada)
        self.assertEqual(len(self.sent_notifications), 1)
        
        notification = self.sent_notifications[0]
        self.assertEqual(notification['args'][0], 'CONFIG_CHANGED')
        self.assertEqual(notification['args'][1], 'Teste de Configuração')
        
        # 2. Verificar histórico de notificações
        history = self.notification_service.get_notification_history(limit=10)
        self.assertGreater(len(history), 0)
        
        last_notification = history[0]
        self.assertEqual(last_notification['type'], 'CONFIG_CHANGED')
        self.assertEqual(last_notification['title'], 'Teste de Configuração')
        
        # 3. Verificar estatísticas
        stats = self.notification_service.get_notification_stats()
        self.assertGreater(stats['total_notifications'], 0)
        
        print("✅ Sistema de notificações funcionando corretamente")
    
    def test_backup_system_integration(self):
        """Testa integração do sistema de backup"""
        print("\n=== Testando Sistema de Backup ===")
        
        # 1. Criar alguns arquivos de teste para backup
        test_db_file = os.path.join(self.data_dir, 'test_trading.db')
        with sqlite3.connect(test_db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE test_data (id INTEGER, value TEXT)')
            cursor.execute('INSERT INTO test_data VALUES (1, "test_value")')
            conn.commit()
        
        # Mock dos caminhos de banco de dados
        original_collect_db = self.backup_service._collect_database_files
        
        def mock_collect_db():
            return [{
                'source': test_db_file,
                'relative_path': 'databases/test_trading.db'
            }]
        
        self.backup_service._collect_database_files = mock_collect_db
        
        # 2. Criar backup
        backup_result = self.backup_service.create_backup(
            backup_type='integration_test',
            include_databases=True,
            include_configs=False,
            include_logs=False
        )
        
        # Verificar que backup foi criado
        self.assertTrue(backup_result['success'])
        self.assertIn('backup_file', backup_result)
        self.assertGreater(backup_result['size_bytes'], 0)
        
        backup_file = backup_result['backup_file']
        self.assertTrue(os.path.exists(backup_file))
        
        # 3. Listar backups
        backups = self.backup_service.list_backups(backup_type='integration_test')
        self.assertGreater(len(backups), 0)
        
        created_backup = backups[0]
        self.assertEqual(created_backup['backup_type'], 'integration_test')
        self.assertTrue(created_backup['file_exists'])
        
        # 4. Verificar estatísticas
        stats = self.backup_service.get_backup_stats()
        self.assertGreater(stats['total_backups'], 0)
        self.assertGreater(stats['successful_backups'], 0)
        
        print("✅ Sistema de backup funcionando corretamente")
    
    def test_config_validation_integration(self):
        """Testa integração do sistema de validação"""
        print("\n=== Testando Sistema de Validação ===")
        
        # 1. Configuração válida
        valid_config = {
            'trading': {
                'ta_params': {
                    'rsi_period': 14,
                    'rsi_overbought': 70,
                    'rsi_oversold': 30,
                    'sma_short': 9,
                    'sma_long': 21
                },
                'indicator_weights': {
                    'rsi': 0.2,
                    'macd': 0.25,
                    'bb': 0.15,
                    'stoch': 0.15,
                    'sma_cross': 0.15,
                    'volume': 0.1
                }
            }
        }
        
        validation = self.config_manager.validate_config(valid_config)
        self.assertTrue(validation['valid'])
        self.assertEqual(len(validation['errors']), 0)
        
        # 2. Configuração inválida
        invalid_config = {
            'trading': {
                'ta_params': {
                    'rsi_overbought': 30,  # Menor que oversold
                    'rsi_oversold': 70,
                    'sma_short': 21,  # Maior que longa
                    'sma_long': 9
                },
                'indicator_weights': {
                    'rsi': 0.5,  # Soma dos pesos > 1.0
                    'macd': 0.6,
                    'bb': 0.1,
                    'stoch': 0.1,
                    'sma_cross': 0.1,
                    'volume': 0.1
                }
            }
        }
        
        validation = self.config_manager.validate_config(invalid_config)
        self.assertFalse(validation['valid'])
        self.assertGreater(len(validation['errors']), 0)
        
        # Verificar erros específicos
        error_messages = ' '.join(validation['errors'])
        self.assertIn('RSI', error_messages)
        self.assertIn('SMA', error_messages)
        self.assertIn('peso', error_messages.lower())
        
        # 3. Testar aplicação de configuração inválida via middleware
        result = self.config_middleware.intercept_config_change(
            invalid_config,
            'validation_test',
            apply_immediately=True
        )
        
        # Deve falhar na validação
        self.assertFalse(result['success'])
        self.assertIn('validation', result.get('error', '').lower())
        
        print("✅ Sistema de validação funcionando corretamente")
    
    def test_middleware_rollback_functionality(self):
        """Testa funcionalidade de rollback do middleware"""
        print("\n=== Testando Funcionalidade de Rollback ===")
        
        # 1. Configuração inicial válida
        initial_config = {
            'trading': {
                'ta_params': {
                    'rsi_period': 14,
                    'min_confidence': 60
                }
            }
        }
        
        self.config_manager.save_config(initial_config, 'rollback_test', 'Configuração inicial')
        
        # 2. Aplicar configuração via middleware
        self.config_middleware.intercept_config_change(
            initial_config,
            'rollback_initial',
            apply_immediately=True
        )
        
        # 3. Tentar aplicar configuração problemática
        problematic_config = {
            'trading': {
                'ta_params': {
                    'rsi_period': 14,
                    'min_confidence': 60
                }
            }
        }
        
        # Simular problema na aplicação
        original_apply = self.config_middleware._apply_config_safely
        
        def failing_apply(new_config, old_config):
            return {'success': False, 'error': 'Simulated application failure'}
        
        self.config_middleware._apply_config_safely = failing_apply
        
        # Tentar aplicar
        result = self.config_middleware.intercept_config_change(
            problematic_config,
            'rollback_test_fail',
            apply_immediately=True
        )
        
        # Deve falhar e fazer rollback
        self.assertFalse(result['success'])
        self.assertTrue(result.get('rollback_performed', False))
        
        # Restaurar método original
        self.config_middleware._apply_config_safely = original_apply
        
        # 4. Testar rollback manual
        rollback_result = self.config_middleware.rollback_to_config(
            initial_config,
            'manual_rollback_test'
        )
        
        self.assertTrue(rollback_result['success'])
        
        print("✅ Funcionalidade de rollback funcionando corretamente")
    
    def test_system_health_monitoring(self):
        """Testa monitoramento de saúde do sistema"""
        print("\n=== Testando Monitoramento de Saúde ===")
        
        # 1. Verificar status individual dos componentes
        
        # Config Manager
        config_health = True
        try:
            test_config = self.config_manager.load_config()
            self.assertIsInstance(test_config, dict)
        except:
            config_health = False
        
        self.assertTrue(config_health)
        
        # Config Middleware
        middleware_status = self.config_middleware.get_middleware_status()
        self.assertIsInstance(middleware_status, dict)
        self.assertIn('auto_refresh_enabled', middleware_status)
        
        # Notification Service
        notif_stats = self.notification_service.get_notification_stats()
        self.assertIsInstance(notif_stats, dict)
        
        # Backup Service
        backup_stats = self.backup_service.get_backup_stats()
        self.assertIsInstance(backup_stats, dict)
        
        # 2. Verificar integração entre componentes
        integration_healthy = True
        
        # Testar fluxo: mudança de config -> notificação -> backup
        try:
            # Mudança de configuração
            test_config = {'test': {'value': 'integration_health_test'}}
            
            # Registrar callback que será chamado
            callback_called = threading.Event()
            
            def health_callback(old_config, new_config):
                callback_called.set()
            
            self.config_middleware.add_config_change_callback(health_callback)
            
            # Aplicar mudança
            result = self.config_middleware.intercept_config_change(
                test_config,
                'health_test',
                apply_immediately=True
            )
            
            if not result['success']:
                integration_healthy = False
            
            # Verificar se callback foi chamado
            if not callback_called.wait(timeout=1):
                integration_healthy = False
            
        except Exception as e:
            print(f"Erro na verificação de integração: {e}")
            integration_healthy = False
        
        self.assertTrue(integration_healthy)
        
        print("✅ Monitoramento de saúde funcionando corretamente")
    
    def test_performance_under_load(self):
        """Testa performance do sistema sob carga"""
        print("\n=== Testando Performance Sob Carga ===")
        
        import time
        
        # 1. Múltiplas mudanças de configuração simultâneas
        num_changes = 10
        start_time = time.time()
        
        results = []
        
        for i in range(num_changes):
            config = {
                'trading': {
                    'ta_params': {
                        'rsi_period': 14 + i,
                        'min_confidence': 60 + i
                    }
                }
            }
            
            result = self.config_middleware.intercept_config_change(
                config,
                f'load_test_{i}',
                apply_immediately=True
            )
            
            results.append(result)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verificar que todas as mudanças foram processadas
        successful_changes = sum(1 for r in results if r.get('success', False))
        self.assertEqual(successful_changes, num_changes)
        
        # Verificar performance (deve processar em menos de 5 segundos)
        self.assertLess(duration, 5.0, f"Performance ruim: {duration:.2f}s para {num_changes} mudanças")
        
        # 2. Múltiplas notificações
        notif_start_time = time.time()
        
        for i in range(20):
            self.notification_service.send_notification(
                'PERFORMANCE_TEST',
                f'Teste de Performance {i}',
                f'Mensagem de teste número {i}',
                {'test_number': i}
            )
        
        notif_end_time = time.time()
        notif_duration = notif_end_time - notif_start_time
        
        # Verificar que todas as notificações foram processadas
        self.assertEqual(len(self.sent_notifications), 20)
        
        # Performance de notificações (deve ser muito rápida)
        self.assertLess(notif_duration, 2.0, f"Performance de notificações ruim: {notif_duration:.2f}s")
        
        print(f"✅ Performance adequada: {duration:.2f}s para {num_changes} configs, {notif_duration:.2f}s para 20 notificações")
    
    def test_data_persistence_integrity(self):
        """Testa integridade da persistência de dados"""
        print("\n=== Testando Integridade da Persistência ===")
        
        # 1. Salvar configuração complexa
        complex_config = {
            'trading': {
                'ta_params': {
                    'rsi_period': 14,
                    'rsi_overbought': 70,
                    'rsi_oversold': 30,
                    'sma_short': 9,
                    'sma_long': 21,
                    'ema_short': 12,
                    'ema_long': 26,
                    'min_confidence': 65,
                    'min_risk_reward': 1.5
                },
                'signal_config': {
                    'max_active_signals': 5,
                    'signal_cooldown_minutes': 60,
                    'target_multipliers': [2.0, 3.5, 5.0]
                },
                'indicator_weights': {
                    'rsi': 0.20,
                    'macd': 0.25,
                    'bb': 0.15,
                    'stoch': 0.15,
                    'sma_cross': 0.15,
                    'volume': 0.10
                }
            },
            'streaming': {
                'bitcoin': {
                    'fetch_interval': 300,
                    'max_queue_size': 200
                }
            },
            'system': {
                'auto_start_stream': True,
                'enable_auto_signals': True,
                'data_retention_days': 30
            }
        }
        
        # Salvar configuração
        success = self.config_manager.save_config(
            complex_config, 
            'integrity_test', 
            'Teste de integridade'
        )
        self.assertTrue(success)
        
        # 2. Criar novo gerenciador para simular reinicialização
        new_config_manager = DynamicConfigManager(
            db_path=self.config_manager.db_path
        )
        
        # Carregar configuração
        loaded_config = new_config_manager.load_config()
        
        # 3. Verificar integridade dos dados
        
        # Verificar estrutura
        self.assertIn('trading', loaded_config)
        self.assertIn('streaming', loaded_config)
        self.assertIn('system', loaded_config)
        
        # Verificar valores específicos
        self.assertEqual(loaded_config['trading']['ta_params']['rsi_period'], 14)
        self.assertEqual(loaded_config['trading']['signal_config']['max_active_signals'], 5)
        self.assertEqual(len(loaded_config['trading']['signal_config']['target_multipliers']), 3)
        self.assertEqual(loaded_config['streaming']['bitcoin']['fetch_interval'], 300)
        
        # Verificar tipos de dados
        self.assertIsInstance(loaded_config['trading']['ta_params']['rsi_period'], int)
        self.assertIsInstance(loaded_config['trading']['ta_params']['min_risk_reward'], float)
        self.assertIsInstance(loaded_config['system']['auto_start_stream'], bool)
        self.assertIsInstance(loaded_config['trading']['signal_config']['target_multipliers'], list)
        
        # 4. Verificar histórico
        history = new_config_manager.get_config_history(limit=10)
        self.assertGreater(len(history), 0)
        
        # Encontrar nossa entrada
        integrity_entries = [h for h in history if h['changed_by'] == 'integrity_test']
        self.assertGreater(len(integrity_entries), 0)
        
        print("✅ Integridade da persistência verificada")
    
    def test_error_handling_and_recovery(self):
        """Testa tratamento de erros e recuperação"""
        print("\n=== Testando Tratamento de Erros e Recuperação ===")
        
        # 1. Teste de erro na validação
        invalid_config = {
            'trading': {
                'ta_params': {
                    'rsi_overbought': 10,  # Inválido
                    'rsi_oversold': 90     # Inválido
                }
            }
        }
        
        # Deve falhar na validação
        validation = self.config_manager.validate_config(invalid_config)
        self.assertFalse(validation['valid'])
        
        # Middleware deve rejeitar
        result = self.config_middleware.intercept_config_change(
            invalid_config,
            'error_test',
            apply_immediately=True
        )
        self.assertFalse(result['success'])
        
        # 2. Teste de erro na aplicação
        valid_config = {
            'trading': {
                'ta_params': {
                    'rsi_period': 14
                }
            }
        }
        
        # Forçar erro na aplicação
        original_apply = self.mock_app.trading_analyzer.ta_params.update
        
        def failing_update(*args, **kwargs):
            raise Exception("Simulated application error")
        
        self.mock_app.trading_analyzer.ta_params.update = failing_update
        
        # Tentar aplicar
        result = self.config_middleware.intercept_config_change(
            valid_config,
            'error_recovery_test',
            apply_immediately=True
        )
        
        # Deve falhar mas não quebrar o sistema
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        
        # Restaurar função original
        self.mock_app.trading_analyzer.ta_params.update = original_apply
        
        # 3. Verificar que sistema continua funcionando após erro
        working_config = {
            'trading': {
                'ta_params': {
                    'rsi_period': 20  # Diferente para verificar que aplicou
                }
            }
        }
        
        recovery_result = self.config_middleware.intercept_config_change(
            working_config,
            'recovery_test',
            apply_immediately=True
        )
        
        # Deve funcionar normalmente
        self.assertTrue(recovery_result['success'])
        
        # 4. Verificar logs de erro no histórico
        history = self.config_middleware.get_application_history(limit=10)
        
        # Deve ter registros de sucesso e falha
        statuses = [h.get('success', False) for h in history]
        self.assertIn(True, statuses)   # Pelo menos um sucesso
        self.assertIn(False, statuses)  # Pelo menos uma falha
        
        print("✅ Tratamento de erros e recuperação funcionando corretamente")


class TestSystemConfigurationProfiles(unittest.TestCase):
    """Testes específicos para perfis de configuração"""
    
    def setUp(self):
        """Setup para testes de perfis"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = DynamicConfigManager(
            db_path=os.path.join(self.temp_dir, 'profiles_test.db')
        )
    
    def tearDown(self):
        """Cleanup"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_profile_management(self):
        """Testa gerenciamento completo de perfis"""
        
        # 1. Criar perfil conservador
        conservative_config = {
            'trading': {
                'ta_params': {
                    'min_confidence': 80,  # Alta confiança
                    'rsi_overbought': 75,
                    'rsi_oversold': 25
                },
                'signal_config': {
                    'max_active_signals': 3,  # Poucos sinais
                    'signal_cooldown_minutes': 120  # Cooldown longo
                }
            }
        }
        
        success = self.config_manager.create_config_profile(
            'conservative',
            conservative_config,
            'Perfil conservador para operações de baixo risco'
        )
        self.assertTrue(success)
        
        # 2. Criar perfil agressivo
        aggressive_config = {
            'trading': {
                'ta_params': {
                    'min_confidence': 50,  # Confiança menor
                    'rsi_overbought': 65,
                    'rsi_oversold': 35
                },
                'signal_config': {
                    'max_active_signals': 10,  # Mais sinais
                    'signal_cooldown_minutes': 30  # Cooldown curto
                }
            }
        }
        
        success = self.config_manager.create_config_profile(
            'aggressive',
            aggressive_config,
            'Perfil agressivo para operações de alto risco'
        )
        self.assertTrue(success)
        
        # 3. Listar perfis
        profiles = self.config_manager.list_config_profiles()
        self.assertEqual(len(profiles), 2)
        
        profile_names = [p['name'] for p in profiles]
        self.assertIn('conservative', profile_names)
        self.assertIn('aggressive', profile_names)
        
        # 4. Carregar perfil específico
        loaded_conservative = self.config_manager.load_config_profile('conservative')
        self.assertIsNotNone(loaded_conservative)
        self.assertEqual(loaded_conservative['trading']['ta_params']['min_confidence'], 80)
        
        loaded_aggressive = self.config_manager.load_config_profile('aggressive')
        self.assertIsNotNone(loaded_aggressive)
        self.assertEqual(loaded_aggressive['trading']['ta_params']['min_confidence'], 50)
        
        # 5. Verificar diferenças entre perfis
        self.assertNotEqual(
            loaded_conservative['trading']['ta_params']['min_confidence'],
            loaded_aggressive['trading']['ta_params']['min_confidence']
        )
        
        self.assertNotEqual(
            loaded_conservative['trading']['signal_config']['max_active_signals'],
            loaded_aggressive['trading']['signal_config']['max_active_signals']
        )


def run_integration_tests():
    """Executa todos os testes de integração"""
    
    print("🧪 EXECUTANDO TESTES DE INTEGRAÇÃO COMPLETOS")
    print("=" * 60)
    
    # Criar suite de testes
    test_suite = unittest.TestSuite()
    
    # Adicionar testes de integração
    integration_tests = unittest.TestLoader().loadTestsFromTestCase(TestCompleteSystemIntegration)
    profile_tests = unittest.TestLoader().loadTestsFromTestCase(TestSystemConfigurationProfiles)
    
    test_suite.addTests(integration_tests)
    test_suite.addTests(profile_tests)
    
    # Executar testes
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout, buffer=True)
    result = runner.run(test_suite)
    
    # Resumo dos resultados
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS TESTES DE INTEGRAÇÃO")
    print("=" * 60)
    print(f"✅ Testes executados: {result.testsRun}")
    print(f"❌ Falhas: {len(result.failures)}")
    print(f"💥 Erros: {len(result.errors)}")
    print(f"⏭️  Pulados: {len(result.skipped)}")
    
    if result.failures:
        print("\n❌ FALHAS:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print("\n💥 ERROS:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun) * 100
    print(f"\n📈 Taxa de Sucesso: {success_rate:.1f}%")
    
    if result.wasSuccessful():
        print("\n🎉 TODOS OS TESTES DE INTEGRAÇÃO PASSARAM!")
        print("✅ O sistema está pronto para produção")
    else:
        print("\n⚠️  ALGUNS TESTES FALHARAM")
        print("🔧 Verifique os problemas antes de usar em produção")
    
    print("=" * 60)
    
    return result.wasSuccessful()


def run_quick_integration_test():
    """Executa teste rápido de integração para verificação básica"""
    
    print("⚡ TESTE RÁPIDO DE INTEGRAÇÃO")
    print("-" * 40)
    
    try:
        # Teste básico de importação
        from config_manager import DynamicConfigManager
        from middleware.config_middleware import ConfigurationMiddleware
        from services.notification_service import NotificationService
        from services.backup_service import BackupService
        
        print("✅ Imports OK")
        
        # Teste básico de inicialização
        temp_dir = tempfile.mkdtemp()
        
        config_manager = DynamicConfigManager(
            db_path=os.path.join(temp_dir, 'quick_test.db')
        )
        
        middleware = ConfigurationMiddleware()
        notification_service = NotificationService()
        backup_service = BackupService(backup_dir=os.path.join(temp_dir, 'backups'))
        
        print("✅ Inicialização OK")
        
        # Teste básico de funcionalidade
        test_config = {'test': {'value': 'quick_test'}}
        success = config_manager.save_config(test_config, 'quick_test')
        
        if success:
            loaded = config_manager.load_config()
            if loaded.get('test', {}).get('value') == 'quick_test':
                print("✅ Persistência OK")
            else:
                print("❌ Persistência FALHOU")
                return False
        else:
            print("❌ Salvamento FALHOU")
            return False
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        print("✅ TESTE RÁPIDO PASSOU!")
        return True
        
    except Exception as e:
        print(f"❌ TESTE RÁPIDO FALHOU: {e}")
        return False


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'quick':
        # Teste rápido
        success = run_quick_integration_test()
        sys.exit(0 if success else 1)
    else:
        # Testes completos
        success = run_integration_tests()
        sys.exit(0 if success else 1)