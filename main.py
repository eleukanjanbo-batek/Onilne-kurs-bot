import asyncio
import logging
import sqlite3
import os
import threading
from flask import Flask, render_template_string, request, redirect, session, url_for
from aiogram import Bot, Dispatcher, F
from aiogram.types import (Message, ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
                           ReplyKeyboardRemove)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

# .env yuklash
load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ID")) if os.getenv("ID") else None

# --- 1. BOT SOZLAMALARI ---
bot = Bot(token=TOKEN)
dp = Dispatcher()


def db_setup():
    conn = sqlite3.connect("taelim.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        ism TEXT,
        kurs TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_config (
        id INTEGER PRIMARY KEY,
        login TEXT,
        password TEXT
    )
    """)
    check = cursor.execute("SELECT COUNT(*) FROM admin_config").fetchone()
    if check[0] == 0:
        cursor.execute("INSERT INTO admin_config (id, login, password) VALUES (1, 'admin', '123')")
    conn.commit()
    conn.close()


class RoyxatdanOthis(StatesGroup):
    ism_kutish = State()
    kurs_tanlash = State()


kurslar_inline = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Python", callback_data="kurs_Python")],
        [InlineKeyboardButton(text="SMM", callback_data="kurs_SMM")],
        [InlineKeyboardButton(text="Dizayn", callback_data="kurs_Dizayn")]
    ]
)


# --- 2. BOT HANDLERLARI ---

@dp.message(CommandStart())
async def start(message: Message):
    db_setup()
    kb = [
        [KeyboardButton(text="📚 Kurslar"), KeyboardButton(text="📝 Kursga jaziliw")],
        [KeyboardButton(text="🎥 Sabaqlar"), KeyboardButton(text="👤 Profil")],
        [KeyboardButton(text="ℹ️ Admin haqqinda")]
    ]
    if message.from_user.id == ADMIN_ID:
        kb.append([KeyboardButton(text="📊 Admin Panel")])

    asosi_menyu = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(f"Assalawmaleykum {message.from_user.first_name}!\nOnlayn kurs botina xosh kelipsiz.",
                         reply_markup=asosi_menyu)


@dp.message(F.text == "📊 Admin Panel")
async def panel_info(message: Message):
    # 'Havola kutilmoqda...' degan yozuv o'rniga haqiqiy link bo'lishi shart
    # Renderga qo'yganingizdan keyin bu yerga Render bergan sayt manzilingizni yozasiz
    panel_url = "https://google.com"  # Vaqtincha xato bermasligi uchun shunday tursin

    panel_tugma = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Saytga kiriw", url=panel_url)]
    ])
    await message.answer(f"Admin paneli manzili kutilmekde...", reply_markup=panel_tugma)


@dp.message(F.text == "📚 Kurslar")
async def kurslar(message: Message):
    await message.answer("Bizdegi bar bolgan kurslar:\n\n1. 🐍 **Python**\n2. 📈 **SMM**\n3. 🎨 **Dizayn**")


@dp.message(F.text == "📝 Kursga jaziliw")
async def yozilish(message: Message, state: FSMContext):
    await message.answer("Ati-familiyanizdi kiritin:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(RoyxatdanOthis.ism_kutish)


@dp.message(RoyxatdanOthis.ism_kutish)
async def ism_qabul(message: Message, state: FSMContext):
    await state.update_data(ism=message.text)
    await message.answer(f"Jaqsi {message.text}, kursdi tanlan:", reply_markup=kurslar_inline)
    await state.set_state(RoyxatdanOthis.kurs_tanlash)


@dp.callback_query(RoyxatdanOthis.kurs_tanlash)
async def kurs_qabul(call: CallbackQuery, state: FSMContext):
    kurs_nomi = call.data.split("_")[1]
    data = await state.get_data()
    ism = data.get("ism")

    conn = sqlite3.connect("taelim.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, ism, kurs) VALUES (?, ?, ?)",
                   (call.from_user.id, ism, kurs_nomi))
    conn.commit()
    conn.close()

    await call.message.answer(f"Qutliqlaymiz {ism}, {kurs_nomi} kursina jazildiniz!")
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, f"Jana oqiwshi: {ism}\nKurs: {kurs_nomi}")
        except:
            pass
    await state.clear()


# --- 3. FLASK ADMIN PANEL ---

app = Flask(__name__)
app.secret_key = "janbolat_secret_key_2026"

HEAD_COMMON = """
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    * { font-family: 'Poppins', sans-serif; box-sizing: border-box; }
    body { background: #eef2f7; margin: 0; padding: 20px; }
    .glass-card { background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); max-width: 800px; margin: auto; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { padding: 12px; border-bottom: 1px solid #ddd; text-align: left; }
    .btn-del { color: red; text-decoration: none; }
</style>
"""


@app.route('/', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'): return redirect(url_for('dashboard'))
    if request.method == 'POST':
        conn = sqlite3.connect("taelim.db")
        conn.row_factory = sqlite3.Row
        admin = conn.execute("SELECT * FROM admin_config WHERE id=1").fetchone()
        conn.close()
        if request.form.get('login') == admin['login'] and request.form.get('password') == admin['password']:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
    return render_template_string(HEAD_COMMON + """
        <div class="glass-card" style="max-width:300px; margin-top:100px; text-align:center;">
            <h2>Admin Login</h2>
            <form method="POST">
                <input type="text" name="login" placeholder="Login" required style="width:100%; padding:10px; margin:5px 0;"><br>
                <input type="password" name="password" placeholder="Parol" required style="width:100%; padding:10px; margin:5px 0;"><br>
                <button type="submit" style="width:100%; padding:10px; background:#0088cc; color:white; border:none; border-radius:5px;">Kirish</button>
            </form>
        </div>
    """)


@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = sqlite3.connect("taelim.db")
    conn.row_factory = sqlite3.Row
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template_string(HEAD_COMMON + """
        <div class="glass-card">
            <h2><i class="fas fa-users"></i> O'quvchilar ro'yxati</h2>
            <table>
                <tr><th>ID</th><th>Ism</th><th>Kurs</th><th>Amal</th></tr>
                {% for user in users %}
                <tr>
                    <td>{{ user['user_id'] }}</td><td>{{ user['ism'] }}</td><td>{{ user['kurs'] }}</td>
                    <td><a href="/delete/{{ user['user_id'] }}" class="btn-del">O'chirish</a></td>
                </tr>
                {% endfor %}
            </table>
            <br><a href="/logout">Chiqish</a>
        </div>
    """, users=users)


@app.route('/delete/<int:user_id>')
def delete_user(user_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = sqlite3.connect("taelim.db")
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- 4. RUN ---

def run_flask():
    # Render PORT'ni o'zi beradi, agar bermasa 5000 ishlaydi
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)


async def run_bot():
    logging.basicConfig(level=logging.INFO)
    db_setup()
    await dp.start_polling(bot)


if __name__ == "__main__":
    # Flaskni alohida thread'da ishga tushiramiz
    threading.Thread(target=run_flask, daemon=True).start()
    # Botni asosiy thread'da ishga tushiramiz
    asyncio.run(run_bot())