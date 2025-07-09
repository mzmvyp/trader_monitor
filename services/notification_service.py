# services/notification_service.py - Sistema de notificações multi-canal

import os
import json
import sqlite3
import smtplib
import requests
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.logging_config import logger

class NotificationService:
    """
    Serviço de notificações que suporta múltiplos canais:
    - Email (SMTP)
    - Slack (Webhook)
    - Discord (Webhook)
    - Telegram (Bot API)
    - Webhook genérico
    """
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join('data', 'notifications.db')
        
        # Configurações dos canais (serão carregadas do banco ou arquivo)
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
            },
            'webhook': {
                'enabled': False,
                'url': '',
                'headers': {},
                'method': 'POST'
            }
        }
        
        # Tipos de notificação e suas prioridades
        self.notification_types = {
            'CONFIG_CHANGED': 'medium',
            'CONFIG_APPLIED': 'low',
            'CONFIG_ERROR': 'high',
            'SYSTEM_HEALTH': 'high',
            'SYSTEM_STATUS': 'medium',
            'SYSTEM_ERROR': 'critical',
            'TRADING_SIGNAL': 'medium',
            'PERFORMANCE_ALERT': 'medium',
            'SECURITY_ALERT': 'critical',
            'MAINTENANCE': 'low',
            'MANUAL': 'medium'
        }
        
        # Cache para rate limiting
        self.last_notification_times = {}
        self.min_interval_between_notifications = 5  # segundos
        
        self.setup_database()
        self.load_config()
    
    def setup_database(self):
        """Configura banco de dados para histórico de notificações"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tabela de histórico de notificações
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notification_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT,
                    priority TEXT NOT NULL,
                    channels_sent TEXT,
                    sent_at TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT
                )
            ''')
            
            # Tabela de configurações de notificação
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notification_config (
                    id INTEGER PRIMARY KEY,
                    channel TEXT UNIQUE NOT NULL,
                    config_data TEXT NOT NULL,
                    enabled BOOLEAN DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("[NOTIFICATION] Banco de notificações inicializado")
            
        except Exception as e:
            logger.error(f"[NOTIFICATION] Erro ao configurar banco: {e}")
    
    def load_config(self):
        """Carrega configurações do banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT channel, config_data, enabled FROM notification_config')
            rows = cursor.fetchall()
            
            for row in rows:
                channel, config_data, enabled = row
                if channel in self.config:
                    channel_config = json.loads(config_data)
                    channel_config['enabled'] = bool(enabled)
                    self.config[channel] = channel_config
            
            conn.close()
            logger.info("[NOTIFICATION] Configurações carregadas")
            
        except Exception as e:
            logger.error(f"[NOTIFICATION] Erro ao carregar configurações: {e}")
    
    def save_config(self):
        """Salva configurações no banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.now().isoformat()
            
            for channel, config in self.config.items():
                config_data = config.copy()
                enabled = config_data.pop('enabled', False)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO notification_config 
                    (channel, config_data, enabled, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', (channel, json.dumps(config_data), enabled, timestamp))
            
            conn.commit()
            conn.close()
            
            logger.info("[NOTIFICATION] Configurações salvas")
            return True
            
        except Exception as e:
            logger.error(f"[NOTIFICATION] Erro ao salvar configurações: {e}")
            return False
    
    def send_notification(self, notification_type: str, title: str, message: str, 
                         details: Dict = None, priority: str = None) -> Dict[str, Any]:
        """
        Envia notificação através dos canais habilitados
        
        Args:
            notification_type: Tipo da notificação
            title: Título da notificação
            message: Mensagem principal
            details: Detalhes adicionais (dict)
            priority: Prioridade (low, medium, high, critical)
            
        Returns:
            Resultado do envio
        """
        try:
            # Determinar prioridade
            if priority is None:
                priority = self.notification_types.get(notification_type, 'medium')
            
            # Verificar rate limiting
            now = datetime.now()
            cache_key = f"{notification_type}_{title}"
            
            if cache_key in self.last_notification_times:
                time_diff = (now - self.last_notification_times[cache_key]).total_seconds()
                if time_diff < self.min_interval_between_notifications:
                    logger.debug(f"[NOTIFICATION] Rate limiting: {cache_key}")
                    return {
                        'success': False,
                        'error': 'Rate limited',
                        'retry_after': self.min_interval_between_notifications - time_diff
                    }
            
            self.last_notification_times[cache_key] = now
            
            # Preparar dados da notificação
            notification_data = {
                'type': notification_type,
                'title': title,
                'message': message,
                'details': details or {},
                'priority': priority,
                'timestamp': now.isoformat()
            }
            
            # Enviar para canais habilitados
            sent_channels = []
            errors = []
            
            for channel, config in self.config.items():
                if config.get('enabled', False):
                    try:
                        success = self._send_to_channel(channel, notification_data)
                        if success:
                            sent_channels.append(channel)
                        else:
                            errors.append(f"{channel}: failed to send")
                    except Exception as e:
                        errors.append(f"{channel}: {str(e)}")
                        logger.error(f"[NOTIFICATION] Erro no canal {channel}: {e}")
            
            # Registrar no histórico
            self._save_to_history(notification_data, sent_channels, len(errors) == 0, errors)
            
            # Resultado
            result = {
                'success': len(sent_channels) > 0,
                'channels_sent': sent_channels,
                'total_channels': len([c for c in self.config.values() if c.get('enabled')]),
                'timestamp': now.isoformat()
            }
            
            if errors:
                result['errors'] = errors
            
            logger.info(f"[NOTIFICATION] Enviado para {len(sent_channels)} canais: {title}")
            return result
            
        except Exception as e:
            logger.error(f"[NOTIFICATION] Erro ao enviar notificação: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _send_to_channel(self, channel: str, notification_data: Dict) -> bool:
        """Envia notificação para um canal específico"""
        config = self.config[channel]
        
        if channel == 'email':
            return self._send_email(notification_data, config)
        elif channel == 'slack':
            return self._send_slack(notification_data, config)
        elif channel == 'discord':
            return self._send_discord(notification_data, config)
        elif channel == 'telegram':
            return self._send_telegram(notification_data, config)
        elif channel == 'webhook':
            return self._send_webhook(notification_data, config)
        else:
            logger.warning(f"[NOTIFICATION] Canal desconhecido: {channel}")
            return False
    
    def _send_email(self, notification_data: Dict, config: Dict) -> bool:
        """Envia notificação por email"""
        try:
            # Validar configuração
            required_fields = ['smtp_server', 'smtp_port', 'username', 'password', 'from_email', 'to_emails']
            for field in required_fields:
                if not config.get(field):
                    logger.error(f"[EMAIL] Campo obrigatório ausente: {field}")
                    return False
            
            # Criar mensagem
            msg = MIMEMultipart()
            msg['From'] = config['from_email']
            msg['To'] = ', '.join(config['to_emails'])
            msg['Subject'] = f"[{notification_data['priority'].upper()}] {notification_data['title']}"
            
            # Corpo da mensagem
            body = f"""
{notification_data['message']}

Tipo: {notification_data['type']}
Prioridade: {notification_data['priority']}
Timestamp: {notification_data['timestamp']}
"""
            
            if notification_data['details']:
                body += f"\nDetalhes:\n{json.dumps(notification_data['details'], indent=2)}"
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Enviar email
            server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
            server.starttls()
            server.login(config['username'], config['password'])
            server.send_message(msg)
            server.quit()
            
            logger.debug(f"[EMAIL] Enviado: {notification_data['title']}")
            return True
            
        except Exception as e:
            logger.error(f"[EMAIL] Erro ao enviar: {e}")
            return False
    
    def _send_slack(self, notification_data: Dict, config: Dict) -> bool:
        """Envia notificação para Slack"""
        try:
            # Validar webhook URL
            if not config.get('webhook_url'):
                logger.error("[SLACK] Webhook URL não configurada")
                return False
            
            # Determinar cor baseada na prioridade
            color_map = {
                'low': '#36a64f',      # Verde
                'medium': '#ffaa00',   # Amarelo
                'high': '#ff6600',     # Laranja
                'critical': '#ff0000'  # Vermelho
            }
            
            color = color_map.get(notification_data['priority'], '#36a64f')
            
            # Criar payload
            payload = {
                'channel': config.get('channel', '#trading-alerts'),
                'username': config.get('username', 'Trading System'),
                'attachments': [{
                    'color': color,
                    'title': notification_data['title'],
                    'text': notification_data['message'],
                    'fields': [
                        {
                            'title': 'Tipo',
                            'value': notification_data['type'],
                            'short': True
                        },
                        {
                            'title': 'Prioridade',
                            'value': notification_data['priority'].upper(),
                            'short': True
                        },
                        {
                            'title': 'Timestamp',
                            'value': notification_data['timestamp'],
                            'short': False
                        }
                    ],
                    'footer': 'Trading System',
                    'ts': int(datetime.now().timestamp())
                }]
            }
            
            # Adicionar detalhes se existirem
            if notification_data['details']:
                details_text = json.dumps(notification_data['details'], indent=2)
                payload['attachments'][0]['fields'].append({
                    'title': 'Detalhes',
                    'value': f"```{details_text}```",
                    'short': False
                })
            
            # Enviar
            response = requests.post(config['webhook_url'], json=payload, timeout=10)
            response.raise_for_status()
            
            logger.debug(f"[SLACK] Enviado: {notification_data['title']}")
            return True
            
        except Exception as e:
            logger.error(f"[SLACK] Erro ao enviar: {e}")
            return False
    
    def _send_discord(self, notification_data: Dict, config: Dict) -> bool:
        """Envia notificação para Discord"""
        try:
            # Validar webhook URL
            if not config.get('webhook_url'):
                logger.error("[DISCORD] Webhook URL não configurada")
                return False
            
            # Determinar cor baseada na prioridade
            color_map = {
                'low': 0x36a64f,      # Verde
                'medium': 0xffaa00,   # Amarelo
                'high': 0xff6600,     # Laranja
                'critical': 0xff0000  # Vermelho
            }
            
            color = color_map.get(notification_data['priority'], 0x36a64f)
            
            # Criar embed
            embed = {
                'title': notification_data['title'],
                'description': notification_data['message'],
                'color': color,
                'fields': [
                    {
                        'name': 'Tipo',
                        'value': notification_data['type'],
                        'inline': True
                    },
                    {
                        'name': 'Prioridade',
                        'value': notification_data['priority'].upper(),
                        'inline': True
                    },
                    {
                        'name': 'Timestamp',
                        'value': notification_data['timestamp'],
                        'inline': False
                    }
                ],
                'footer': {
                    'text': 'Trading System'
                },
                'timestamp': notification_data['timestamp']
            }
            
            # Adicionar detalhes se existirem
            if notification_data['details']:
                details_text = json.dumps(notification_data['details'], indent=2)
                embed['fields'].append({
                    'name': 'Detalhes',
                    'value': f"```json\n{details_text}\n```",
                    'inline': False
                })
            
            # Payload do Discord
            payload = {
                'username': config.get('username', 'Trading System'),
                'embeds': [embed]
            }
            
            # Enviar
            response = requests.post(config['webhook_url'], json=payload, timeout=10)
            response.raise_for_status()
            
            logger.debug(f"[DISCORD] Enviado: {notification_data['title']}")
            return True
            
        except Exception as e:
            logger.error(f"[DISCORD] Erro ao enviar: {e}")
            return False
    
    def _send_telegram(self, notification_data: Dict, config: Dict) -> bool:
        """Envia notificação para Telegram"""
        try:
            # Validar configuração
            if not config.get('bot_token') or not config.get('chat_id'):
                logger.error("[TELEGRAM] Bot token ou chat_id não configurados")
                return False
            
            # Criar mensagem
            priority_emoji = {
                'low': '🟢',
                'medium': '🟡', 
                'high': '🟠',
                'critical': '🔴'
            }
            
            emoji = priority_emoji.get(notification_data['priority'], '🟡')
            
            message = f"{emoji} *{notification_data['title']}*\n\n"
            message += f"{notification_data['message']}\n\n"
            message += f"📋 Tipo: `{notification_data['type']}`\n"
            message += f"⚠️ Prioridade: `{notification_data['priority'].upper()}`\n"
            message += f"🕒 Timestamp: `{notification_data['timestamp']}`"
            
            if notification_data['details']:
                details_text = json.dumps(notification_data['details'], indent=2)
                message += f"\n\n📄 Detalhes:\n```json\n{details_text}\n```"
            
            # URL da API do Telegram
            url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
            
            # Payload
            payload = {
                'chat_id': config['chat_id'],
                'text': message,
                'parse_mode': config.get('parse_mode', 'Markdown')
            }
            
            # Enviar
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.debug(f"[TELEGRAM] Enviado: {notification_data['title']}")
            return True
            
        except Exception as e:
            logger.error(f"[TELEGRAM] Erro ao enviar: {e}")
            return False
    
    def _send_webhook(self, notification_data: Dict, config: Dict) -> bool:
        """Envia notificação para webhook genérico"""
        try:
            # Validar URL
            if not config.get('url'):
                logger.error("[WEBHOOK] URL não configurada")
                return False
            
            # Preparar headers
            headers = config.get('headers', {})
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'
            
            # Método HTTP
            method = config.get('method', 'POST').upper()
            
            # Payload
            payload = {
                'notification': notification_data,
                'source': 'trading_system',
                'version': '2.0.0'
            }
            
            # Enviar
            if method == 'POST':
                response = requests.post(config['url'], json=payload, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(config['url'], json=payload, headers=headers, timeout=10)
            else:
                logger.error(f"[WEBHOOK] Método HTTP não suportado: {method}")
                return False
            
            response.raise_for_status()
            
            logger.debug(f"[WEBHOOK] Enviado: {notification_data['title']}")
            return True
            
        except Exception as e:
            logger.error(f"[WEBHOOK] Erro ao enviar: {e}")
            return False
    
    def _save_to_history(self, notification_data: Dict, sent_channels: List[str], 
                        success: bool, errors: List[str]):
        """Salva notificação no histórico"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO notification_history 
                (type, title, message, details, priority, channels_sent, sent_at, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                notification_data['type'],
                notification_data['title'],
                notification_data['message'],
                json.dumps(notification_data['details']),
                notification_data['priority'],
                ','.join(sent_channels),
                notification_data['timestamp'],
                success,
                '; '.join(errors) if errors else None
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[NOTIFICATION] Erro ao salvar histórico: {e}")
    
    def get_notification_history(self, limit: int = 50) -> List[Dict]:
        """Obtém histórico de notificações"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT type, title, message, details, priority, channels_sent, sent_at, success, error_message
                FROM notification_history
                ORDER BY sent_at DESC
                LIMIT ?
            ''', (limit,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'type': row[0],
                    'title': row[1],
                    'message': row[2],
                    'details': json.loads(row[3]) if row[3] else {},
                    'priority': row[4],
                    'channels_sent': row[5].split(',') if row[5] else [],
                    'sent_at': row[6],
                    'success': bool(row[7]),
                    'error_message': row[8]
                })
            
            conn.close()
            return history
            
        except Exception as e:
            logger.error(f"[NOTIFICATION] Erro ao obter histórico: {e}")
            return []
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas de notificações"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Total de notificações
            cursor.execute('SELECT COUNT(*) FROM notification_history')
            total_notifications = cursor.fetchone()[0]
            
            # Notificações bem-sucedidas
            cursor.execute('SELECT COUNT(*) FROM notification_history WHERE success = 1')
            successful_notifications = cursor.fetchone()[0]
            
            # Por tipo
            cursor.execute('''
                SELECT type, COUNT(*) 
                FROM notification_history 
                GROUP BY type 
                ORDER BY COUNT(*) DESC
            ''')
            by_type = dict(cursor.fetchall())
            
            # Por prioridade
            cursor.execute('''
                SELECT priority, COUNT(*) 
                FROM notification_history 
                GROUP BY priority 
                ORDER BY COUNT(*) DESC
            ''')
            by_priority = dict(cursor.fetchall())
            
            # Últimas 24h
            from datetime import datetime, timedelta
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()
            cursor.execute('SELECT COUNT(*) FROM notification_history WHERE sent_at > ?', (yesterday,))
            last_24h = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_notifications': total_notifications,
                'successful_notifications': successful_notifications,
                'success_rate': successful_notifications / total_notifications if total_notifications > 0 else 0,
                'by_type': by_type,
                'by_priority': by_priority,
                'last_24h': last_24h,
                'enabled_channels': [ch for ch, cfg in self.config.items() if cfg.get('enabled')],
                'total_channels': len([ch for ch, cfg in self.config.items() if cfg.get('enabled')])
            }
            
        except Exception as e:
            logger.error(f"[NOTIFICATION] Erro ao obter estatísticas: {e}")
            return {
                'total_notifications': 0,
                'successful_notifications': 0,
                'success_rate': 0,
                'by_type': {},
                'by_priority': {},
                'last_24h': 0,
                'enabled_channels': [],
                'total_channels': 0
            }
    
    def update_channel_config(self, channel: str, config: Dict) -> bool:
        """Atualiza configuração de um canal"""
        if channel not in self.config:
            logger.error(f"[NOTIFICATION] Canal desconhecido: {channel}")
            return False
        
        self.config[channel].update(config)
        return self.save_config()
    
    def enable_channel(self, channel: str) -> bool:
        """Habilita um canal de notificação"""
        if channel not in self.config:
            logger.error(f"[NOTIFICATION] Canal desconhecido: {channel}")
            return False
        
        self.config[channel]['enabled'] = True
        return self.save_config()
    
    def disable_channel(self, channel: str) -> bool:
        """Desabilita um canal de notificação"""
        if channel not in self.config:
            logger.error(f"[NOTIFICATION] Canal desconhecido: {channel}")
            return False
        
        self.config[channel]['enabled'] = False
        return self.save_config()
    
    def test_channel(self, channel: str) -> Dict[str, Any]:
        """Testa um canal de notificação"""
        if channel not in self.config:
            return {'success': False, 'error': f'Canal desconhecido: {channel}'}
        
        if not self.config[channel].get('enabled'):
            return {'success': False, 'error': f'Canal {channel} está desabilitado'}
        
        # Notificação de teste
        test_notification = {
            'type': 'TEST',
            'title': f'Teste do Canal {channel.title()}',
            'message': f'Esta é uma notificação de teste para verificar se o canal {channel} está funcionando corretamente.',
            'details': {
                'test_time': datetime.now().isoformat(),
                'channel': channel
            },
            'priority': 'low',
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            success = self._send_to_channel(channel, test_notification)
            return {
                'success': success,
                'message': f'Teste do canal {channel} {"bem-sucedido" if success else "falhou"}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


# ==================== INSTÂNCIA GLOBAL E FUNÇÕES AUXILIARES ====================

# Instância global do serviço de notificações
notification_service = NotificationService()

def setup_notification_integration():
    """Configura integração com outros sistemas"""
    try:
        # Configurar notificações básicas para desenvolvimento/teste
        # Em produção, estas configurações viriam do banco ou arquivo de config
        
        # Por enquanto, apenas inicializar sem configurações específicas
        # O usuário pode configurar via interface web ou API
        
        logger.info("[NOTIFICATION] Integração configurada")
        return True
        
    except Exception as e:
        logger.error(f"[NOTIFICATION] Erro na configuração de integração: {e}")
        return False

def send_system_notification(title: str, message: str, priority: str = 'medium', 
                           notification_type: str = 'SYSTEM_STATUS', details: Dict = None):
    """Função auxiliar para enviar notificações do sistema"""
    return notification_service.send_notification(
        notification_type=notification_type,
        title=title,
        message=message,
        details=details,
        priority=priority
    )

def configure_email_notifications(smtp_server: str, smtp_port: int, username: str, 
                                password: str, from_email: str, to_emails: List[str]) -> bool:
    """Configura notificações por email"""
    config = {
        'enabled': True,
        'smtp_server': smtp_server,
        'smtp_port': smtp_port,
        'username': username,
        'password': password,
        'from_email': from_email,
        'to_emails': to_emails
    }
    
    return notification_service.update_channel_config('email', config)

def configure_slack_notifications(webhook_url: str, channel: str = '#trading-alerts', 
                                 username: str = 'Trading System') -> bool:
    """Configura notificações do Slack"""
    config = {
        'enabled': True,
        'webhook_url': webhook_url,
        'channel': channel,
        'username': username
    }
    
    return notification_service.update_channel_config('slack', config)

def configure_discord_notifications(webhook_url: str, username: str = 'Trading System') -> bool:
    """Configura notificações do Discord"""
    config = {
        'enabled': True,
        'webhook_url': webhook_url,
        'username': username
    }
    
    return notification_service.update_channel_config('discord', config)

def configure_telegram_notifications(bot_token: str, chat_id: str, 
                                   parse_mode: str = 'Markdown') -> bool:
    """Configura notificações do Telegram"""
    config = {
        'enabled': True,
        'bot_token': bot_token,
        'chat_id': chat_id,
        'parse_mode': parse_mode
    }
    
    return notification_service.update_channel_config('telegram', config)