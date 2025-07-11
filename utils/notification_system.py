# utils/notification_system.py
import smtplib
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from utils.logging_config import logger

class SimpleNotificationSystem:
    def __init__(self):
        # Configurações (adicione no seu config.py)
        self.email_enabled = True  # Ativar/desativar email
        self.discord_enabled = False  # Ativar/desativar Discord
        self.browser_enabled = True  # Notificações no navegador
        
        # Email settings
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.email_user = "seu_email@gmail.com"  # Configurar no .env
        self.email_password = "sua_senha_app"    # App password do Gmail
        self.notify_email = "destino@email.com"  # Email para receber notificações
        
        # Discord webhook (opcional)
        self.discord_webhook = "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
        
        # Armazenar últimos sinais para evitar spam
        self.last_signals = []

    def send_signal_notification(self, signal_data):
        """Envia notificação quando um novo sinal é gerado"""
        try:
            # Verificar se é um sinal novo (evitar duplicatas)
            signal_id = f"{signal_data.get('type')}_{signal_data.get('entry')}_{signal_data.get('created_at')[:16]}"
            
            if signal_id in self.last_signals:
                return  # Sinal já notificado
            
            # Adicionar à lista (manter apenas os últimos 10)
            self.last_signals.append(signal_id)
            if len(self.last_signals) > 10:
                self.last_signals.pop(0)
            
            # Preparar dados da mensagem
            message_data = self._format_signal_message(signal_data)
            
            # Enviar por todos os canais habilitados
            if self.email_enabled:
                self._send_email_notification(message_data)
            
            if self.discord_enabled:
                self._send_discord_notification(message_data)
            
            # Salvar para notificação no navegador
            self._save_browser_notification(message_data)
            
            logger.info(f"[NOTIFICATION] Sinal notificado: {signal_data.get('type')} - {signal_data.get('entry')}")
            
        except Exception as e:
            logger.error(f"[NOTIFICATION] Erro ao enviar notificação: {e}")

    def _format_signal_message(self, signal_data):
        """Formata a mensagem do sinal"""
        signal_type = signal_data.get('type', 'UNKNOWN')
        entry_price = signal_data.get('entry', 0)
        confidence = signal_data.get('confidence', 0)
        targets = signal_data.get('targets', [])
        stop_loss = signal_data.get('stop_loss', 0)
        
        # Emoji baseado no tipo
        emoji = "🟢" if signal_type == "BUY" else "🔴" if signal_type == "SELL" else "⚪"
        
        # Formatação básica
        message = {
            'title': f"{emoji} NOVO SINAL {signal_type}",
            'entry': f"${entry_price:,.2f}",
            'confidence': f"{confidence:.1f}%",
            'targets': [f"${t:,.2f}" for t in targets[:3]],  # Apenas 3 primeiros targets
            'stop_loss': f"${stop_loss:,.2f}" if stop_loss else "N/A",
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        }
        
        return message

    def _send_email_notification(self, message_data):
        """Envia notificação por email"""
        try:
            # Criar mensagem
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = self.notify_email
            msg['Subject'] = f"🚨 {message_data['title']} - Bitcoin Trading"
            
            # Corpo do email (HTML simples)
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #2563eb;">{message_data['title']}</h2>
                <div style="background: #f8fafc; padding: 15px; border-radius: 8px; margin: 10px 0;">
                    <p><strong>📍 Preço de Entrada:</strong> {message_data['entry']}</p>
                    <p><strong>🎯 Targets:</strong> {' | '.join(message_data['targets'])}</p>
                    <p><strong>🛑 Stop Loss:</strong> {message_data['stop_loss']}</p>
                    <p><strong>📊 Confiança:</strong> {message_data['confidence']}</p>
                    <p><strong>⏰ Horário:</strong> {message_data['timestamp']}</p>
                </div>
                <p style="color: #6b7280; font-size: 12px;">
                    Gerado pelo Bitcoin Trading System Enhanced
                </p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            # Enviar email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            server.send_message(msg)
            server.quit()
            
            logger.info("[NOTIFICATION] Email enviado com sucesso")
            
        except Exception as e:
            logger.error(f"[NOTIFICATION] Erro ao enviar email: {e}")

    def _send_discord_notification(self, message_data):
        """Envia notificação para Discord (opcional)"""
        try:
            if not self.discord_webhook:
                return
            
            # Cor baseada no tipo de sinal
            color = 0x10b981 if "BUY" in message_data['title'] else 0xef4444
            
            embed = {
                "title": message_data['title'],
                "color": color,
                "fields": [
                    {"name": "📍 Entrada", "value": message_data['entry'], "inline": True},
                    {"name": "📊 Confiança", "value": message_data['confidence'], "inline": True},
                    {"name": "🎯 Targets", "value": "\n".join(message_data['targets']), "inline": False},
                    {"name": "🛑 Stop Loss", "value": message_data['stop_loss'], "inline": True}
                ],
                "timestamp": datetime.now().isoformat(),
                "footer": {"text": "Bitcoin Trading System Enhanced"}
            }
            
            payload = {"embeds": [embed]}
            
            response = requests.post(self.discord_webhook, json=payload)
            if response.status_code == 204:
                logger.info("[NOTIFICATION] Discord notificado com sucesso")
            
        except Exception as e:
            logger.error(f"[NOTIFICATION] Erro ao enviar Discord: {e}")

    def _save_browser_notification(self, message_data):
        """Salva notificação para exibir no navegador"""
        try:
            # Salvar em arquivo JSON para o frontend ler
            notification = {
                'id': datetime.now().timestamp(),
                'type': 'signal',
                'title': message_data['title'],
                'message': f"Entrada: {message_data['entry']} | Confiança: {message_data['confidence']}",
                'timestamp': message_data['timestamp'],
                'read': False
            }
            
            # Ler notificações existentes
            try:
                with open('static/notifications.json', 'r') as f:
                    notifications = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                notifications = []
            
            # Adicionar nova notificação
            notifications.append(notification)
            
            # Manter apenas as últimas 20 notificações
            notifications = notifications[-20:]
            
            # Salvar de volta
            with open('static/notifications.json', 'w') as f:
                json.dump(notifications, f, indent=2)
            
            logger.info("[NOTIFICATION] Notificação salva para o navegador")
            
        except Exception as e:
            logger.error(f"[NOTIFICATION] Erro ao salvar notificação do navegador: {e}")

    def test_notification(self):
        """Testa o sistema de notificação"""
        test_signal = {
            'type': 'BUY',
            'entry': 45250.75,
            'targets': [46000, 46500, 47000],
            'stop_loss': 44800,
            'confidence': 85.5,
            'created_at': datetime.now().isoformat()
        }
        
        logger.info("[NOTIFICATION] Enviando notificação de teste...")
        self.send_signal_notification(test_signal)

# Instância global
notification_system = SimpleNotificationSystem()


