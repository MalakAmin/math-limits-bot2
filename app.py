import os
import sys
import logging

# إعداد logging أولاً
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# التحقق من إصدار Python
logger.info(f"Python version: {sys.version}")
logger.info(f"Current directory: {os.getcwd()}")
logger.info(f"Files in directory: {os.listdir('.')}")

# محاولة استيراد المكتبات
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, 
        CommandHandler, 
        CallbackQueryHandler,
        ContextTypes
    )
    from dotenv import load_dotenv
    TELEGRAM_AVAILABLE = True
except ImportError as e:
    logger.error(f"خطأ في استيراد مكتبات Telegram: {e}")
    TELEGRAM_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
    logger.info(f"pandas version: {pd.__version__}")
except ImportError as e:
    logger.error(f"خطأ في استيراد pandas: {e}")
    PANDAS_AVAILABLE = False
    # إنشاء كائن وهمي
    class MockPandas:
        def read_excel(self, *args, **kwargs):
            return MockDataFrame()
    class MockDataFrame:
        def __init__(self):
            self.data = []
        def iterrows(self):
            return []
        @property
        def shape(self):
            return (0, 0)
    pd = MockPandas()

if TELEGRAM_AVAILABLE:
    # تحميل متغيرات البيئة
    load_dotenv()

# متغيرات
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 10000))

# ... (بقية دوال load_correct_answers وغيرها تبقى كما هي)

def main():
    """الدالة الرئيسية"""
    if not TELEGRAM_AVAILABLE:
        logger.error("مكتبة python-telegram-bot غير مثبتة!")
        return
    
    if not TOKEN:
        logger.error("TOKEN غير موجود! تأكد من إعداد TELEGRAM_BOT_TOKEN")
        return
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("begin", begin_test))
    application.add_handler(CommandHandler("results", results_command))
    application.add_handler(CallbackQueryHandler(handle_answer))
    
    # التحقق إذا كان على Render
    is_render = os.getenv('RENDER', '').lower() in ['true', '1', 'yes']
    
    if is_render:
        # على Render - استخدام webhook
        webhook_url = f"https://{os.getenv('RENDER_SERVICE_NAME', '')}.onrender.com/{TOKEN}"
        logger.info(f"Using webhook on Render: {webhook_url}")
        
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=webhook_url,
            drop_pending_updates=True
        )
    else:
        # محلي - استخدام polling
        logger.info("Running locally with polling...")
        application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
