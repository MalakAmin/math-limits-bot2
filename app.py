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

# استيراد المكتبات
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, 
        CommandHandler, 
        CallbackQueryHandler,
        ContextTypes
    )
    from dotenv import load_dotenv
    import pandas as pd
    TELEGRAM_AVAILABLE = True
    PANDAS_AVAILABLE = True
    logger.info(f"pandas version: {pd.__version__}")
except ImportError as e:
    logger.error(f"خطأ في استيراد المكتبات: {e}")
    TELEGRAM_AVAILABLE = False
    PANDAS_AVAILABLE = False

# تحميل متغيرات البيئة
load_dotenv()

# متغيرات
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 10000))
IMAGES_BASE_DIR = 'Images'  # تأكد أن الحرف كبير I إذا كان المجلد Images

# تحميل الإجابات الصحيحة
def load_correct_answers():
    """تحميل الإجابات الصحيحة من ملف Excel"""
    try:
        df = pd.read_excel('Answers.xlsx')
        
        # إنشاء قاموس للإجابات الصحيحة
        correct_answers = {}
        
        for _, row in df.iterrows():
            question_num = int(row['image number'])
            q_type = str(row['Question Type']).strip().lower()
            answer = str(row['answer']).strip().lower()
            
            correct_answers[question_num] = {
                'type': q_type,
                'correct_answer': answer,
                'user_answer': None,
                'is_correct': False
            }
        
        logger.info(f"تم تحميل {len(correct_answers)} إجابة صحيحة")
        return correct_answers
    
    except Exception as e:
        logger.error(f"خطأ في تحميل ملف Excel: {e}")
        # إنشاء بيانات وهمية للاختبار
        return create_mock_data()

def create_mock_data():
    """إنشاء بيانات وهمية للاختبار"""
    logger.info("جاري إنشاء بيانات وهمية للاختبار")
    mock_data = {}
    
    for i in range(1, 20):
        mock_data[i] = {
            'type': 'tf',
            'correct_answer': 't' if i % 2 == 0 else 'f',
            'user_answer': None,
            'is_correct': False
        }
    
    for i in range(20, 46):
        answers = ['a', 'b', 'c', 'd']
        mock_data[i] = {
            'type': 'mcq',
            'correct_answer': answers[i % 4],
            'user_answer': None,
            'is_correct': False
        }
    
    return mock_data

# وظيفة للحصول على مسار الصورة
def get_image_path(question_num):
    """الحصول على مسار الصورة بناءً على رقم السؤال"""
    if 1 <= question_num <= 19:
        folder = "True or False"
    elif 20 <= question_num <= 45:
        folder = "mcq"
    else:
        return None
    
    # عدة صيغ محتملة
    image_name = f"{question_num}.png"
    path = os.path.join(IMAGES_BASE_DIR, folder, image_name)
    
    if os.path.exists(path):
        return path
    
    # محاولة صيغ أخرى
    alternative_paths = [
        os.path.join(IMAGES_BASE_DIR, folder, f"{question_num}.jpg"),
        os.path.join(IMAGES_BASE_DIR, folder, f"Q{question_num}.png"),
        os.path.join('images', folder, f"{question_num}.png"),  # حرف صغير i
    ]
    
    for alt_path in alternative_paths:
        if os.path.exists(alt_path):
            return alt_path
    
    logger.warning(f"لم يتم العثور على صورة للسؤال {question_num}")
    return None

# قاموس لحفظ إجابات المستخدمين
user_sessions = {}
correct_answers = load_correct_answers()

# تعريف الدوال
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء الاختبار"""
    user_id = update.effective_user.id
    
    await update.message.reply_text(
        "📚 **مرحباً بك في بوت اختبار الرياضيات!**\n\n"
        "🎯 **معلومات عن الاختبار:**\n"
        "• عدد الأسئلة: 45 سؤالاً\n"
        "• الأسئلة 1-19: صح/خطأ\n"
        "• الأسئلة 20-45: اختيار من متعدد\n\n"
        "🔄 **لبدء الاختبار:**\n"
        "اضغط /begin"
    )

async def begin_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إرسال الأسئلة"""
    user_id = update.effective_user.id
    
    # تهيئة جلسة المستخدم
    user_sessions[user_id] = {
        'current_question': 1,
        'total_questions': len(correct_answers),
        'score': 0,
        'answers': {},
        'completed': False,
        'username': update.effective_user.username or update.effective_user.first_name
    }
    
    # نسخ الإجابات الصحيحة
    for q_num, data in correct_answers.items():
        user_sessions[user_id]['answers'][q_num] = {
            'type': data['type'],
            'correct_answer': data['correct_answer'],
            'user_answer': None,
            'is_correct': False
        }
    
    await update.message.reply_text(
        f"🚀 **تم تهيئة الاختبار!**\n"
        f"عدد الأسئلة: {len(correct_answers)}\n\n"
        "جاري إرسال أول سؤال..."
    )
    
    # إرسال أول سؤال
    await send_question(update, context, user_id)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """إرسال سؤال للمستخدم"""
    session = user_sessions[user_id]
    question_num = session['current_question']
    
    if question_num > session['total_questions']:
        # انتهاء الأسئلة
        await show_results(update, context, user_id)
        return
    
    # الحصول على مسار الصورة
    image_path = get_image_path(question_num)
    
    if not image_path:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⚠️ لم يتم العثور على صورة للسؤال {question_num}"
        )
        session['current_question'] += 1
        await send_question(update, context, user_id)
        return
    
    # تحديد نوع السؤال وبناء الأزرار
    question_data = session['answers'][question_num]
    
    if question_data['type'] == 'tf':
        # أزرار صح/خطأ
        keyboard = [
            [
                InlineKeyboardButton("✅ صح (True)", callback_data=f"answer_{question_num}_t"),
                InlineKeyboardButton("❌ خطأ (False)", callback_data=f"answer_{question_num}_f")
            ]
        ]
        question_type_text = "📝 **سؤال صح/خطأ**"
    else:
        # أزرار MCQ
        keyboard = [
            [
                InlineKeyboardButton("أ", callback_data=f"answer_{question_num}_a"),
                InlineKeyboardButton("ب", callback_data=f"answer_{question_num}_b"),
                InlineKeyboardButton("ج", callback_data=f"answer_{question_num}_c"),
                InlineKeyboardButton("د", callback_data=f"answer_{question_num}_d")
            ]
        ]
        question_type_text = "🔠 **سؤال اختيار من متعدد**"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # إرسال الصورة مع الأزرار
        with open(image_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo,
                caption=f"**السؤال رقم: {question_num}**\n{question_type_text}\n\nاختر الإجابة الصحيحة:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"خطأ في إرسال الصورة {image_path}: {e}")
        # إرسال رسالة بديلة
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"**السؤال رقم: {question_num}**\n{question_type_text}\n\nاختر الإجابة الصحيحة:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إجابة المستخدم"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_sessions:
        await query.edit_message_text("⚠️ الجلسة منتهية. اضغط /start للبدء")
        return
    
    session = user_sessions[user_id]
    
    # استخراج البيانات
    data = query.data
    parts = data.split('_')
    
    if len(parts) != 3:
        return
    
    question_num = int(parts[1])
    user_answer = parts[2]
    
    # حفظ إجابة المستخدم
    if question_num in session['answers']:
        session['answers'][question_num]['user_answer'] = user_answer
        
        # التحقق إذا كانت الإجابة صحيحة
        correct_answer = session['answers'][question_num]['correct_answer']
        if user_answer == correct_answer:
            session['answers'][question_num]['is_correct'] = True
            session['score'] += 1
    
    # الانتقال للسؤال التالي
    session['current_question'] += 1
    
    # إرسال تأكيد
    await query.edit_message_text(
        f"✅ **تم حفظ إجابتك للسؤال {question_num}**\n"
        f"إجابتك: {user_answer.upper()}\n\n"
        f"جاري تحميل السؤال التالي..."
    )
    
    # إرسال السؤال التالي
    await send_question(update, context, user_id)

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    """عرض النتائج"""
    if user_id is None:
        user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        if hasattr(update, 'message'):
            await update.message.reply_text("⚠️ لا توجد جلسة نشطة. اضغط /start للبدء")
        return
    
    session = user_sessions[user_id]
    
    # حساب النتيجة
    total = session['total_questions']
    score = session['score']
    percentage = (score / total) * 100 if total > 0 else 0
    
    # إنشاء تفاصيل الإجابات
    details = "📊 **تفاصيل الإجابات:**\n\n"
    
    for q_num in range(1, total + 1):
        if q_num in session['answers']:
            ans = session['answers'][q_num]
            user_ans = ans['user_answer'] or "لم يُجب"
            correct_ans = ans['correct_answer']
            is_correct = ans['is_correct']
            
            emoji = "✅" if is_correct else "❌"
            details += f"{emoji} سؤال {q_num}: إجابتك ({user_ans.upper()}) | الصحيحة ({correct_ans.upper()})\n"
    
    # رسالة النتيجة
    result_message = (
        f"🎉 **تم الانتهاء من الاختبار!**\n\n"
        f"📈 **النتيجة النهائية:**\n"
        f"• عدد الأسئلة: {total}\n"
        f"• الإجابات الصحيحة: {score}\n"
        f"• الإجابات الخاطئة: {total - score}\n"
        f"• النسبة المئوية: {percentage:.1f}%\n\n"
        f"{details}\n"
        f"🔄 لإعادة الاختبار: /start"
    )
    
    if hasattr(update, 'message'):
        await update.message.reply_text(result_message, parse_mode='Markdown')
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=result_message,
            parse_mode='Markdown'
        )
    
    session['completed'] = True

async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض النتيجة الحالية"""
    await show_results(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض رسالة المساعدة"""
    help_text = (
        "🤖 **بوت اختبار الرياضيات - التعليمات**\n\n"
        "📋 **الأوامر المتاحة:**\n"
        "/start - بدء جلسة جديدة\n"
        "/begin - بدء الاختبار\n"
        "/results - عرض النتائج\n"
        "/help - عرض التعليمات\n\n"
        "🎯 **أنواع الأسئلة:**\n"
        "• 1-19: صح/خطأ (✅/❌)\n"
        "• 20-45: اختيار من متعدد (أ/ب/ج/د)"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    """الدالة الرئيسية"""
    if not TOKEN:
        logger.error("❌ TOKEN غير موجود! تأكد من إعداد TELEGRAM_BOT_TOKEN في متغيرات البيئة")
        return
    
    logger.info("🚀 بدء تشغيل بوت الرياضيات...")
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("begin", begin_test))
    application.add_handler(CommandHandler("results", results_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(handle_answer))
    
    # التحقق إذا كان على Render
    is_render = os.getenv('RENDER', '').lower() in ['true', '1', 'yes']
    
    if is_render:
        # على Render - استخدام webhook
        render_service_name = os.getenv('RENDER_SERVICE_NAME', 'math-limits-bot')
        webhook_url = f"https://{render_service_name}.onrender.com/{TOKEN}"
        
        logger.info(f"🌐 استخدام webhook على Render: {webhook_url}")
        
        # بدء webhook
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=webhook_url,
            drop_pending_updates=True
        )
    else:
        # محلي - استخدام polling
        logger.info("💻 التشغيل محلياً باستخدام polling...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )

if __name__ == '__main__':
    main()
