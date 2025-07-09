# services/notification_service.py - Sistema de notificações para configurações

import smtplib
import json
import requests
from datetime import datetime
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from typing import Dict, List, Optional, Any
from utils.logging_config import logger

class NotificationService:
    """
    Serviço de notificações para mudanças de configuração e eventos do sistema
    Suporta: Email, Webhook, Slack, Discord, Telegram
    """
    
    def __init__(self):
        self.notification_channels = {}
        self.notification_queue = []
        self.notification_history = []
        self.max_history_size = 1000
        
        # Configurações padrão
        self.config = {
            'email': {
                'enabled': False,
                'smtp_server': '',
                'smtp_port': 587,
                'username': '',
                'password': '',
                'from_email': '',
                'to_emails': []
            },
            'webhook': {
                'enabled': False,
                'url': '',
                'headers': {},
                'timeout': 10
            },
            'slack': {
                'enabled': False,
                'webhook_url': '',
                'channel': '#trading-alerts',
                'username': 'Trading System'
            },
            'discord': {
                'enabled': False,
                'webhook_url': '',
                'username': 'Trading System'
            },
            'telegram': {
                'enabled': False,
                'bot_token': '',
                'chat_id': '',
                'parse_mode': 'Markdown'
            }
        }
        
        # Tipos de notificação e suas prioridades
        self.notification_types = {
            'CONFIG_CHANGED': {'priority': 'medium', 'icon': '⚙️'},
            'CONFIG_APPLIED': {'priority': 'low', 'icon': '✅'},
            'CONFIG_ERROR': {'priority': 'high', 'icon': '❌'},
            'SYSTEM_HEALTH': {'priority': 'high', 'icon': '🏥'},
            'TRADING_SIGNAL': {'priority': 'medium', 'icon': '📊'},
            'PERFORMANCE_ALERT': {'priority': 'medium', 'icon': '⚡'},
            'SECURITY_ALERT': {'priority': 'critical', 'icon': '🔐'},
            'MAINTENANCE': {'priority': 'low', 'icon': '🔧'}
        }
        
        self.load_config()
    
    def load_config(self):
        """Carrega configuração de notificações do arquivo ou banco"""
        try:
            # Tentar carregar de arquivo de configuração
            import os
            config_file = os.path.join('data', 'notification_config.json')
            
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
                    logger.info("[NOTIFICATIONS] Configuração carregada do arquivo")
            else:
                logger.info("[NOTIFICATIONS] Usando configuração padrão")
                
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro ao carregar configuração: {e}")
    
    def save_config(self):
        """Salva configuração atual em arquivo"""
        try:
            import os
            os.makedirs('data', exist_ok=True)
            config_file = os.path.join('data', 'notification_config.json')
            
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
                
            logger.info("[NOTIFICATIONS] Configuração salva")
            return True
            
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro ao salvar configuração: {e}")
            return False
    
    def send_notification(self, 
                         notification_type: str,
                         title: str,
                         message: str,
                         details: Dict = None,
                         priority: str = None) -> Dict[str, Any]:
        """
        Envia notificação através de todos os canais habilitados
        
        Args:
            notification_type: Tipo da notificação (CONFIG_CHANGED, etc.)
            title: Título da notificação
            message: Mensagem principal
            details: Detalhes adicionais (dict)
            priority: Prioridade (critical, high, medium, low)
        
        Returns:
            Resultado do envio para cada canal
        """
        try:
            # Determinar prioridade
            if not priority:
                priority = self.notification_types.get(notification_type, {}).get('priority', 'medium')
            
            # Criar objeto de notificação
            notification = {
                'id': f"notif_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                'type': notification_type,
                'title': title,
                'message': message,
                'details': details or {},
                'priority': priority,
                'timestamp': datetime.now().isoformat(),
                'icon': self.notification_types.get(notification_type, {}).get('icon', '📢')
            }
            
            # Adicionar ao histórico
            self._add_to_history(notification)
            
            # Enviar através de todos os canais habilitados
            results = {}
            
            if self.config['email']['enabled']:
                results['email'] = self._send_email(notification)
            
            if self.config['webhook']['enabled']:
                results['webhook'] = self._send_webhook(notification)
                
            if self.config['slack']['enabled']:
                results['slack'] = self._send_slack(notification)
                
            if self.config['discord']['enabled']:
                results['discord'] = self._send_discord(notification)
                
            if self.config['telegram']['enabled']:
                results['telegram'] = self._send_telegram(notification)
            
            # Log resultado
            success_count = sum(1 for r in results.values() if r.get('success', False))
            total_count = len(results)
            
            logger.info(f"[NOTIFICATIONS] Enviado '{title}' para {success_count}/{total_count} canais")
            
            return {
                'notification_id': notification['id'],
                'success': success_count > 0,
                'results': results,
                'summary': f"{success_count}/{total_count} canais"
            }
            
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro no envio: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_email(self, notification: Dict) -> Dict:
        """Envia notificação por email"""
        try:
            config = self.config['email']
            
            # Criar mensagem
            msg = MimeMultipart()
            msg['From'] = config['from_email']
            msg['To'] = ', '.join(config['to_emails'])
            msg['Subject'] = f"[Trading System] {notification['title']}"
            
            # Corpo do email
            body = self._format_email_body(notification)
            msg.attach(MimeText(body, 'html'))
            
            # Enviar
            server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
            server.starttls()
            server.login(config['username'], config['password'])
            server.send_message(msg)
            server.quit()
            
            return {'success': True, 'message': 'Email enviado'}
            
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro no email: {e}")
            return {'success': False, 'error': str(e)}
    
    def _send_webhook(self, notification: Dict) -> Dict:
        """Envia notificação via webhook"""
        try:
            config = self.config['webhook']
            
            payload = {
                'notification': notification,
                'system': 'trading_system',
                'timestamp': datetime.now().isoformat()
            }
            
            response = requests.post(
                config['url'],
                json=payload,
                headers=config.get('headers', {}),
                timeout=config.get('timeout', 10)
            )
            
            response.raise_for_status()
            
            return {'success': True, 'status_code': response.status_code}
            
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro no webhook: {e}")
            return {'success': False, 'error': str(e)}
    
    def _send_slack(self, notification: Dict) -> Dict:
        """Envia notificação para Slack"""
        try:
            config = self.config['slack']
            
            # Determinar cor baseada na prioridade
            color_map = {
                'critical': '#ff0000',
                'high': '#ff6600',
                'medium': '#ffcc00',
                'low': '#00ff00'
            }
            
            payload = {
                'channel': config['channel'],
                'username': config['username'],
                'icon_emoji': ':robot_face:',
                'attachments': [{
                    'color': color_map.get(notification['priority'], '#36a64f'),
                    'title': f"{notification['icon']} {notification['title']}",
                    'text': notification['message'],
                    'fields': self._format_slack_fields(notification),
                    'footer': 'Trading System',
                    'ts': int(datetime.now().timestamp())
                }]
            }
            
            response = requests.post(config['webhook_url'], json=payload)
            response.raise_for_status()
            
            return {'success': True, 'message': 'Slack enviado'}
            
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro no Slack: {e}")
            return {'success': False, 'error': str(e)}
    
    def _send_discord(self, notification: Dict) -> Dict:
        """Envia notificação para Discord"""
        try:
            config = self.config['discord']
            
            # Determinar cor baseada na prioridade
            color_map = {
                'critical': 16711680,  # Vermelho
                'high': 16753920,      # Laranja
                'medium': 16776960,    # Amarelo
                'low': 65280          # Verde
            }
            
            embed = {
                'title': f"{notification['icon']} {notification['title']}",
                'description': notification['message'],
                'color': color_map.get(notification['priority'], 3447003),
                'timestamp': notification['timestamp'],
                'footer': {'text': 'Trading System'},
                'fields': self._format_discord_fields(notification)
            }
            
            payload = {
                'username': config['username'],
                'embeds': [embed]
            }
            
            response = requests.post(config['webhook_url'], json=payload)
            response.raise_for_status()
            
            return {'success': True, 'message': 'Discord enviado'}
            
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro no Discord: {e}")
            return {'success': False, 'error': str(e)}
    
    def _send_telegram(self, notification: Dict) -> Dict:
        """Envia notificação para Telegram"""
        try:
            config = self.config['telegram']
            
            # Formatar mensagem
            message = self._format_telegram_message(notification)
            
            url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
            
            payload = {
                'chat_id': config['chat_id'],
                'text': message,
                'parse_mode': config.get('parse_mode', 'Markdown'),
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            return {'success': True, 'message': 'Telegram enviado'}
            
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro no Telegram: {e}")
            return {'success': False, 'error': str(e)}
    
    def _format_email_body(self, notification: Dict) -> str:
        """Formata corpo do email em HTML"""
        priority_colors = {
            'critical': '#dc3545',
            'high': '#fd7e14',
            'medium': '#ffc107',
            'low': '#28a745'
        }
        
        color = priority_colors.get(notification['priority'], '#6c757d')
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .details {{ background-color: #f8f9fa; padding: 15px; border-left: 4px solid {color}; margin: 15px 0; }}
                .footer {{ text-align: center; color: #6c757d; font-size: 12px; padding: 20px; }}
                .badge {{ background-color: {color}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{notification['icon']} {notification['title']}</h1>
                <span class="badge">{notification['priority'].upper()}</span>
            </div>
            
            <div class="content">
                <p><strong>Mensagem:</strong></p>
                <p>{notification['message']}</p>
                
                <p><strong>Tipo:</strong> {notification['type']}</p>
                <p><strong>Data/Hora:</strong> {notification['timestamp']}</p>
        """
        
        if notification['details']:
            html += """
                <div class="details">
                    <h3>Detalhes:</h3>
                    <ul>
            """
            for key, value in notification['details'].items():
                html += f"<li><strong>{key}:</strong> {value}</li>"
            
            html += """
                    </ul>
                </div>
            """
        
        html += """
            </div>
            
            <div class="footer">
                <p>Sistema de Trading - Notificação Automática</p>
                <p>Esta é uma mensagem automática, não responda este email.</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _format_slack_fields(self, notification: Dict) -> List[Dict]:
        """Formata campos para Slack"""
        fields = [
            {
                'title': 'Tipo',
                'value': notification['type'],
                'short': True
            },
            {
                'title': 'Prioridade',
                'value': notification['priority'].upper(),
                'short': True
            }
        ]
        
        if notification['details']:
            for key, value in list(notification['details'].items())[:3]:  # Máximo 3 campos extras
                fields.append({
                    'title': key.replace('_', ' ').title(),
                    'value': str(value)[:100],  # Limitar tamanho
                    'short': len(str(value)) < 50
                })
        
        return fields
    
    def _format_discord_fields(self, notification: Dict) -> List[Dict]:
        """Formata campos para Discord"""
        fields = [
            {
                'name': 'Tipo',
                'value': notification['type'],
                'inline': True
            },
            {
                'name': 'Prioridade',
                'value': notification['priority'].upper(),
                'inline': True
            }
        ]
        
        if notification['details']:
            for key, value in list(notification['details'].items())[:3]:
                fields.append({
                    'name': key.replace('_', ' ').title(),
                    'value': str(value)[:1024],  # Limite do Discord
                    'inline': len(str(value)) < 50
                })
        
        return fields
    
    def _format_telegram_message(self, notification: Dict) -> str:
        """Formata mensagem para Telegram"""
        message = f"{notification['icon']} *{notification['title']}*\n\n"
        message += f"{notification['message']}\n\n"
        message += f"📊 *Tipo:* `{notification['type']}`\n"
        message += f"⚠️ *Prioridade:* `{notification['priority'].upper()}`\n"
        message += f"🕐 *Horário:* `{notification['timestamp']}`\n"
        
        if notification['details']:
            message += "\n*Detalhes:*\n"
            for key, value in notification['details'].items():
                message += f"• *{key.replace('_', ' ').title()}:* `{value}`\n"
        
        message += "\n_Sistema de Trading - Notificação Automática_"
        
        return message
    
    def _add_to_history(self, notification: Dict):
        """Adiciona notificação ao histórico"""
        self.notification_history.append(notification)
        
        # Manter tamanho máximo
        if len(self.notification_history) > self.max_history_size:
            self.notification_history = self.notification_history[-self.max_history_size:]
    
    def get_notification_history(self, limit: int = 50, 
                               notification_type: str = None,
                               priority: str = None) -> List[Dict]:
        """Obtém histórico de notificações com filtros opcionais"""
        history = self.notification_history.copy()
        
        # Aplicar filtros
        if notification_type:
            history = [n for n in history if n['type'] == notification_type]
        
        if priority:
            history = [n for n in history if n['priority'] == priority]
        
        # Ordenar por timestamp (mais recentes primeiro)
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return history[:limit]
    
    def get_notification_stats(self, days: int = 7) -> Dict:
        """Obtém estatísticas de notificações dos últimos N dias"""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_notifications = [
            n for n in self.notification_history 
            if datetime.fromisoformat(n['timestamp']) > cutoff_date
        ]
        
        stats = {
            'total_notifications': len(recent_notifications),
            'by_type': {},
            'by_priority': {},
            'by_day': {},
            'success_rate': 0
        }
        
        # Estatísticas por tipo
        for notif in recent_notifications:
            notif_type = notif['type']
            priority = notif['priority']
            day = notif['timestamp'][:10]  # YYYY-MM-DD
            
            stats['by_type'][notif_type] = stats['by_type'].get(notif_type, 0) + 1
            stats['by_priority'][priority] = stats['by_priority'].get(priority, 0) + 1
            stats['by_day'][day] = stats['by_day'].get(day, 0) + 1
        
        return stats
    
    def test_notifications(self) -> Dict:
        """Testa todos os canais de notificação configurados"""
        test_results = {}
        
        test_notification = {
            'id': 'test_notification',
            'type': 'SYSTEM_HEALTH',
            'title': 'Teste de Notificações',
            'message': 'Esta é uma mensagem de teste para verificar se as notificações estão funcionando corretamente.',
            'details': {
                'test_time': datetime.now().isoformat(),
                'system_status': 'operational',
                'version': '2.0.0'
            },
            'priority': 'low',
            'timestamp': datetime.now().isoformat(),
            'icon': '🧪'
        }
        
        # Testar cada canal habilitado
        if self.config['email']['enabled']:
            test_results['email'] = self._send_email(test_notification)
        
        if self.config['webhook']['enabled']:
            test_results['webhook'] = self._send_webhook(test_notification)
        
        if self.config['slack']['enabled']:
            test_results['slack'] = self._send_slack(test_notification)
        
        if self.config['discord']['enabled']:
            test_results['discord'] = self._send_discord(test_notification)
        
        if self.config['telegram']['enabled']:
            test_results['telegram'] = self._send_telegram(test_notification)
        
        # Resumo
        successful_channels = [k for k, v in test_results.items() if v.get('success', False)]
        
        return {
            'test_completed': True,
            'channels_tested': len(test_results),
            'successful_channels': len(successful_channels),
            'results': test_results,
            'summary': f"{len(successful_channels)}/{len(test_results)} canais funcionando"
        }
    
    def update_config(self, new_config: Dict) -> bool:
        """Atualiza configuração de notificações"""
        try:
            # Validar configuração
            if self._validate_config(new_config):
                self.config.update(new_config)
                success = self.save_config()
                
                if success:
                    logger.info("[NOTIFICATIONS] Configuração atualizada")
                    
                    # Enviar notificação sobre a mudança
                    self.send_notification(
                        'CONFIG_CHANGED',
                        'Configuração de Notificações Atualizada',
                        'As configurações de notificação foram alteradas com sucesso.',
                        {'config_keys': list(new_config.keys())}
                    )
                
                return success
            else:
                logger.error("[NOTIFICATIONS] Configuração inválida")
                return False
                
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro ao atualizar configuração: {e}")
            return False
    
    def _validate_config(self, config: Dict) -> bool:
        """Valida configuração de notificações"""
        try:
            # Validações específicas por canal
            if 'email' in config:
                email_config = config['email']
                if email_config.get('enabled', False):
                    required_fields = ['smtp_server', 'username', 'password', 'from_email', 'to_emails']
                    for field in required_fields:
                        if not email_config.get(field):
                            logger.error(f"[NOTIFICATIONS] Campo obrigatório para email: {field}")
                            return False
            
            if 'webhook' in config:
                webhook_config = config['webhook']
                if webhook_config.get('enabled', False):
                    if not webhook_config.get('url'):
                        logger.error("[NOTIFICATIONS] URL obrigatória para webhook")
                        return False
            
            # Outras validações podem ser adicionadas aqui
            
            return True
            
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro na validação: {e}")
            return False


# ==================== INTEGRAÇÃO COM CONFIG MIDDLEWARE ====================

def create_config_notification_callbacks():
    """Cria callbacks para integrar notificações com mudanças de configuração"""
    
    notification_service = NotificationService()
    
    def on_config_changed(old_config: Dict, new_config: Dict):
        """Callback chamado quando configuração muda"""
        try:
            # Calcular mudanças
            changes = []
            
            def find_changes(old_dict, new_dict, path=""):
                for key, new_value in new_dict.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    if key not in old_dict:
                        changes.append(f"Adicionado {current_path} = {new_value}")
                    elif isinstance(new_value, dict) and isinstance(old_dict[key], dict):
                        find_changes(old_dict[key], new_value, current_path)
                    elif old_dict[key] != new_value:
                        changes.append(f"Alterado {current_path}: {old_dict[key]} → {new_value}")
            
            find_changes(old_config, new_config)
            
            if changes:
                # Determinar prioridade baseada no número de mudanças
                priority = 'high' if len(changes) > 10 else 'medium' if len(changes) > 5 else 'low'
                
                notification_service.send_notification(
                    'CONFIG_CHANGED',
                    f'Configuração Alterada ({len(changes)} mudanças)',
                    f'As configurações do sistema foram modificadas. Total de mudanças: {len(changes)}',
                    {
                        'total_changes': len(changes),
                        'changed_keys': [change.split(' ')[1].split(' ')[0] for change in changes[:5]],
                        'sample_changes': changes[:3]
                    },
                    priority
                )
        
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro no callback de mudança: {e}")
    
    def on_config_applied(applied_components: List[str]):
        """Callback chamado quando configuração é aplicada"""
        try:
            notification_service.send_notification(
                'CONFIG_APPLIED',
                'Configuração Aplicada com Sucesso',
                f'Nova configuração foi aplicada a {len(applied_components)} componentes do sistema.',
                {
                    'applied_components': applied_components,
                    'application_time': datetime.now().isoformat()
                }
            )
        
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro no callback de aplicação: {e}")
    
    def on_config_error(error_message: str, config_data: Dict = None):
        """Callback chamado quando há erro na configuração"""
        try:
            notification_service.send_notification(
                'CONFIG_ERROR',
                'Erro na Configuração',
                f'Ocorreu um erro ao processar configuração: {error_message}',
                {
                    'error_message': error_message,
                    'config_snapshot': str(config_data)[:200] if config_data else None,
                    'error_time': datetime.now().isoformat()
                },
                'high'
            )
        
        except Exception as e:
            logger.error(f"[NOTIFICATIONS] Erro no callback de erro: {e}")
    
    return {
        'on_config_changed': on_config_changed,
        'on_config_applied': on_config_applied,
        'on_config_error': on_config_error
    }


# ==================== GLOBAL INSTANCE ====================

# Instância global do serviço de notificações
notification_service = NotificationService()

def send_config_notification(notification_type: str, title: str, message: str, details: Dict = None):
    """Função utilitária para enviar notificações relacionadas a configurações"""
    return notification_service.send_notification(notification_type, title, message, details)

def setup_notification_integration():
    """Configura integração entre notificações e middleware de configuração"""
    try:
        from middleware.config_middleware import config_middleware
        
        # Criar callbacks
        callbacks = create_config_notification_callbacks()
        
        # Registrar callbacks no middleware
        config_middleware.add_config_change_callback(callbacks['on_config_changed'])
        
        logger.info("[NOTIFICATIONS] Integração com middleware configurada")
        return True
        
    except ImportError:
        logger.warning("[NOTIFICATIONS] Middleware de configuração não disponível")
        return False
    except Exception as e:
        logger.error(f"[NOTIFICATIONS] Erro na integração: {e}")
        return False