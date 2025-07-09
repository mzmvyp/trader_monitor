# cli/config_cli.py - Interface de linha de comando para gerenciar configurações

import argparse
import sys
import json
import os
from datetime import datetime
from typing import Dict, Any, List
import sqlite3
from pathlib import Path

# Adicionar ao path para imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import DynamicConfigManager
from utils.logging_config import logger


class ConfigCLI:
    """Interface de linha de comando para gerenciar configurações do sistema"""
    
    def __init__(self):
        self.config_manager = DynamicConfigManager()
        
        # Cores para output colorido
        self.colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'bold': '\033[1m',
            'end': '\033[0m'
        }
    
    def colored_print(self, text: str, color: str = 'white', bold: bool = False):
        """Imprime texto colorido"""
        if sys.stdout.isatty():  # Só usar cores se for um terminal
            prefix = self.colors.get(color, '')
            if bold:
                prefix += self.colors['bold']
            print(f"{prefix}{text}{self.colors['end']}")
        else:
            print(text)
    
    def print_header(self, text: str):
        """Imprime cabeçalho estilizado"""
        self.colored_print("=" * 60, 'cyan')
        self.colored_print(f" {text}", 'cyan', bold=True)
        self.colored_print("=" * 60, 'cyan')
    
    def print_section(self, text: str):
        """Imprime seção"""
        self.colored_print(f"\n{text}", 'yellow', bold=True)
        self.colored_print("-" * len(text), 'yellow')
    
    def print_success(self, text: str):
        """Imprime mensagem de sucesso"""
        self.colored_print(f"✅ {text}", 'green')
    
    def print_error(self, text: str):
        """Imprime mensagem de erro"""
        self.colored_print(f"❌ {text}", 'red')
    
    def print_warning(self, text: str):
        """Imprime mensagem de aviso"""
        self.colored_print(f"⚠️  {text}", 'yellow')
    
    def print_info(self, text: str):
        """Imprime mensagem informativa"""
        self.colored_print(f"ℹ️  {text}", 'blue')
    
    def show_current_config(self, section: str = None, format_output: str = 'table'):
        """Mostra configuração atual"""
        try:
            config = self.config_manager.load_config()
            
            if section:
                if section in config:
                    config = {section: config[section]}
                else:
                    self.print_error(f"Seção '{section}' não encontrada")
                    return False
            
            self.print_header("CONFIGURAÇÃO ATUAL")
            
            if format_output == 'json':
                print(json.dumps(config, indent=2, ensure_ascii=False))
            elif format_output == 'table':
                self._print_config_table(config)
            elif format_output == 'summary':
                self._print_config_summary(config)
            
            return True
            
        except Exception as e:
            self.print_error(f"Erro ao carregar configuração: {e}")
            return False
    
    def _print_config_table(self, config: Dict, prefix: str = ""):
        """Imprime configuração em formato de tabela"""
        for key, value in config.items():
            current_path = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                self.colored_print(f"{current_path}:", 'cyan', bold=True)
                self._print_config_table(value, current_path)
            else:
                # Formatação baseada no tipo
                if isinstance(value, bool):
                    value_str = "✅ Sim" if value else "❌ Não"
                    color = 'green' if value else 'red'
                elif isinstance(value, (int, float)):
                    value_str = str(value)
                    color = 'blue'
                else:
                    value_str = str(value)
                    color = 'white'
                
                print(f"  {current_path:<30} ", end="")
                self.colored_print(value_str, color)
    
    def _print_config_summary(self, config: Dict):
        """Imprime resumo da configuração"""
        flat_config = self.config_manager._flatten_config(config)
        
        # Estatísticas gerais
        self.print_section("Resumo Geral")
        print(f"  Total de configurações: {len(flat_config)}")
        
        # Por categoria
        categories = {}
        for key in flat_config.keys():
            category = key.split('.')[0]
            categories[category] = categories.get(category, 0) + 1
        
        self.print_section("Por Categoria")
        for category, count in categories.items():
            self.colored_print(f"  {category:<15} {count:>3} configurações", 'cyan')
        
        # Validação
        validation = self.config_manager.validate_config(config)
        self.print_section("Status de Validação")
        if validation['valid']:
            self.print_success("Configuração válida")
        else:
            self.print_error(f"Configuração inválida ({len(validation['errors'])} erros)")
            for error in validation['errors'][:5]:
                print(f"    • {error}")
        
        if validation.get('warnings'):
            self.print_warning(f"{len(validation['warnings'])} avisos encontrados")
            for warning in validation['warnings'][:3]:
                print(f"    • {warning}")
    
    def validate_config(self, config_file: str = None):
        """Valida configuração"""
        try:
            if config_file:
                # Validar arquivo específico
                with open(config_file, 'r') as f:
                    config = json.load(f)
                self.print_header(f"VALIDAÇÃO DE {config_file}")
            else:
                # Validar configuração atual
                config = self.config_manager.load_config()
                self.print_header("VALIDAÇÃO DA CONFIGURAÇÃO ATUAL")
            
            validation = self.config_manager.validate_config(config)
            
            if validation['valid']:
                self.print_success("Configuração é válida!")
            else:
                self.print_error(f"Configuração inválida - {len(validation['errors'])} erros encontrados:")
                for i, error in enumerate(validation['errors'], 1):
                    print(f"  {i}. {error}")
            
            if validation.get('warnings'):
                self.print_warning(f"{len(validation['warnings'])} avisos encontrados:")
                for i, warning in enumerate(validation['warnings'], 1):
                    print(f"  {i}. {warning}")
            
            return validation['valid']
            
        except Exception as e:
            self.print_error(f"Erro na validação: {e}")
            return False
    
    def backup_config(self, output_file: str = None):
        """Cria backup da configuração atual"""
        try:
            config = self.config_manager.load_config()
            
            if not output_file:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = f"config_backup_{timestamp}.json"
            
            # Dados do backup
            backup_data = {
                'backup_info': {
                    'created_at': datetime.now().isoformat(),
                    'version': '2.0.0',
                    'type': 'full_config_backup'
                },
                'configuration': config,
                'metadata': {
                    'total_settings': len(self.config_manager._flatten_config(config)),
                    'validation': self.config_manager.validate_config(config)
                }
            }
            
            # Salvar backup
            with open(output_file, 'w') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            self.print_success(f"Backup criado: {output_file}")
            return True
            
        except Exception as e:
            self.print_error(f"Erro ao criar backup: {e}")
            return False
    
    def restore_config(self, backup_file: str, validate_before: bool = True, force: bool = False):
        """Restaura configuração de backup"""
        try:
            # Carregar backup
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)
            
            if 'configuration' not in backup_data:
                self.print_error("Arquivo de backup inválido - falta configuração")
                return False
            
            config = backup_data['configuration']
            
            self.print_header(f"RESTAURAÇÃO DE {backup_file}")
            
            # Mostrar informações do backup
            if 'backup_info' in backup_data:
                info = backup_data['backup_info']
                self.print_info(f"Data do backup: {info.get('created_at', 'Desconhecida')}")
                self.print_info(f"Versão: {info.get('version', 'Desconhecida')}")
            
            # Validar se solicitado
            if validate_before:
                self.print_section("Validando configuração do backup...")
                validation = self.config_manager.validate_config(config)
                
                if not validation['valid']:
                    self.print_error("Configuração do backup é inválida:")
                    for error in validation['errors']:
                        print(f"  • {error}")
                    
                    if not force:
                        self.print_error("Use --force para restaurar mesmo assim")
                        return False
                    else:
                        self.print_warning("Continuando com --force (configuração inválida)")
                else:
                    self.print_success("Configuração do backup é válida")
            
            # Confirmar restauração
            if not force:
                response = input("\nDeseja continuar com a restauração? [y/N]: ").strip().lower()
                if response not in ['y', 'yes', 's', 'sim']:
                    self.print_info("Restauração cancelada")
                    return False
            
            # Fazer backup da configuração atual antes de restaurar
            self.print_section("Criando backup da configuração atual...")
            current_backup = f"config_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            self.backup_config(current_backup)
            
            # Restaurar configuração
            self.print_section("Restaurando configuração...")
            success = self.config_manager.save_config(config, 'cli_restore', f'Restaurado de {backup_file}')
            
            if success:
                self.print_success("Configuração restaurada com sucesso!")
                self.print_info(f"Backup da configuração anterior salvo em: {current_backup}")
                return True
            else:
                self.print_error("Erro ao salvar configuração restaurada")
                return False
            
        except Exception as e:
            self.print_error(f"Erro na restauração: {e}")
            return False
    
    def set_config_value(self, key_path: str, value: str, value_type: str = 'auto'):
        """Define valor de configuração específica"""
        try:
            config = self.config_manager.load_config()
            
            # Converter valor para o tipo correto
            if value_type == 'auto':
                # Tentar detectar tipo automaticamente
                if value.lower() in ['true', 'false']:
                    converted_value = value.lower() == 'true'
                elif value.replace('.', '').replace('-', '').isdigit():
                    converted_value = float(value) if '.' in value else int(value)
                else:
                    converted_value = value
            elif value_type == 'bool':
                converted_value = value.lower() in ['true', '1', 'yes', 'sim']
            elif value_type == 'int':
                converted_value = int(value)
            elif value_type == 'float':
                converted_value = float(value)
            elif value_type == 'json':
                converted_value = json.loads(value)
            else:
                converted_value = value
            
            # Navegar pela estrutura aninhada
            keys = key_path.split('.')
            current = config
            
            # Criar estrutura se não existir
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            # Definir valor
            old_value = current.get(keys[-1])
            current[keys[-1]] = converted_value
            
            # Validar configuração
            validation = self.config_manager.validate_config(config)
            if not validation['valid']:
                self.print_error("Configuração resultante seria inválida:")
                for error in validation['errors']:
                    print(f"  • {error}")
                return False
            
            # Salvar configuração
            success = self.config_manager.save_config(config, 'cli_set', f'Alterado {key_path}')
            
            if success:
                self.print_success(f"Configuração atualizada:")
                print(f"  {key_path}: {old_value} → {converted_value}")
                return True
            else:
                self.print_error("Erro ao salvar configuração")
                return False
                
        except Exception as e:
            self.print_error(f"Erro ao definir configuração: {e}")
            return False
    
    def list_profiles(self):
        """Lista perfis de configuração disponíveis"""
        try:
            profiles = self.config_manager.list_config_profiles()
            
            self.print_header("PERFIS DE CONFIGURAÇÃO")
            
            if not profiles:
                self.print_info("Nenhum perfil encontrado")
                return True
            
            for profile in profiles:
                status = "🔹 PADRÃO" if profile['is_default'] else "🔸"
                self.colored_print(f"{status} {profile['name']}", 'cyan', bold=True)
                
                if profile['description']:
                    print(f"    {profile['description']}")
                
                print(f"    Criado: {profile['created_at']}")
                print(f"    Atualizado: {profile['updated_at']}")
                print()
            
            return True
            
        except Exception as e:
            self.print_error(f"Erro ao listar perfis: {e}")
            return False
    
    def apply_profile(self, profile_name: str, force: bool = False):
        """Aplica perfil de configuração"""
        try:
            profile_config = self.config_manager.load_config_profile(profile_name)
            
            if not profile_config:
                self.print_error(f"Perfil '{profile_name}' não encontrado")
                return False
            
            self.print_header(f"APLICANDO PERFIL: {profile_name}")
            
            # Validar perfil
            validation = self.config_manager.validate_config(profile_config)
            if not validation['valid']:
                self.print_error("Perfil contém configuração inválida:")
                for error in validation['errors']:
                    print(f"  • {error}")
                
                if not force:
                    self.print_error("Use --force para aplicar mesmo assim")
                    return False
            
            # Confirmar aplicação
            if not force:
                response = input(f"\nDeseja aplicar o perfil '{profile_name}'? [y/N]: ").strip().lower()
                if response not in ['y', 'yes', 's', 'sim']:
                    self.print_info("Aplicação cancelada")
                    return False
            
            # Aplicar perfil
            success = self.config_manager.save_config(
                profile_config, 
                'cli_profile', 
                f'Aplicado perfil {profile_name}'
            )
            
            if success:
                self.print_success(f"Perfil '{profile_name}' aplicado com sucesso!")
                return True
            else:
                self.print_error("Erro ao aplicar perfil")
                return False
                
        except Exception as e:
            self.print_error(f"Erro ao aplicar perfil: {e}")
            return False
    
    def show_history(self, limit: int = 20, config_key: str = None):
        """Mostra histórico de mudanças"""
        try:
            history = self.config_manager.get_config_history(config_key, limit)
            
            if config_key:
                self.print_header(f"HISTÓRICO DE {config_key}")
            else:
                self.print_header(f"HISTÓRICO DE MUDANÇAS (últimas {limit})")
            
            if not history:
                self.print_info("Nenhuma mudança encontrada")
                return True
            
            for change in history:
                # Timestamp
                timestamp = change['changed_at']
                self.colored_print(f"📅 {timestamp}", 'cyan')
                
                # Usuário e motivo
                user = change['changed_by']
                reason = change.get('reason', 'Sem motivo especificado')
                print(f"   👤 {user} - {reason}")
                
                # Mudança
                key = change['config_key']
                old_val = change['old_value']
                new_val = change['new_value']
                
                if old_val is None:
                    self.colored_print(f"   ➕ {key} = {new_val}", 'green')
                else:
                    print(f"   🔄 {key}: {old_val} → {new_val}")
                
                print()
            
            return True
            
        except Exception as e:
            self.print_error(f"Erro ao mostrar histórico: {e}")
            return False
    
    def export_config(self, output_file: str, include_metadata: bool = True):
        """Exporta configuração para arquivo"""
        try:
            export_data = self.config_manager.export_config(include_metadata)
            
            with open(output_file, 'w') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.print_success(f"Configuração exportada para: {output_file}")
            
            if include_metadata:
                self.print_info("Exportação inclui metadados completos")
            
            return True
            
        except Exception as e:
            self.print_error(f"Erro na exportação: {e}")
            return False
    
    def import_config(self, input_file: str, validate_before: bool = True, force: bool = False):
        """Importa configuração de arquivo"""
        try:
            with open(input_file, 'r') as f:
                import_data = json.load(f)
            
            self.print_header(f"IMPORTANDO DE {input_file}")
            
            # Usar método do config manager
            result = self.config_manager.import_config(import_data, validate_before)
            
            if result['success']:
                self.print_success("Configuração importada com sucesso!")
                return True
            else:
                self.print_error(f"Erro na importação: {result['error']}")
                return False
                
        except Exception as e:
            self.print_error(f"Erro ao importar: {e}")
            return False


def create_cli_parser():
    """Cria parser de argumentos da CLI"""
    parser = argparse.ArgumentParser(
        description="Sistema de Trading - Gerenciador de Configurações CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s show                                    # Mostra configuração atual
  %(prog)s show --section trading --format json   # Mostra seção trading em JSON
  %(prog)s validate                               # Valida configuração atual
  %(prog)s backup config_backup.json              # Cria backup
  %(prog)s restore config_backup.json             # Restaura backup
  %(prog)s set trading.ta_params.rsi_period 20    # Define valor específico
  %(prog)s profiles list                          # Lista perfis disponíveis
  %(prog)s profiles apply conservative            # Aplica perfil conservador
  %(prog)s history --limit 10                     # Mostra últimas 10 mudanças
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponíveis')
    
    # Comando show
    show_parser = subparsers.add_parser('show', help='Mostra configuração atual')
    show_parser.add_argument('--section', help='Seção específica para mostrar')
    show_parser.add_argument('--format', choices=['table', 'json', 'summary'], 
                           default='table', help='Formato de saída')
    
    # Comando validate
    validate_parser = subparsers.add_parser('validate', help='Valida configuração')
    validate_parser.add_argument('--file', help='Arquivo específico para validar')
    
    # Comando backup
    backup_parser = subparsers.add_parser('backup', help='Cria backup da configuração')
    backup_parser.add_argument('output_file', nargs='?', help='Arquivo de saída')
    
    # Comando restore
    restore_parser = subparsers.add_parser('restore', help='Restaura configuração de backup')
    restore_parser.add_argument('backup_file', help='Arquivo de backup')
    restore_parser.add_argument('--no-validate', action='store_true', 
                              help='Pula validação antes de restaurar')
    restore_parser.add_argument('--force', action='store_true', 
                              help='Força restauração mesmo com problemas')
    
    # Comando set
    set_parser = subparsers.add_parser('set', help='Define valor de configuração')
    set_parser.add_argument('key_path', help='Caminho da configuração (ex: trading.ta_params.rsi_period)')
    set_parser.add_argument('value', help='Novo valor')
    set_parser.add_argument('--type', choices=['auto', 'string', 'int', 'float', 'bool', 'json'],
                          default='auto', help='Tipo do valor')
    
    # Comando profiles
    profiles_parser = subparsers.add_parser('profiles', help='Gerencia perfis de configuração')
    profiles_subparsers = profiles_parser.add_subparsers(dest='profiles_action')
    
    profiles_subparsers.add_parser('list', help='Lista perfis disponíveis')
    
    apply_parser = profiles_subparsers.add_parser('apply', help='Aplica perfil')
    apply_parser.add_argument('profile_name', help='Nome do perfil')
    apply_parser.add_argument('--force', action='store_true', help='Força aplicação')
    
    # Comando history
    history_parser = subparsers.add_parser('history', help='Mostra histórico de mudanças')
    history_parser.add_argument('--limit', type=int, default=20, help='Número de entradas')
    history_parser.add_argument('--key', help='Chave específica')
    
    # Comando export
    export_parser = subparsers.add_parser('export', help='Exporta configuração')
    export_parser.add_argument('output_file', help='Arquivo de saída')
    export_parser.add_argument('--no-metadata', action='store_true', 
                             help='Exclui metadados da exportação')
    
    # Comando import
    import_parser = subparsers.add_parser('import', help='Importa configuração')
    import_parser.add_argument('input_file', help='Arquivo de entrada')
    import_parser.add_argument('--no-validate', action='store_true', 
                             help='Pula validação antes de importar')
    import_parser.add_argument('--force', action='store_true', 
                             help='Força importação mesmo com problemas')
    
    return parser


def main():
    """Função principal da CLI"""
    parser = create_cli_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    cli = ConfigCLI()
    
    try:
        # Executar comando
        if args.command == 'show':
            success = cli.show_current_config(args.section, args.format)
        
        elif args.command == 'validate':
            success = cli.validate_config(args.file)
        
        elif args.command == 'backup':
            success = cli.backup_config(args.output_file)
        
        elif args.command == 'restore':
            success = cli.restore_config(
                args.backup_file, 
                not args.no_validate, 
                args.force
            )
        
        elif args.command == 'set':
            success = cli.set_config_value(args.key_path, args.value, args.type)
        
        elif args.command == 'profiles':
            if args.profiles_action == 'list':
                success = cli.list_profiles()
            elif args.profiles_action == 'apply':
                success = cli.apply_profile(args.profile_name, args.force)
            else:
                cli.print_error("Ação de perfil não especificada")
                return 1
        
        elif args.command == 'history':
            success = cli.show_history(args.limit, args.key)
        
        elif args.command == 'export':
            success = cli.export_config(args.output_file, not args.no_metadata)
        
        elif args.command == 'import':
            success = cli.import_config(
                args.input_file, 
                not args.no_validate, 
                args.force
            )
        
        else:
            cli.print_error(f"Comando desconhecido: {args.command}")
            return 1
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        cli.print_info("\nOperação cancelada pelo usuário")
        return 1
    except Exception as e:
        cli.print_error(f"Erro inesperado: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())