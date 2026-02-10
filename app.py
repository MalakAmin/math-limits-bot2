import os
import sys
import logging
import asyncio

# إعداد logging أولاً
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# التحقق من إصدار Python
logger.info(f"Python version: {sys.version}")

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
    logger.info("✅ جميع المكتبات مثبتة بنجاح")
except ImportError as e:
    logger.error(f"❌ خطأ في استيراد المكتبات: {e}")
    sys.exit(1)

# تحميل متغيرات البيئة
load_dotenv()

# متغيرات
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 10000))
IMAGES_BASE_DIR = 'Images'

def load_correct_answers():
    """تحميل الإجابات الصحيحة من ملف Excel"""
    try:
        # قراءة ملف Excel
        df = pd.read_excel('Answers.xlsx')
        logger.info(f"✅ تم تحميل ملف Excel بنجاح")
        logger.info(f"📊 شكل البيانات: {df.shape}")
        
        # عرض أسماء الأعمدة كما يراها pandas
        logger.info(f"📋 أسماء الأعمدة في pandas: {list(df.columns)}")
        
        # تنظيف أسماء الأعمدة (إزالة مسافات زائدة)
        df.columns = df.columns.str.strip()
        logger.info(f"📋 أسماء الأعمدة بعد التنظيف: {list(df.columns)}")
        
        # التحقق من وجود الأعمدة المطلوبة
        required_columns = ['image number', 'Question Type', 'answer']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(f"❌ الأعمدة الناقصة: {missing_columns}")
            logger.error(f"❌ الأعمدة الموجودة: {list(df.columns)}")
            return create_mock_data()
        
        # إنشاء قاموس للإجابات الصحيحة
        correct_answers = {}
        
        for idx, row in df.iterrows():
            try:
                # استخدام الأسماء الصحيحة للأعمدة
                question_num = int(row['image number'])
                q_type = str(row['Question Type']).strip().lower()
                answer = str(row['answer']).strip().lower()
                
                # التحقق من صحة البيانات
                if q_type not in ['tf', 'mcq']:
                    logger.warning(f"⚠️ نوع سؤال غير معروف في الصف {idx+1}: {q_type}")
                    q_type = 'tf' if question_num <= 19 else 'mcq'
                
                if q_type == 'tf' and answer not in ['t', 'f']:
                    logger.warning(f"⚠️ إجابة tf غير صحيحة في الصف {idx+1}: {answer}")
                    answer = 't' if answer in ['true', 'صحيح', 'صح'] else 'f'
                
                if q_type == 'mcq' and answer not in ['a', 'b', 'c', 'd']:
                    logger.warning(f"⚠️ إجابة mcq غير صحيحة في الصف {idx+1}: {answer}")
                    answer = 'a'  # قيمة افتراضية
                
                correct_answers[question_num] = {
                    'type': q_type,
                    'correct_answer': answer,
                    'user_answer': None,
                    'is_correct': False
                }
                
                logger.debug(f"📝 سؤال {question_num}: نوع={q_type}, إجابة={answer}")
                
            except Exception as e:
                logger.warning(f"⚠️ خطأ في معالجة الصف {idx+1}: {e}")
                logger.warning(f"⚠️ بيانات الصف: {row.to_dict()}")
                continue
        
        logger.info(f"📊 تم تحميل {len(correct_answers)} إجابة صحيحة")
        
        # عرض إحصائيات
        tf_count = sum(1 for q in correct_answers.values() if q['type'] == 'tf')
        mcq_count = sum(1 for q in correct_answers.values() if q['type'] == 'mcq')
        logger.info(f"📈 الإحصائيات: TF={tf_count}, MCQ={mcq_count}")
        
        # عرض عينة
        logger.info("🔍 عينة من الأسئلة:")
        for q_num in sorted(correct_answers.keys())[:10]:
            data = correct_answers[q_num]
            logger.info(f"  {q_num}: {data['type']} -> {data['correct_answer']}")
        
        return correct_answers
    
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل ملف Excel: {e}", exc_info=True)
        logger.info("📝 جاري إنشاء بيانات وهمية للاختبار...")
        return create_mock_data()

def create_mock_data():
    """إنشاء بيانات وهمية للاختبار"""
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
    
    logger.info(f"📝 تم إنشاء {len(mock_data)} سؤال وهمي")
    return mock_data

def get_image_path(question_num):
    """الحصول على مسار الصورة بناءً على رقم السؤال"""
    if 1 <= question_num <= 19:
        folder = "True or False"
    elif 20 <= question_num <= 45:
        folder = "mcq"
    else:
        return None
    
    # مسارات محتملة
    base_paths = [
        os.path.join(IMAGES_BASE_DIR, folder, f"{question_num}.png"),
        os.path.join(IMAGES_BASE_DIR, folder, f"{question_num}.jpg"),
        os.path.join(IMAGES_BASE_DIR, folder, f"{question_num}.PNG"),
        os.path.join(IMAGES_BASE_DIR, folder, f"{question_num}.JPG"),
        os.path.join('images', folder, f"{question_num}.png"),  # حرف صغير
    ]
    
    for path in base_paths:
        if os.path.exists(path):
            logger.debug(f"📸 وجدت صورة: {path}")
            return path
    
    logger.warning(f"⚠️ لم أجد صورة للسؤال {question_num}")
    return None

# قاموس لحفظ إجابات المستخدمين
user_sessions = {}
correct_answers = load_correct_answers()

# تعريف الدوال
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء الاختبار"""
    user_id = update.effective_user.id
    logger.info(f"👤 المستخدم {user_id} بدأ الجلسة")
    
    await update.message.reply_text(
        "📚 **مرحباً بك في بوت اختبار الرياضيات!**\n\n"
        "🎯 **معلومات عن الاختبار:**\n"
        "• الأسئلة 1-19: صح/خطأ ✅/❌\n"
        "• الأسئلة 20-45: اختيار من متعدد 🔠\n"
        "• عدد الأسئلة: 45 سؤالاً\n\n"
        "🔄 **لبدء الاختبار:**\n"
        "اضغط /begin\n\n"
        "❓ **للمساعدة:** /help\n"
        "🔍 **لفحص الحالة:** /check"
    )

async def begin_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إرسال الأسئلة"""
    user_id = update.effective_user.id
    
    if user_id in user_sessions and not user_sessions[user_id]['completed']:
        await update.message.reply_text(
            "⚠️ لديك اختبار قيد التقدم!\n"
            "📊 لرؤية النتائج: /results\n"
            "🔄 لبدء اختبار جديد: /start"
        )
        return
    
    logger.info(f"🚀 المستخدم {user_id} بدأ الاختبار")
    
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
        f"✅ **تم تهيئة الاختبار!**\n"
        f"📊 عدد الأسئلة: {len(correct_answers)}\n\n"
        "⏳ جاري إرسال أول سؤال..."
    )
    
    # إرسال أول سؤال
    await send_question(update, context, user_id)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """إرسال سؤال للمستخدم"""
    session = user_sessions[user_id]
    question_num = session['current_question']
    
    if question_num > session['total_questions']:
        logger.info(f"🏁 المستخدم {user_id} أنهى جميع الأسئلة")
        await show_results(update, context, user_id)
        return
    
    logger.info(f"📨 إرسال السؤال {question_num} للمستخدم {user_id}")
    
    # الحصول على مسار الصورة
    image_path = get_image_path(question_num)
    
    if not image_path:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⚠️ لم أجد صورة للسؤال {question_num}\n"
                 f"جاري الانتقال للسؤال التالي..."
        )
        session['current_question'] += 1
        await asyncio.sleep(1)
        await send_question(update, context, user_id)
        return
    
    # تحديد نوع السؤال وبناء الأزرار
    question_data = session['answers'][question_num]
    
    if question_data['type'] == 'tf':
        keyboard = [
            [
                InlineKeyboardButton("✅ صح (True)", callback_data=f"answer_{question_num}_t"),
                InlineKeyboardButton("❌ خطأ (False)", callback_data=f"answer_{question_num}_f")
            ]
        ]
        question_type_text = "📝 **سؤال صح/خطأ**"
    else:
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
        with open(image_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo,
                caption=f"**السؤال رقم: {question_num}**\n{question_type_text}\n\nاختر الإجابة الصحيحة:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال الصورة: {e}")
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
    logger.info(f"📝 المستخدم {user_id} أجاب على سؤال")
    
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
            logger.debug(f"✅ إجابة صحيحة للسؤال {question_num}")
        else:
            logger.debug(f"❌ إجابة خاطئة للسؤال {question_num}")
    
    # الانتقال للسؤال التالي
    session['current_question'] += 1
    
    # إرسال تأكيد
    await query.edit_message_text(
        f"✅ **تم حفظ إجابتك**\n"
        f"السؤال: {question_num}\n"
        f"إجابتك: {user_answer.upper()}\n\n"
        f"⏳ جاري تحميل السؤال التالي..."
    )
    
    # انتظار ثم إرسال السؤال التالي
    await asyncio.sleep(1)
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
        f"• الإجابات الصحيحة: {score}/{total}\n"
        f"• النسبة المئوية: {percentage:.1f}%\n"
        f"• المستوى: {'ممتاز 🏆' if percentage >= 90 else 'جيد جداً ⭐' if percentage >= 75 else 'مقبول ✓' if percentage >= 50 else 'ضعف 📉'}\n\n"
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
    logger.info(f"📊 المستخدم {user_id} حصل على {score}/{total} ({percentage:.1f}%)")

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
        "/check - فحص حالة البوت\n"
        "/help - عرض التعليمات\n\n"
        "🎯 **أنواع الأسئلة:**\n"
        "• 1-19: صح/خطأ (✅/❌)\n"
        "• 20-45: اختيار من متعدد (أ/ب/ج/د)\n\n"
        "⚠️ **ملاحظات:**\n"
        "• الإجابة لا يمكن تغييرها بعد الاختيار\n"
        "• يمكنك إعادة الاختبار متى شئت"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فحص حالة البوت"""
    user_id = update.effective_user.id
    
    # التحقق من الصور
    tf_count = 0
    mcq_count = 0
    
    if os.path.exists('Images/True or False'):
        tf_files = [f for f in os.listdir('Images/True or False') if f.lower().endswith(('.png', '.jpg'))]
        tf_count = len(tf_files)
    
    if os.path.exists('Images/mcq'):
        mcq_files = [f for f in os.listdir('Images/mcq') if f.lower().endswith(('.png', '.jpg'))]
        mcq_count = len(mcq_files)
    
    check_message = (
        f"🔍 **فحص حالة البوت**\n\n"
        f"• حالة البوت: ✅ نشط\n"
        f"• عدد الأسئلة المحملة: {len(correct_answers)}\n"
        f"• الصور المتاحة: صح/خطأ={tf_count}, MCQ={mcq_count}\n"
        f"• جلسة المستخدم: {'✅ نشطة' if user_id in user_sessions else '❌ غير نشطة'}\n\n"
    )
    
    if user_id in user_sessions:
        session = user_sessions[user_id]
        check_message += f"📊 **تقدمك الحالي:**\n"
        check_message += f"• السؤال الحالي: {session['current_question']}/{session['total_questions']}\n"
        check_message += f"• النقاط الحالية: {session['score']}\n"
        check_message += f"• حالة الاختبار: {'مكتمل ✅' if session['completed'] else 'قيد التقدم ⏳'}\n\n"
    
    check_message += "🔄 لبدء الاختبار: /begin\n"
    check_message += "📊 لعرض النتائج: /results"
    
    await update.message.reply_text(check_message, parse_mode='Markdown')

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر تصحيح للأدمن فقط"""
    user_id = update.effective_user.id
    
    # يمكنك تحديد ID أدمن هنا
    admin_ids = [user_id]  # أضف IDs الأدمن هنا
    
    if user_id not in admin_ids:
        await update.message.reply_text("⛔ ليس لديك صلاحية هذا الأمر")
        return
    
    debug_info = (
        f"🔧 **معلومات التصحيح**\n\n"
        f"• إصدار Python: {sys.version}\n"
        f"• عدد الأسئلة: {len(correct_answers)}\n"
        f"• عدد الجلسات النشطة: {len(user_sessions)}\n"
        f"• مجلد الصور: {'موجود ✅' if os.path.exists('Images') else 'غير موجود ❌'}\n"
        f"• ملف Excel: {'موجود ✅' if os.path.exists('Answers.xlsx') else 'غير موجود ❌'}\n"
        f"• التوكن: {'مضبوط ✅' if TOKEN else 'غير مضبوط ❌'}\n"
    )
    
    await update.message.reply_text(debug_info, parse_mode='Markdown')

def main():
    """الدالة الرئيسية"""
    logger.info("🚀 بدء تشغيل بوت الرياضيات...")
    
    # التحقق من التوكن
    if not TOKEN:
        logger.error("❌ TOKEN غير موجود! تأكد من إعداد TELEGRAM_BOT_TOKEN")
        logger.info("💡 التعليمات:")
        logger.info("1. اذهب إلى Render Dashboard")
        logger.info("2. اختر خدمتك")
        logger.info("3. اضغط على Environment")
        logger.info("4. أضف متغير: TELEGRAM_BOT_TOKEN = توكن_البوت_هنا")
        return
    
    logger.info(f"✅ التوكن موجود")
    
    # التحقق من مجلد الصور
    logger.info("🔍 التحقق من هيكل المجلدات...")
    
    if os.path.exists('Images'):
        logger.info("✅ مجلد Images موجود")
        if os.path.exists('Images/True or False'):
            tf_files = [f for f in os.listdir('Images/True or False') if f.lower().endswith(('.png', '.jpg'))]
            logger.info(f"📁 True or False: {len(tf_files)} صورة")
        else:
            logger.warning("⚠️ مجلد True or False غير موجود")
            
        if os.path.exists('Images/mcq'):
            mcq_files = [f for f in os.listdir('Images/mcq') if f.lower().endswith(('.png', '.jpg'))]
            logger.info(f"📁 mcq: {len(mcq_files)} صورة")
        else:
            logger.warning("⚠️ مجلد mcq غير موجود")
    else:
        logger.warning("⚠️ مجلد Images غير موجود!")
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("begin", begin_test))
    application.add_handler(CommandHandler("results", results_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("debug", debug_command))
    application.add_handler(CallbackQueryHandler(handle_answer))
    
    # التحقق إذا كان على Render
    is_render = os.getenv('RENDER', '').lower() in ['true', '1', 'yes']
    
    if is_render:
        # على Render - استخدام webhook
        render_service_name = os.getenv('RENDER_SERVICE_NAME', 'math-limits-bot2')
        webhook_url = f"https://{render_service_name}.onrender.com/{TOKEN}"
        
        logger.info(f"🌐 استخدام webhook على Render")
        logger.info(f"📡 Webhook URL: {webhook_url}")
        
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
