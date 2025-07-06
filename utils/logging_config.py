# your_project/utils/logging_config.py

import logging
import os
import sys
import codecs
from config import app_config

# Configure encoding for Windows to handle emojis and special characters
if sys.platform.startswith('win'):
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

class WindowsCompatibleFormatter(logging.Formatter):
    """
    Custom logging formatter to replace emojis with compatible text for Windows consoles,
    and to ensure consistent log message formatting.
    """
    def format(self, record):
        msg = super().format(record)
        # Define emoji replacements for better compatibility in various environments
        emoji_replacements = {
            '🚀': '[START]', '📊': '[DATA]', '✅': '[OK]', '❌': '[ERROR]',
            '🛑': '[STOP]', '💰': '[BTC]', '📈': '[TRADE]', '🔄': '[API]',
            '⚙️': '[CTRL]', '🎯': '[TARGET]', '🧹': '[CLEAN]', '📝': '[SAMPLE]',
            '🔧': '[FIX]', '⏰': '[TIME]'
        }
        for emoji, replacement in emoji_replacements.items():
            msg = msg.replace(emoji, replacement)
        return msg

def setup_logging():
    """
    Sets up the logging configuration for the application.
    Logs will be written to a file and to the console.
    """
    # Ensure the data directory exists for log files
    os.makedirs(app_config.DATA_DIR, exist_ok=True)

    # Create a custom formatter instance
    formatter = WindowsCompatibleFormatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # File handler: logs to a file, with UTF-8 encoding
    file_handler = logging.FileHandler(app_config.LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Console handler: logs to the standard output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Get the root logger and set its level
    logger = logging.getLogger()
    logger.setLevel(app_config.LOG_LEVEL)
    
    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize the logger immediately when this module is imported
logger = setup_logging()
