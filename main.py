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

# --- 1. BOT VA BAZA SOZLAMALARI ---
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
        id INTEGER PRIMARY KEY, login TEXT, password TEXT
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


def get_main_menu(user_id):
    kb = [
        [KeyboardButton(text="📚 Kurslar"), KeyboardButton(text="📝 Kursga jaziliw")],
        [KeyboardButton(text="🎥 Sabaqlar"), KeyboardButton(text="👤 Profil")],
        [KeyboardButton(text="ℹ️ Admin haqqinda")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="📊 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# --- 2. BOT HANDLERLARI ---

@dp.message(CommandStart())
async def start(message: Message):
    db_setup()
    await message.answer(f"Assalawmaleykum {message.from_user.first_name}!\nOnlayn kurs botina xosh kelipsiz.",
                         reply_markup=get_main_menu(message.from_user.id))


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
    kurslar_inline = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Python", callback_data="kurs_Python")],
        [InlineKeyboardButton(text="SMM", callback_data="kurs_SMM")],
        [InlineKeyboardButton(text="Dizayn", callback_data="kurs_Dizayn")]
    ])
    await message.answer(f"Jaqsi {message.text}, kursdi tanlan:", reply_markup=kurslar_inline)
    await state.set_state(RoyxatdanOthis.kurs_tanlash)


@dp.callback_query(RoyxatdanOthis.kurs_tanlash)
async def kurs_qabul(call: CallbackQuery, state: FSMContext):
    kurs_nomi = call.data.split("_")[1]
    user_data = await state.get_data()
    ism = user_data.get("ism")

    conn = sqlite3.connect("taelim.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, ism, kurs) VALUES (?, ?, ?)",
                   (call.from_user.id, ism, kurs_nomi))
    conn.commit()
    conn.close()

    await call.message.delete()
    await call.message.answer(f"Qutliqlaymiz {ism}, {kurs_nomi} kursina jazildiniz!",
                              reply_markup=get_main_menu(call.from_user.id))

    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, f"Jana oqiwshi: {ism}\nKurs: {kurs_nomi}")
        except:
            pass
    await state.clear()


@dp.message(F.text == "👤 Profil")
async def profil(message: Message):
    conn = sqlite3.connect("taelim.db")
    user = conn.execute("SELECT ism, kurs FROM users WHERE user_id = ?", (message.from_user.id,)).fetchone()
    conn.close()
    if user:
        await message.answer(f"👤 Profilingiz:\n\n📝 Ism: {user[0]}\n🎓 Kurs: {user[1]}")
    else:
        await message.answer("Siz ro'yxatdan o'tmagansiz.")


@dp.message(F.text == "🎥 Sabaqlar")
async def sabaqlar(message: Message):
    conn = sqlite3.connect("taelim.db")
    user = conn.execute("SELECT kurs FROM users WHERE user_id = ?", (message.from_user.id,)).fetchone()
    conn.close()
    if user:
        await message.answer(f"Sizdin {user[0]} kursi boyinsha sabaqlariniz juklenmekde...")
    else:
        await message.answer("Sabaqlardi koriw ushin aldin kursga jazilin!")


@dp.message(F.text == "ℹ️ Admin haqqinda")
async def admin_haqqinda(message: Message):
    await message.answer("Admin: Eleukanov Janbolat\nTelegram: @Batekkkkkk")


@dp.message(F.text == "📊 Admin Panel")
async def panel_info(message: Message):
    panel_url = os.getenv("PUBLIC_URL", "https://onilne-kurs-bot.onrender.com/")
    panel_tugma = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Saytga kiriw", url=panel_url)]])
    await message.answer(f"Admin paneli manzili:", reply_markup=panel_tugma)


# --- 3. FLASK ADMIN PANEL ---
# --- 3. FLASK ADMIN PANEL (Web qismi) ---

app = Flask(__name__)
app.secret_key = "janbolat_secret_key"  # O'zgartirishingiz mumkin

# Universal CSS va HEAD qismi
HEAD_COMMON = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    * { font-family: 'Poppins', sans-serif; box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #eef2f7; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
    .glass-card { 
        background: white; 
        padding: 40px; 
        border-radius: 20px; 
        box-shadow: 0 8px 32px rgba(0,0,0,0.1); 
        width: 380px; 
        text-align: center; 
        transition: transform 0.3s ease;
    }
    .glass-card:hover { transform: translateY(-5px); }
    h2 { color: #333; margin-bottom: 30px; font-weight: 600; }
    input { 
        width: 100%; 
        padding: 12px; 
        margin-bottom: 20px; 
        border: 1px solid #ddd; 
        border-radius: 10px; 
        outline: none; 
        font-size: 15px;
    }
    input:focus { border-color: #0088cc; }
    button { 
        width: 100%; 
        padding: 12px; 
        background: #0088cc; 
        color: white; 
        border: none; 
        border-radius: 10px; 
        font-weight: 600; 
        cursor: pointer; 
        transition: 0.3s;
    }
    button:hover { background: #006fa5; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { padding: 15px; border-bottom: 1px solid #ddd; text-align: left; }
    .btn-del { color: red; text-decoration: none; cursor: pointer; }
</style>
"""


@app.route('/', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'): return redirect(url_for('dashboard'))
    error = False
    if request.method == 'POST':
        if request.form.get('login') == 'admin' and request.form.get('password') == '123':
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        error = True

    return render_template_string(HEAD_COMMON + """
        <div class="glass-card">
            <h2><i class="fas fa-user-lock"></i> Admin Panel</h2>
            {% if error %}<p style="color: red; margin-bottom: 15px;">Login yamasa parol qate!</p>{% endif %}
            <form method="POST">
                <input type="text" name="login" placeholder="Login" required>
                <input type="password" name="password" placeholder="Parol" required>
                <button type="submit">Kiriw</button>
            </form>
        </div>
    """, error=error)


@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = sqlite3.connect("taelim.db")
    conn.row_factory = sqlite3.Row
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()

    return render_template_string(HEAD_COMMON + """
        <div class="glass-card" style="width: 800px; max-width: 90%; margin: 40px auto; display: block;">
            <h2><i class="fas fa-users"></i> Oqiwshilar dizimi</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Ati</th>
                    <th>Kurs</th>
                    <th>Amel</th>
                </tr>
                {% for user in users %}
                <tr>
                    <td>{{ user['user_id'] }}</td>
                    <td>{{ user['ism'] }}</td>
                    <td>{{ user['kurs'] }}</td>
                    <td><a href="/delete/{{ user['user_id'] }}" class="btn-del"><i class="fas fa-trash"></i> O'chirish</a></td>
                </tr>
                {% endfor %}
            </table>
            <br><a href="/logout" style="text-decoration: none; color: #555;">Shigiw</a>
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)


async def run_bot():
    logging.basicConfig(level=logging.INFO)
    db_setup()
    await dp.start_polling(bot)


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(run_bot())