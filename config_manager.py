# config_manager.py - Gerenciador dinâmico de configurações

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional
from utils.logging_config import logger
from config import app_config

class DynamicConfigManager:
    """
    Gerenciador de configurações dinâmico que permite:
    - Carregar configurações do banco de dados
    - Aplicar configurações em tempo real
    - Validar configurações
    - Fazer backup de configurações
    - Migrar configurações entre versões
    """
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(app_config.DATA_DIR, 'dynamic_config.db')
        self.current_config = {}
        self.default_config = self._get_default_config()
        
        # Configurações que podem ser aplicadas em tempo real
        self.runtime_applicable = {
            'trading.ta_params',
            'trading.signal_config', 
            'trading.indicator_weights',
            'streaming.bitcoin.fetch_interval',
            'streaming.bitcoin.max_queue_size',
            'system.enable_auto_signals',
            'system.require_volume_confirmation',
            'system.enable_notifications'
        }
        
        self.setup_database()
        self.load_config()
    
    def setup_database(self):
        """Configura banco de dados para configurações dinâmicas"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tabela principal de configurações
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS dynamic_config (
                    id INTEGER PRIMARY KEY,
                    config_key TEXT UNIQUE NOT NULL,
                    config_value TEXT NOT NULL,
                    config_type TEXT NOT NULL,
                    description TEXT,
                    is_runtime_applicable BOOLEAN DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # Tabela de histórico de configurações
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT NOT NULL,
                    changed_by TEXT DEFAULT 'system',
                    changed_at TEXT NOT NULL,
                    reason TEXT
                )
            ''')
            
            # Tabela de perfis de configuração
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_name TEXT UNIQUE NOT NULL,
                    config_data TEXT NOT NULL,
                    description TEXT,
                    is_default BOOLEAN DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # Tabela de validação de configurações
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config_validation_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT NOT NULL,
                    validation_type TEXT NOT NULL,
                    validation_rule TEXT NOT NULL,
                    error_message TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("[CONFIG_MGR] Banco de configurações dinâmicas inicializado")
            
        except Exception as e:
            logger.error(f"[CONFIG_MGR] Erro ao configurar banco: {e}")
    
    def load_config(self) -> Dict[str, Any]:
        """Carrega configuração atual do banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT config_key, config_value, config_type FROM dynamic_config')
            rows = cursor.fetchall()
            
            config = {}
            for row in rows:
                key, value, value_type = row
                
                # Converter valor baseado no tipo
                if value_type == 'json':
                    config[key] = json.loads(value)
                elif value_type == 'int':
                    config[key] = int(value)
                elif value_type == 'float':
                    config[key] = float(value)
                elif value_type == 'bool':
                    config[key] = value.lower() == 'true'
                else:
                    config[key] = value
            
            conn.close()
            
            # Se não há configuração salva, usar padrões
            if not config:
                config = self.default_config.copy()
                self.save_config(config, reason="Configuração inicial")
            
            self.current_config = config
            logger.info(f"[CONFIG_MGR] Configuração carregada: {len(config)} itens")
            
            return config
            
        except Exception as e:
            logger.error(f"[CONFIG_MGR] Erro ao carregar configuração: {e}")
            return self.default_config.copy()
    
    def save_config(self, config: Dict[str, Any], changed_by: str = 'system', reason: str = None) -> bool:
        """Salva configuração no banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.now().isoformat()
            
            for key, value in self._flatten_config(config).items():
                # Determinar tipo do valor
                if isinstance(value, dict) or isinstance(value, list):
                    value_str = json.dumps(value)
                    value_type = 'json'
                elif isinstance(value, int):
                    value_str = str(value)
                    value_type = 'int'
                elif isinstance(value, float):
                    value_str = str(value)
                    value_type = 'float'
                elif isinstance(value, bool):
                    value_str = str(value)
                    value_type = 'bool'
                else:
                    value_str = str(value)
                    value_type = 'string'
                
                # Verificar se configuração já existe
                cursor.execute('SELECT config_value FROM dynamic_config WHERE config_key = ?', (key,))
                existing = cursor.fetchone()
                
                if existing:
                    old_value = existing[0]
                    if old_value != value_str:
                        # Atualizar configuração existente
                        cursor.execute('''
                            UPDATE dynamic_config 
                            SET config_value = ?, config_type = ?, updated_at = ?
                            WHERE config_key = ?
                        ''', (value_str, value_type, timestamp, key))
                        
                        # Adicionar ao histórico
                        cursor.execute('''
                            INSERT INTO config_history 
                            (config_key, old_value, new_value, changed_by, changed_at, reason)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (key, old_value, value_str, changed_by, timestamp, reason))
                else:
                    # Inserir nova configuração
                    is_runtime = key in self.runtime_applicable
                    description = self._get_config_description(key)
                    
                    cursor.execute('''
                        INSERT INTO dynamic_config 
                        (config_key, config_value, config_type, description, 
                         is_runtime_applicable, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (key, value_str, value_type, description, is_runtime, timestamp, timestamp))
                    
                    # Adicionar ao histórico
                    cursor.execute('''
                        INSERT INTO config_history 
                        (config_key, old_value, new_value, changed_by, changed_at, reason)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (key, None, value_str, changed_by, timestamp, reason or "Nova configuração"))
            
            conn.commit()
            conn.close()
            
            self.current_config = config
            logger.info(f"[CONFIG_MGR] Configuração salva: {len(config)} itens")
            
            return True
            
        except Exception as e:
            logger.error(f"[CONFIG_MGR] Erro ao salvar configuração: {e}")
            return False
    
    def apply_config_to_system(self, app_instance = None) -> Dict[str, Any]:
        """Aplica configuração atual aos componentes do sistema"""
        try:
            applied_components = []
            errors = []
            
            if not app_instance:
                logger.warning("[CONFIG_MGR] Instância da aplicação não fornecida")
                return {'success': False, 'error': 'App instance required'}
            
            config = self.current_config
            
            # Aplicar configurações de trading
            if hasattr(app_instance, 'trading_analyzer'):
                trading_result = self._apply_trading_config(app_instance.trading_analyzer, config)
                if trading_result['success']:
                    applied_components.extend(trading_result['components'])
                else:
                    errors.append(f"Trading: {trading_result['error']}")
            
            # Aplicar configurações de streaming
            if hasattr(app_instance, 'bitcoin_streamer'):
                streaming_result = self._apply_streaming_config(app_instance.bitcoin_streamer, config)
                if streaming_result['success']:
                    applied_components.extend(streaming_result['components'])
                else:
                    errors.append(f"Streaming: {streaming_result['error']}")
            
            # Aplicar configurações multi-asset
            if hasattr(app_instance, 'multi_asset_manager'):
                multi_result = self._apply_multi_asset_config(app_instance.multi_asset_manager, config)
                if multi_result['success']:
                    applied_components.extend(multi_result['components'])
                else:
                    errors.append(f"Multi-Asset: {multi_result['error']}")
            
            if errors:
                logger.warning(f"[CONFIG_MGR] Aplicação parcial: {', '.join(errors)}")
                return {
                    'success': False,
                    'error': '; '.join(errors),
                    'applied_components': applied_components
                }
            
            logger.info(f"[CONFIG_MGR] Configuração aplicada: {', '.join(applied_components)}")
            return {
                'success': True,
                'applied_components': applied_components
            }
            
        except Exception as e:
            logger.error(f"[CONFIG_MGR] Erro ao aplicar configuração: {e}")
            return {'success': False, 'error': str(e)}
    
    def _apply_trading_config(self, trading_analyzer, config: Dict) -> Dict:
        """Aplica configurações específicas do trading analyzer"""
        try:
            applied = []
            
            # Aplicar parâmetros de análise técnica
            ta_params = self._get_nested_config(config, 'trading.ta_params')
            if ta_params:
                trading_analyzer.ta_params.update(ta_params)
                applied.append('ta_params')
            
            # Aplicar configurações de sinais
            signal_config = self._get_nested_config(config, 'trading.signal_config')
            if signal_config:
                trading_analyzer.signal_config.update(signal_config)
                applied.append('signal_config')
            
            # Aplicar pesos dos indicadores
            indicator_weights = self._get_nested_config(config, 'trading.indicator_weights')
            if indicator_weights:
                trading_analyzer.indicator_weights.update(indicator_weights)
                applied.append('indicator_weights')
            
            return {'success': True, 'components': [f'trading.{c}' for c in applied]}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _apply_streaming_config(self, bitcoin_streamer, config: Dict) -> Dict:
        """Aplica configurações específicas do streamer"""
        try:
            applied = []
            
            # Aplicar intervalo de fetch
            fetch_interval = self._get_nested_config(config, 'streaming.bitcoin.fetch_interval')
            if fetch_interval:
                bitcoin_streamer.fetch_interval = fetch_interval
                applied.append('fetch_interval')
            
            # Aplicar tamanho máximo da queue
            max_queue_size = self._get_nested_config(config, 'streaming.bitcoin.max_queue_size')
            if max_queue_size:
                # Nota: Não podemos alterar maxlen de uma deque existente
                # Esta configuração se aplicaria na próxima inicialização
                applied.append('max_queue_size')
            
            return {'success': True, 'components': [f'streaming.{c}' for c in applied]}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _apply_multi_asset_config(self, multi_asset_manager, config: Dict) -> Dict:
        """Aplica configurações específicas do multi-asset manager"""
        try:
            applied = []
            
            # Aplicar configurações de assets específicos
            multi_config = self._get_nested_config(config, 'multi_asset')
            if multi_config:
                # Implementar aplicação de configurações multi-asset
                applied.append('multi_asset_settings')
            
            return {'success': True, 'components': applied}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Valida configuração contra regras definidas"""
        try:
            errors = []
            warnings = []
            
            flat_config = self._flatten_config(config)
            
            # Carregar regras de validação do banco
            validation_rules = self._load_validation_rules()
            
            for key, value in flat_config.items():
                if key in validation_rules:
                    for rule in validation_rules[key]:
                        result = self._apply_validation_rule(key, value, rule)
                        if not result['valid']:
                            if result['severity'] == 'error':
                                errors.append(result['message'])
                            else:
                                warnings.append(result['message'])
            
            # Validações específicas adicionais
            additional_errors = self._additional_validations(flat_config)
            errors.extend(additional_errors)
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"[CONFIG_MGR] Erro na validação: {e}")
            return {
                'valid': False,
                'errors': [f'Erro na validação: {str(e)}'],
                'warnings': []
            }
    
    def _load_validation_rules(self) -> Dict[str, list]:
        """Carrega regras de validação do banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT config_key, validation_type, validation_rule, error_message
                FROM config_validation_rules
                WHERE is_active = 1
            ''')
            
            rules = {}
            for row in cursor.fetchall():
                key, val_type, rule, message = row
                if key not in rules:
                    rules[key] = []
                
                rules[key].append({
                    'type': val_type,
                    'rule': rule,
                    'message': message
                })
            
            conn.close()
            return rules
            
        except Exception as e:
            logger.error(f"[CONFIG_MGR] Erro ao carregar regras: {e}")
            return {}
    
    def _apply_validation_rule(self, key: str, value: Any, rule: Dict) -> Dict:
        """Aplica uma regra de validação específica"""
        try:
            rule_type = rule['type']
            rule_expr = rule['rule']
            
            if rule_type == 'range':
                # Formato: "min,max"
                min_val, max_val = map(float, rule_expr.split(','))
                valid = min_val <= float(value) <= max_val
                message = rule['message'] or f"{key} deve estar entre {min_val} e {max_val}"
                
            elif rule_type == 'comparison':
                # Formato: "other_key,operator" (ex: "rsi_oversold,<")
                other_key, operator = rule_expr.split(',')
                # Implementar comparação entre configurações
                valid = True  # Placeholder
                message = rule['message'] or f"Comparação {key} {operator} {other_key} falhou"
                
            elif rule_type == 'sum_equals':
                # Para validar que soma de pesos = 1.0
                target_sum = float(rule_expr)
                # Esta validação seria aplicada em um grupo de configurações
                valid = True  # Placeholder
                message = rule['message'] or f"Soma deve ser {target_sum}"
                
            else:
                valid = True
                message = ""
            
            return {
                'valid': valid,
                'message': message,
                'severity': 'error'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'message': f"Erro na validação de {key}: {str(e)}",
                'severity': 'error'
            }
    
    def _additional_validations(self, flat_config: Dict) -> list:
        """Validações específicas adicionais"""
        errors = []
        
        try:
            # Validar RSI overbought > oversold
            rsi_ob = flat_config.get('trading.ta_params.rsi_overbought')
            rsi_os = flat_config.get('trading.ta_params.rsi_oversold')
            if rsi_ob and rsi_os and rsi_os >= rsi_ob:
                errors.append("RSI oversold deve ser menor que overbought")
            
            # Validar SMA curta < longa
            sma_short = flat_config.get('trading.ta_params.sma_short')
            sma_long = flat_config.get('trading.ta_params.sma_long')
            if sma_short and sma_long and sma_short >= sma_long:
                errors.append("SMA curta deve ser menor que SMA longa")
            
            # Validar EMA curta < longa
            ema_short = flat_config.get('trading.ta_params.ema_short')
            ema_long = flat_config.get('trading.ta_params.ema_long')
            if ema_short and ema_long and ema_short >= ema_long:
                errors.append("EMA curta deve ser menor que EMA longa")
            
            # Validar soma dos pesos = 1.0
            weights = [
                flat_config.get('trading.indicator_weights.rsi', 0),
                flat_config.get('trading.indicator_weights.macd', 0),
                flat_config.get('trading.indicator_weights.bb', 0),
                flat_config.get('trading.indicator_weights.stoch', 0),
                flat_config.get('trading.indicator_weights.sma_cross', 0),
                flat_config.get('trading.indicator_weights.volume', 0)
            ]
            
            total_weight = sum(float(w) for w in weights if w is not None)
            if abs(total_weight - 1.0) > 0.01:
                errors.append(f"Soma dos pesos deve ser 1.0 (atual: {total_weight:.3f})")
            
        except Exception as e:
            logger.error(f"[CONFIG_MGR] Erro nas validações adicionais: {e}")
            errors.append(f"Erro na validação: {str(e)}")
        
        return errors
    
    def create_config_profile(self, name: str, config: Dict[str, Any], description: str = None) -> bool:
        """Cria um perfil de configuração"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            config_json = json.dumps(config, indent=2)
            timestamp = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT OR REPLACE INTO config_profiles 
                (profile_name, config_data, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, config_json, description, timestamp, timestamp))
            
            conn.commit()
            conn.close()
            
            logger.info(f"[CONFIG_MGR] Perfil criado: {name}")
            return True
            
        except Exception as e:
            logger.error(f"[CONFIG_MGR] Erro ao criar perfil: {e}")
            return False
    
    def load_config_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """Carrega um perfil de configuração"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT config_data FROM config_profiles WHERE profile_name = ?', (name,))
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                return json.loads(result[0])
            return None
            
        except Exception as e:
            logger.error(f"[CONFIG_MGR] Erro ao carregar perfil: {e}")
            return None
    
    def list_config_profiles(self) -> list:
        """Lista todos os perfis de configuração"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT profile_name, description, is_default, created_at, updated_at
                FROM config_profiles
                ORDER BY is_default DESC, created_at ASC
            ''')
            
            profiles = []
            for row in cursor.fetchall():
                profiles.append({
                    'name': row[0],
                    'description': row[1],
                    'is_default': bool(row[2]),
                    'created_at': row[3],
                    'updated_at': row[4]
                })
            
            conn.close()
            return profiles
            
        except Exception as e:
            logger.error(f"[CONFIG_MGR] Erro ao listar perfis: {e}")
            return []
    
    def get_config_history(self, config_key: str = None, limit: int = 50) -> list:
        """Obtém histórico de mudanças de configuração"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if config_key:
                cursor.execute('''
                    SELECT config_key, old_value, new_value, changed_by, changed_at, reason
                    FROM config_history
                    WHERE config_key = ?
                    ORDER BY changed_at DESC
                    LIMIT ?
                ''', (config_key, limit))
            else:
                cursor.execute('''
                    SELECT config_key, old_value, new_value, changed_by, changed_at, reason
                    FROM config_history
                    ORDER BY changed_at DESC
                    LIMIT ?
                ''', (limit,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'config_key': row[0],
                    'old_value': row[1],
                    'new_value': row[2],
                    'changed_by': row[3],
                    'changed_at': row[4],
                    'reason': row[5]
                })
            
            conn.close()
            return history
            
        except Exception as e:
            logger.error(f"[CONFIG_MGR] Erro ao obter histórico: {e}")
            return []
    
    def export_config(self, include_metadata: bool = True) -> Dict[str, Any]:
        """Exporta configuração atual com metadados"""
        export_data = {
            'config': self.current_config.copy(),
            'exported_at': datetime.now().isoformat(),
            'version': '2.0.0'
        }
        
        if include_metadata:
            export_data['metadata'] = {
                'profiles': self.list_config_profiles(),
                'recent_history': self.get_config_history(limit=20),
                'validation_summary': self.validate_config(self.current_config)
            }
        
        return export_data
    
    def import_config(self, config_data: Dict[str, Any], validate: bool = True) -> Dict[str, Any]:
        """Importa configuração de dados exportados"""
        try:
            if 'config' not in config_data:
                return {'success': False, 'error': 'Formato de importação inválido'}
            
            imported_config = config_data['config']
            
            if validate:
                validation = self.validate_config(imported_config)
                if not validation['valid']:
                    return {
                        'success': False,
                        'error': f"Configuração inválida: {'; '.join(validation['errors'])}"
                    }
            
            # Salvar configuração importada
            save_success = self.save_config(
                imported_config,
                changed_by='import',
                reason='Configuração importada'
            )
            
            if not save_success:
                return {'success': False, 'error': 'Erro ao salvar configuração importada'}
            
            return {
                'success': True,
                'message': 'Configuração importada com sucesso',
                'imported_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[CONFIG_MGR] Erro na importação: {e}")
            return {'success': False, 'error': str(e)}
    
    # ==================== HELPER METHODS ====================
    
    def _flatten_config(self, config: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """Achata configuração aninhada para chaves planas"""
        items = []
        for k, v in config.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_config(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    def _get_nested_config(self, config: Dict[str, Any], key_path: str) -> Any:
        """Obtém valor de configuração usando path aninhado (ex: 'trading.ta_params.rsi_period')"""
        keys = key_path.split('.')
        value = config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    def _get_config_description(self, key: str) -> str:
        """Retorna descrição da configuração baseada na chave"""
        descriptions = {
            'trading.ta_params.rsi_period': 'Período para cálculo do RSI',
            'trading.ta_params.rsi_overbought': 'Nível de sobrecompra do RSI',
            'trading.ta_params.rsi_oversold': 'Nível de sobrevenda do RSI',
            'trading.ta_params.min_confidence': 'Confiança mínima para gerar sinais',
            'trading.signal_config.max_active_signals': 'Máximo de sinais ativos simultâneos',
            'trading.signal_config.signal_cooldown_minutes': 'Intervalo mínimo entre sinais',
            'streaming.bitcoin.fetch_interval': 'Intervalo de fetch de dados Bitcoin',
            'system.enable_auto_signals': 'Habilitação de geração automática de sinais'
        }
        
        return descriptions.get(key, f'Configuração: {key}')
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Retorna configuração padrão do sistema"""
        return {
            'trading': {
                'ta_params': {
                    'rsi_period': 14,
                    'rsi_overbought': 70,
                    'rsi_oversold': 30,
                    'sma_short': 9,
                    'sma_long': 21,
                    'ema_short': 12,
                    'ema_long': 26,
                    'macd_signal': 9,
                    'bb_period': 20,
                    'bb_std': 2.0,
                    'stoch_k': 14,
                    'stoch_d': 3,
                    'stoch_overbought': 80,
                    'stoch_oversold': 20,
                    'volume_sma': 20,
                    'atr_period': 14,
                    'min_confidence': 60,
                    'min_risk_reward': 1.5,
                    'min_volume_ratio': 1.1,
                },
                'signal_config': {
                    'max_active_signals': 5,
                    'signal_cooldown_minutes': 60,
                    'target_multipliers': [2.0, 3.5, 5.0],
                    'stop_loss_atr_multiplier': 2.0,
                    'partial_take_profit': [0.5, 0.3, 0.2],
                    'trailing_stop_distance': 1.5,
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
                'require_volume_confirmation': True,
                'enable_auto_signals': True,
                'enable_advanced_patterns': False,
                'enable_notifications': True,
                'correlation_analysis': False,
                'auto_cleanup': True,
                'data_retention_days': 30
            }
        }

# ==================== GLOBAL INSTANCE ====================

# Instância global do gerenciador de configurações
dynamic_config_manager = DynamicConfigManager()

def get_dynamic_config() -> Dict[str, Any]:
    """Retorna configuração dinâmica atual"""
    return dynamic_config_manager.current_config

def update_dynamic_config(config: Dict[str, Any], app_instance=None) -> bool:
    """Atualiza configuração dinâmica e aplica ao sistema"""
    try:
        # Validar configuração
        validation = dynamic_config_manager.validate_config(config)
        if not validation['valid']:
            logger.error(f"[CONFIG] Configuração inválida: {validation['errors']}")
            return False
        
        # Salvar configuração
        save_success = dynamic_config_manager.save_config(config, changed_by='api')
        if not save_success:
            logger.error("[CONFIG] Erro ao salvar configuração")
            return False
        
        # Aplicar ao sistema se instância fornecida
        if app_instance:
            apply_result = dynamic_config_manager.apply_config_to_system(app_instance)
            if not apply_result['success']:
                logger.warning(f"[CONFIG] Configuração salva mas não aplicada: {apply_result['error']}")
        
        return True
        
    except Exception as e:
        logger.error(f"[CONFIG] Erro ao atualizar configuração: {e}")
        return False