import os
import logging
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ContextTypes, 
    filters
)
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# متغيرات
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8443))
EXCEL_FILE = 'Answers.xlsx'
IMAGES_BASE_DIR = 'images'

# تحميل الإجابات الصحيحة
def load_correct_answers():
    """تحميل الإجابات الصحيحة من ملف Excel"""
    try:
        df = pd.read_excel(EXCEL_FILE)
        
        # إنشاء قاموس للإجابات الصحيحة
        correct_answers = {}
        
        for _, row in df.iterrows():
            question_num = int(row['image number'])
            q_type = row['Question Type'].strip().lower()
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
        return {}

# وظيفة مساعدة للحصول على مسار الصورة
def get_image_path(question_num):
    """الحصول على مسار الصورة بناءً على رقم السؤال"""
    if 1 <= question_num <= 19:
        folder = "True or False"
    elif 20 <= question_num <= 45:
        folder = "mcq"
    else:
        return None
    
    # عدة صيغ محتملة للصورة
    possible_paths = [
        os.path.join(IMAGES_BASE_DIR, folder, f"{question_num}.png"),
        os.path.join(IMAGES_BASE_DIR, folder, f"{question_num}.jpg"),
        os.path.join(IMAGES_BASE_DIR, folder, f"Q{question_num}.png"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    logger.warning(f"لم يتم العثور على صورة للسؤال {question_num}")
    return None

# قاموس لحفظ إجابات المستخدمين
user_sessions = {}
correct_answers = load_correct_answers()

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء الاختبار"""
    user_id = update.effective_user.id
    
    await update.message.reply_text(
        "📚 **مرحباً بك في بوت اختبار الرياضيات!**\n\n"
        "🎯 **معلومات عن الاختبار:**\n"
        "• عدد الأسئلة: 45 سؤالاً\n"
        "• الأسئلة 1-19: صح/خطأ (True/False)\n"
        "• الأسئلة 20-45: اختيار من متعدد (MCQ)\n\n"
        "🔄 **كيفية الاستخدام:**\n"
        "1. اضغط /begin لبدء الاختبار\n"
        "2. سأرسل لك كل سؤال على حدة\n"
        "3. اختر الإجابة المناسبة\n"
        "4. في النهاية سأظهر لك نتيجتك\n\n"
        "📊 **لرؤية النتيجة:** /results\n"
        "🔄 **لإعادة الاختبار:** /start\n"
        "❓ **للمساعدة:** /help"
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
        "🚀 **تم تهيئة الاختبار!**\n"
        f"عدد الأسئلة: {len(correct_answers)}\n\n"
        "سيبدأ الاختبار الآن..."
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
    
    # استخراج البيانات من callback
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
    
    # إرسال السؤال التالي بعد تأخير بسيط
    import asyncio
    await asyncio.sleep(1)
    
    await send_question(update, context, user_id)

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    """عرض النتائج"""
    if user_id is None:
        user_id = update.effective_user.id
    
    if user_id not in user_sessions:
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
        f"🔄 لإعادة الاختبار: /start\n"
        f"📤 لتصدير النتيجة: /export"
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

async def export_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تصدير النتائج لملف Excel"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        await update.message.reply_text("⚠️ لا توجد جلسة نشطة")
        return
    
    session = user_sessions[user_id]
    
    # إنشاء DataFrame للنتائج
    results_data = []
    
    for q_num, ans_data in session['answers'].items():
        results_data.append({
            'رقم السؤال': q_num,
            'نوع السؤال': ans_data['type'].upper(),
            'الإجابة الصحيحة': ans_data['correct_answer'].upper(),
            'إجابة الطالب': ans_data['user_answer'].upper() if ans_data['user_answer'] else 'لم يُجب',
            'صحيح؟': 'نعم' if ans_data['is_correct'] else 'لا'
        })
    
    df = pd.DataFrame(results_data)
    
    # حفظ في ملف مؤقت
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w+b', suffix='.xlsx', delete=False) as tmp:
        df.to_excel(tmp.name, index=False)
        
        # إرسال الملف للمستخدم
        with open(tmp.name, 'rb') as file:
            await update.message.reply_document(
                document=file,
                filename=f"نتيجة_الاختبار_{user_id}.xlsx",
                caption="📎 **ملف نتائج الاختبار**"
            )
        
        # تنظيف الملف المؤقت
        os.unlink(tmp.name)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض رسالة المساعدة"""
    help_text = (
        "🤖 **بوت اختبار الرياضيات - التعليمات**\n\n"
        "📋 **الأوامر المتاحة:**\n"
        "/start - بدء جلسة جديدة\n"
        "/begin - بدء الاختبار\n"
        "/results - عرض النتائج الحالية\n"
        "/export - تصدير النتائج لملف Excel\n"
        "/help - عرض هذه التعليمات\n\n"
        "🎯 **أنواع الأسئلة:**\n"
        "• 1-19: صح/خطأ (✅/❌)\n"
        "• 20-45: اختيار من متعدد (أ/ب/ج/د)\n\n"
        "⚠️ **ملاحظات:**\n"
        "• لا يمكنك تغيير إجابتك بعد الاختيار\n"
        "• يمكنك إعادة الاختبار متى شئت"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء"""
    logger.error(f"حدث خطأ: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى أو استخدام /start"
        )

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("begin", begin_test))
    application.add_handler(CommandHandler("results", results_command))
    application.add_handler(CommandHandler("export", export_results))
    application.add_handler(CommandHandler("help", help_command))
    
    # handler للإجابات (callback queries)
    application.add_handler(CallbackQueryHandler(handle_answer))
    
    # handler للأخطاء
    application.add_error_handler(error_handler)
    
    # تشغيل البوت
    if os.getenv('RENDER'):
        # التشغيل على Render
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"https://math-limits-bot2.onrender.com/{TOKEN}"
        )
    else:
        # التشغيل المحلي
        application.run_polling()

if __name__ == '__main__':
    main()
