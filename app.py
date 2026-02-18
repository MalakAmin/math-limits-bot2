import os
import sys
import logging
import asyncio
from datetime import datetime

# إعداد logging أولاً
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# استيراد المكتبات
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, 
        CommandHandler, 
        CallbackQueryHandler,
        ContextTypes,
        filters
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

# البيانات الثابتة من ملف Excel - تم تحديثها حسب الملف المرفق
CORRECT_ANSWERS_DATA = {
    1: {'type': 'tf', 'correct_answer': 't'},
    2: {'type': 'tf', 'correct_answer': 't'},
    3: {'type': 'tf', 'correct_answer': 't'},
    4: {'type': 'tf', 'correct_answer': 't'},
    5: {'type': 'tf', 'correct_answer': 't'},
    6: {'type': 'tf', 'correct_answer': 't'},
    7: {'type': 'tf', 'correct_answer': 'f'},
    8: {'type': 'tf', 'correct_answer': 't'},
    9: {'type': 'tf', 'correct_answer': 't'},
    10: {'type': 'tf', 'correct_answer': 't'},
    11: {'type': 'mcq', 'correct_answer': 'c'},
    12: {'type': 'mcq', 'correct_answer': 'b'},
    13: {'type': 'mcq', 'correct_answer': 'c'},
    14: {'type': 'mcq', 'correct_answer': 'c'},
    15: {'type': 'mcq', 'correct_answer': 'b'},
    16: {'type': 'mcq', 'correct_answer': 'b'},
    17: {'type': 'mcq', 'correct_answer': 'b'},
    18: {'type': 'mcq', 'correct_answer': 'b'},
    19: {'type': 'mcq', 'correct_answer': 'b'},
    20: {'type': 'mcq', 'correct_answer': 'b'},
}

def load_correct_answers():
    """تحميل الإجابات الصحيحة - باستخدام البيانات الثابتة"""
    logger.info("📖 جاري تحميل الإجابات الصحيحة...")
    
    correct_answers = {}
    
    for question_num, data in CORRECT_ANSWERS_DATA.items():
        correct_answers[question_num] = {
            'type': data['type'],
            'correct_answer': data['correct_answer'],
            'user_answer': None,
            'is_correct': False,
            'answered_at': None
        }
    
    logger.info(f"✅ تم تحميل {len(correct_answers)} إجابة صحيحة")
    
    # عرض إحصائيات
    tf_count = sum(1 for q in correct_answers.values() if q['type'] == 'tf')
    mcq_count = sum(1 for q in correct_answers.values() if q['type'] == 'mcq')
    logger.info(f"📈 الإحصائيات: صح/خطأ={tf_count}, MCQ={mcq_count}")
    
    return correct_answers

def get_image_path(question_num):
    """الحصول على مسار الصورة بناءً على رقم السؤال"""
    if 1 <= question_num <= 10:
        folder = "True or False"
    elif 11 <= question_num <= 20:
        folder = "mcq"
    else:
        logger.error(f"❌ رقم سؤال غير صحيح: {question_num}")
        return None
    
    # المجلد الأساسي
    base_path = os.path.join(IMAGES_BASE_DIR, folder)
    
    if not os.path.exists(base_path):
        logger.error(f"❌ المجلد غير موجود: {base_path}")
        # محاولة مسار بديل
        alt_base_path = os.path.join('images', folder)
        if os.path.exists(alt_base_path):
            base_path = alt_base_path
            logger.info(f"✅ وجدت المجلد البديل: {alt_base_path}")
        else:
            return None
    
    # قائمة الامتدادات المحتملة
    extensions = ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG']
    
    # المحاولة 1: البحث بالرقم + الامتداد
    for ext in extensions:
        path = os.path.join(base_path, f"{question_num}{ext}")
        if os.path.exists(path):
            logger.debug(f"📸 وجدت صورة: {path}")
            return path
    
    # المحاولة 2: البحث بأي ملف يبدأ بالرقم
    try:
        files = os.listdir(base_path)
        for file in files:
            # تحقق إذا كان الملف يبدأ برقم السؤال
            if file.startswith(str(question_num)):
                path = os.path.join(base_path, file)
                logger.debug(f"📸 وجدت صورة بالاسم: {path}")
                return path
            
            # تحقق إذا كان الملف يحتوي على رقم السؤال في الاسم
            if f"_{question_num}." in file or f" {question_num}." in file:
                path = os.path.join(base_path, file)
                logger.debug(f"📸 وجدت صورة تحتوي على الرقم: {path}")
                return path
    except Exception as e:
        logger.error(f"❌ خطأ في قراءة المجلد: {e}")
    
    logger.warning(f"⚠️ لم أجد صورة للسؤال {question_num} في {base_path}")
    
    return None

# قاموس لحفظ إجابات المستخدمين
user_sessions = {}
correct_answers = load_correct_answers()

# تعريف الدوال
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء الاختبار"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    logger.info(f"👤 المستخدم {username} ({user_id}) بدأ الجلسة")
    
    welcome_text = (
        "📚 **مرحباً بك في بوت اختبار الرياضيات!**\n\n"
        "🎯 **معلومات عن الاختبار:**\n"
        "• الأسئلة 1-10: صح/خطأ ✅/❌\n"
        "• الأسئلة 11-20: اختيار من متعدد 🔠\n"
        "• عدد الأسئلة: 20 سؤالاً\n\n"
        "📝 **كيفية الاستخدام:**\n"
        "1. اضغط /begin لبدء الاختبار\n"
        "2. اختر الإجابة المناسبة لكل سؤال\n"
        "3. في النهاية سأعرض نتيجتك\n\n"
        "⚡ **لبدء الاختبار الآن:**\n"
        "اضغط /begin"
    )
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def begin_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إرسال الأسئلة"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    # التحقق من وجود اختبار سابق
    if user_id in user_sessions and not user_sessions[user_id].get('completed', True):
        await update.message.reply_text(
            "⚠️ لديك اختبار قيد التقدم!\n\n"
            "📊 لعرض النتائج الحالية: /results\n"
            "🔄 لبدء اختبار جديد: /start ثم /begin"
        )
        return
    
    logger.info(f"🚀 المستخدم {username} ({user_id}) بدأ الاختبار")
    
    # تهيئة جلسة المستخدم
    user_sessions[user_id] = {
        'current_question': 1,
        'total_questions': len(correct_answers),
        'score': 0,
        'answers': {},
        'completed': False,
        'username': username,
        'start_time': datetime.now(),
        'end_time': None
    }
    
    # نسخ الإجابات الصحيحة مع إضافة حقول إضافية
    for q_num, data in correct_answers.items():
        user_sessions[user_id]['answers'][q_num] = {
            'type': data['type'],
            'correct_answer': data['correct_answer'],
            'user_answer': None,
            'is_correct': False,
            'answered_at': None,
            'response_time': None
        }
    
    # إرسال رسالة بدء الاختبار
    await update.message.reply_text(
        f"✅ **تم تهيئة الاختبار بنجاح!**\n\n"
        f"📊 عدد الأسئلة: {len(correct_answers)}\n"
        f"👤 الطالب: {username}\n"
        f"⏰ وقت البدء: {datetime.now().strftime('%H:%M:%S')}\n\n"
        "🎯 **جاري إرسال أول سؤال...**",
        parse_mode='Markdown'
    )
    
    # إرسال أول سؤال
    await send_question(update, context, user_id)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """إرسال سؤال للمستخدم"""
    session = user_sessions[user_id]
    question_num = session['current_question']
    
    # التحقق من انتهاء الأسئلة
    if question_num > session['total_questions']:
        logger.info(f"🏁 المستخدم {user_id} أنهى جميع الأسئلة")
        session['end_time'] = datetime.now()
        await show_results(update, context, user_id)
        return
    
    logger.info(f"📨 إرسال السؤال {question_num} للمستخدم {user_id}")
    
    # الحصول على مسار الصورة
    image_path = get_image_path(question_num)
    
    if not image_path:
        logger.error(f"❌ لم أجد صورة للسؤال {question_num}")
        
        # إرسال رسالة خطأ
        await context.bot.send_message(
            chat_id=update.effective_chat.id if hasattr(update, 'message') else update.callback_query.message.chat.id,
            text=f"⚠️ **عذراً، لم أتمكن من العثور على صورة السؤال {question_num}**\n\n"
                 f"جاري الانتقال للسؤال التالي...",
            parse_mode='Markdown'
        )
        
        # الانتقال للسؤال التالي
        session['current_question'] += 1
        await asyncio.sleep(1.5)
        await send_question(update, context, user_id)
        return
    
    # تحديد نوع السؤال وبناء الأزرار
    question_data = session['answers'][question_num]
    
    if question_data['type'] == 'tf':
        # أزرار صح/خطأ
        keyboard = [
            [
                InlineKeyboardButton("✅ صح (True)", callback_data=f"ans_{question_num}_t"),
                InlineKeyboardButton("❌ خطأ (False)", callback_data=f"ans_{question_num}_f")
            ]
        ]
        question_type_text = "📝 **سؤال صح/خطأ**"
    else:
        # أزرار MCQ - أحرف إنجليزية A, B, C, D
        keyboard = [
            [
                InlineKeyboardButton("A", callback_data=f"ans_{question_num}_a"),
                InlineKeyboardButton("B", callback_data=f"ans_{question_num}_b"),
                InlineKeyboardButton("C", callback_data=f"ans_{question_num}_c"),
                InlineKeyboardButton("D", callback_data=f"ans_{question_num}_d")
            ]
        ]
        question_type_text = "🔠 **سؤال اختيار من متعدد**"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # إرسال الصورة مع الأزرار
        with open(image_path, 'rb') as photo:
            message = await context.bot.send_photo(
                chat_id=update.effective_chat.id if hasattr(update, 'message') else update.callback_query.message.chat.id,
                photo=photo,
                caption=f"**السؤال رقم: {question_num}**\n{question_type_text}\n\nاختر الإجابة الصحيحة:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            # حفظ معرف الرسالة (اختياري)
            session['last_message_id'] = message.message_id
            
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال الصورة: {e}")
        
        # إرسال رسالة نصية بديلة
        await context.bot.send_message(
            chat_id=update.effective_chat.id if hasattr(update, 'message') else update.callback_query.message.chat.id,
            text=f"**السؤال رقم: {question_num}**\n{question_type_text}\n\nاختر الإجابة الصحيحة:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إجابة المستخدم"""
    logger.info("🎯 تم استدعاء handle_answer")
    
    if not update.callback_query:
        logger.error("❌ لا يوجد callback_query!")
        return
    
    query = update.callback_query
    user_id = query.from_user.id
    
    # الرد على callback query - هذا مهم جداً!
    try:
        await query.answer()
        logger.info(f"✅ تم الرد على callback_query للمستخدم {user_id}")
    except Exception as e:
        logger.error(f"❌ خطأ في query.answer(): {e}")
    
    logger.info(f"📱 بيانات الزر: {query.data}")
    
    # التحقق من وجود جلسة المستخدم
    if user_id not in user_sessions:
        await query.edit_message_caption(
            caption="⚠️ **انتهت جلستك**\n\nاضغط /start للبدء من جديد",
            reply_markup=None
        )
        return
    
    session = user_sessions[user_id]
    
    # استخراج البيانات من callback_data
    try:
        # التنسيق المتوقع: ans_رقم_إجابة
        parts = query.data.split('_')
        if len(parts) != 3:
            logger.error(f"❌ تنسيق غير صحيح: {query.data}")
            return
        
        question_num = int(parts[1])
        user_answer = parts[2].lower()
        
        logger.info(f"🔍 معالجة: السؤال {question_num}، الإجابة {user_answer}")
        
        # التحقق من صحة السؤال
        if question_num not in session['answers']:
            logger.error(f"❌ السؤال {question_num} غير موجود")
            return
        
        # تسجيل وقت الإجابة
        answer_time = datetime.now()
        
        # حفظ إجابة المستخدم
        session['answers'][question_num]['user_answer'] = user_answer
        session['answers'][question_num]['answered_at'] = answer_time
        
        # حساب زمن الاستجابة (إذا كان هناك وقت بدء للسؤال)
        if 'question_start_time' in session:
            response_time = (answer_time - session['question_start_time']).total_seconds()
            session['answers'][question_num]['response_time'] = response_time
        
        # التحقق إذا كانت الإجابة صحيحة
        correct_answer = session['answers'][question_num]['correct_answer']
        is_correct = user_answer == correct_answer
        session['answers'][question_num]['is_correct'] = is_correct
        
        if is_correct:
            session['score'] += 1
            logger.info(f"✅ إجابة صحيحة! السؤال: {question_num}")
        else:
            logger.info(f"❌ إجابة خاطئة! السؤال: {question_num}")
        
        # تحديث الرسالة لإظهار الاختيار
        emoji = "✅" if is_correct else "❌"
        
        # تحويل الإجابة إلى نص مناسب للعرض
        if user_answer == 't':
            answer_text = "صح"
        elif user_answer == 'f':
            answer_text = "خطأ"
        else:
            answer_text = user_answer.upper()
        
        await query.edit_message_caption(
            caption=f"**السؤال رقم: {question_num}**\n\n{emoji} **اخترت:** {answer_text}\n\n⏳ جاري تحميل السؤال التالي...",
            reply_markup=None,
            parse_mode='Markdown'
        )
        
        # الانتقال للسؤال التالي
        session['current_question'] += 1
        
        # انتظار قصير ثم إرسال السؤال التالي
        await asyncio.sleep(1.5)
        
        # تسجيل وقت بدء السؤال الجديد
        session['question_start_time'] = datetime.now()
        
        # إرسال السؤال التالي
        await send_question(update, context, user_id)
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الإجابة: {e}", exc_info=True)
        
        # إرسال رسالة خطأ للمستخدم
        try:
            await query.edit_message_caption(
                caption="⚠️ **حدث خطأ في معالجة إجابتك**\n\nالرجاء المحاولة مرة أخرى أو اضغط /start",
                reply_markup=None
            )
        except:
            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text="⚠️ حدث خطأ. الرجاء المحاولة مرة أخرى."
            )

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    """عرض النتائج"""
    if user_id is None:
        if hasattr(update, 'message'):
            user_id = update.effective_user.id
        elif hasattr(update, 'callback_query'):
            user_id = update.callback_query.from_user.id
        else:
            return
    
    if user_id not in user_sessions:
        message_text = "⚠️ **لا توجد جلسة نشطة**\n\nاضغط /start للبدء"
        
        if hasattr(update, 'message'):
            await update.message.reply_text(message_text, parse_mode='Markdown')
        else:
            await context.bot.send_message(
                chat_id=update.callback_query.message.chat.id,
                text=message_text,
                parse_mode='Markdown'
            )
        return
    
    session = user_sessions[user_id]
    
    # حساب النتيجة
    total = session['total_questions']
    score = session['score']
    percentage = (score / total) * 100 if total > 0 else 0
    
    # حساب الوقت المستغرق
    if session.get('start_time') and session.get('end_time'):
        time_taken = session['end_time'] - session['start_time']
        minutes = int(time_taken.total_seconds() // 60)
        seconds = int(time_taken.total_seconds() % 60)
        time_str = f"{minutes} دقيقة و{seconds} ثانية"
    else:
        time_str = "غير محسوب"
    
    # تحديد المستوى
    if percentage >= 90:
        level = "ممتاز 🏆"
    elif percentage >= 75:
        level = "جيد جداً ⭐"
    elif percentage >= 50:
        level = "مقبول ✓"
    else:
        level = "ضعف 📉"
    
    # إنشاء تفاصيل الإجابات
    details = "📊 **تفاصيل الإجابات:**\n\n"
    
    # تجميع الإجابات الصحيحة والخاطئة
    correct_answers_list = []
    wrong_answers_list = []
    
    for q_num in sorted(session['answers'].keys()):
        ans = session['answers'][q_num]
        user_ans = ans['user_answer'] or "لم يُجب"
        correct_ans = ans['correct_answer']
        is_correct = ans['is_correct']
        
        # تحويل الإجابات لشكل مقروء
        if user_ans == 't':
            user_display = "صح"
        elif user_ans == 'f':
            user_display = "خطأ"
        else:
            user_display = user_ans.upper()
        
        if correct_ans == 't':
            correct_display = "صح"
        elif correct_ans == 'f':
            correct_display = "خطأ"
        else:
            correct_display = correct_ans.upper()
        
        if is_correct:
            correct_answers_list.append(f"✅ سؤال {q_num}: إجابتك ({user_display})")
        else:
            wrong_answers_list.append(f"❌ سؤال {q_num}: إجابتك ({user_display}) | الصحيحة ({correct_display})")
    
    # إضافة الإجابات الصحيحة أولاً
    for item in correct_answers_list[:10]:
        details += item + "\n"
    
    if len(correct_answers_list) > 10:
        details += f"✅ +{len(correct_answers_list) - 10} إجابة صحيحة أخرى\n"
    
    # إضافة الإجابات الخاطئة
    for item in wrong_answers_list[:10]:
        details += item + "\n"
    
    if len(wrong_answers_list) > 10:
        details += f"❌ +{len(wrong_answers_list) - 10} إجابة خاطئة أخرى\n"
    
    # رسالة النتيجة النهائية
    result_message = (
        f"🎉 **تم الانتهاء من الاختبار!**\n\n"
        f"📈 **النتيجة النهائية:**\n"
        f"• 👤 الطالب: {session['username']}\n"
        f"• 📊 عدد الأسئلة: {total}\n"
        f"• ✅ الإجابات الصحيحة: {score}\n"
        f"• ❌ الإجابات الخاطئة: {total - score}\n"
        f"• 📈 النسبة المئوية: {percentage:.1f}%\n"
        f"• 🏆 المستوى: {level}\n"
        f"• ⏰ الوقت المستغرق: {time_str}\n\n"
        f"{details}\n"
        f"🔄 **لإعادة الاختبار:**\n"
        f"اضغط /start ثم /begin"
    )
    
    # إرسال النتيجة
    await context.bot.send_message(
        chat_id=update.effective_chat.id if hasattr(update, 'message') else update.callback_query.message.chat.id,
        text=result_message,
        parse_mode='Markdown'
    )
    
    # تحديث حالة الجلسة
    session['completed'] = True
    
    logger.info(f"📊 النتيجة: {user_id} - {score}/{total} ({percentage:.1f}%)")

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
        "/help - عرض هذه التعليمات\n\n"
        "🎯 **أنواع الأسئلة:**\n"
        "• الأسئلة 1-10: صح/خطأ (✅/❌)\n"
        "• الأسئلة 11-20: اختيار من متعدد (A/B/C/D)\n\n"
        "⚠️ **ملاحظات:**\n"
        "• يمكنك إعادة الاختبار متى شئت\n"
        "• النتائج تحفظ خلال الجلسة فقط\n"
        "• اضغط على الزر المناسب للإجابة"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض حالة البوت"""
    user_id = update.effective_user.id
    
    status_text = (
        f"🔍 **حالة البوت**\n\n"
        f"• ✅ البوت يعمل بنجاح\n"
        f"• 📊 عدد الأسئلة: {len(correct_answers)}\n"
        f"• 👥 المستخدمون النشطون: {len(user_sessions)}\n"
        f"• 🕐 وقت التشغيل: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    
    if user_id in user_sessions:
        session = user_sessions[user_id]
        status_text += f"📋 **حالتك الحالية:**\n"
        status_text += f"• 👤 الاسم: {session['username']}\n"
        status_text += f"• 📝 السؤال الحالي: {session['current_question']}/{session['total_questions']}\n"
        status_text += f"• ✅ النقاط: {session['score']}\n"
        status_text += f"• 🏁 الحالة: {'مكتمل' if session['completed'] else 'قيد التقدم'}\n\n"
    
    status_text += "🔄 لبدء الاختبار: /begin\n"
    status_text += "📊 لعرض النتائج: /results"
    
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def test_button_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختبار الأزرار"""
    keyboard = [
        [
            InlineKeyboardButton("زر اختبار 1 ✅", callback_data="test_1"),
            InlineKeyboardButton("زر اختبار 2 ❌", callback_data="test_2")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔘 **اختبار الأزرار**\n\nاضغط على أي زر للتحقق من عمل الأزرار:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_test_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أزرار الاختبار"""
    query = update.callback_query
    await query.answer(f"✅ تم الضغط على {query.data}")
    
    await query.edit_message_text(
        text=f"🎉 **الأزرار تعمل بنجاح!**\n\nالزر المضغوط: `{query.data}`\n\n✅ يمكنك الآن استخدام /begin لبدء الاختبار",
        parse_mode='Markdown'
    )

def main():
    """الدالة الرئيسية لتشغيل البوت"""
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
    
    logger.info(f"✅ التوكن موجود وتم التحقق منه")
    
    # التحقق من وجود مجلد الصور
    logger.info("🔍 التحقق من هيكل المجلدات...")
    
    if os.path.exists(IMAGES_BASE_DIR):
        logger.info(f"✅ مجلد {IMAGES_BASE_DIR} موجود")
        
        # التحقق من المجلدات الفرعية
        for folder in ["True or False", "mcq"]:
            folder_path = os.path.join(IMAGES_BASE_DIR, folder)
            if os.path.exists(folder_path):
                files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                logger.info(f"📁 {folder}: {len(files)} صورة")
            else:
                logger.warning(f"⚠️ مجلد {folder} غير موجود")
    else:
        logger.warning(f"⚠️ مجلد {IMAGES_BASE_DIR} غير موجود!")
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة handlers للأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("begin", begin_test))
    application.add_handler(CommandHandler("results", results_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("test", test_button_command))
    
    # إضافة handlers للأزرار
    application.add_handler(CallbackQueryHandler(handle_answer, pattern="^ans_"))
    application.add_handler(CallbackQueryHandler(handle_test_button, pattern="^test_"))
    
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
