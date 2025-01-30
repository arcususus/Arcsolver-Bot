import telebot
from telebot import types
import requests
from bs4 import BeautifulSoup
import re
import time
from PIL import Image, ImageFilter, ImageEnhance
from io import BytesIO
import sqlite3
import json
import pytesseract
import markdown
from test3DATA import admin_id, api_bot, project_id, yagpt_api
from datetime import datetime, timedelta
import asyncio
import os
from threading import Thread


pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
DATA_FILE = "daily_update.json"

bot = telebot.TeleBot(api_bot)
(user_states, user_inputs, user_prop, user_copy, user_messages, echo_enabled, echo_enabled2, img_text, mess_id,
 message_mem) = ({} for _ in range(10))
# Хранение состояний пользователей, ввод пользователя, предмет отдельного пользователя, удаление...

text_mark1 = ('<b><i>Привет, этот бот находит решения школьных предметов.\nДля сложных задач добавлена нейросеть YaGPT.'
              '</i></b>')
text_mark2 = '<b><i>Выбери предмет из списка:</i></b>'

text_mark3 = '<b><i>Используется старый запрос:\nВернитесь на /start.</i></b>'

text_mark4 = ('*🪪Профиль🪪*\n\n*Ваш ID:* `{0}`\n\n*Никнейм:* `{1}`\n*Юзернейм:* `{2}`\n*Класс:* `{Класс}`\n\n'
              '*GPT-запросы:* `{GPT-лимит}`\n*За всё время:* `{GPT-запросы}`\n\n*Статус:* `{Статус}`\n'
              '*Дата создания:* `{Дата}`')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': '-US,en;q=0.5',
}
FIRST_NUMBER, SECOND_NUMBER = range(2)  # Создаем состояния


class Database:
    def __init__(self, db_name='users.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        """Создает таблицу пользователей, если она еще не создана."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                info TEXT DEFAULT ''
            )
        ''')
        self.conn.commit()

    def add_user(self, user_id, info=''):
        """Добавляет нового пользователя с текстом (по умолчанию пусто)."""
        try:
            self.cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
            result = self.cursor.fetchone()
            if result is None:
                first_name = info.from_user.first_name
                last_name = info.from_user.last_name
                username = info.from_user.username
                today = datetime.now()
                data = load_data()

                info = json.dumps({"Ник": f"{f'{last_name} ' if last_name else ''}{first_name}",
                                   "Юзернейм": f"@{username}", "GPT-запросы": 0, "GPT-лимит": data["value"], "Класс": 9,
                                   "Статус": "активный", "Дата": today.strftime('%d.%m.%Y')})

                self.cursor.execute('INSERT INTO users (id, info) VALUES (?, ?)', (user_id, info))
                self.conn.commit()
            else:
                print(f"Пользователь с id {user_id} уже существует.")
        except sqlite3.Error as e:
            print(f"Ошибка при добавлении пользователя: {e}")

    def update_user_info(self, user_id, info):
        """Обновляет текстовую информацию о пользователе."""
        try:
            self.cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
            result = self.cursor.fetchone()
            if result:
                self.cursor.execute('UPDATE users SET info = ? WHERE id = ?', (info, user_id))
                self.conn.commit()
            else:
                print(f"Пользователь с id {user_id} не найден.")
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении информации о пользователе: {e}")

    def get_user_info(self, user_id):
        """Возвращает информацию о пользователе."""
        try:
            self.cursor.execute('SELECT id, info FROM users WHERE id = ?', (user_id,))
            result = self.cursor.fetchone()
            if result:
                return {"id": result[0], "info": result[1]}
            else:
                print(f"Пользователь с id {user_id} не найден.")
                return None
        except sqlite3.Error as e:
            print(f"Ошибка при получении информации о пользователе: {e}")
            return None

    def get_user_count(self):
        """Возвращает количество уникальных пользователей."""
        try:
            self.cursor.execute('SELECT COUNT(*) FROM users')
            count = self.cursor.fetchone()[0]
            return count
        except sqlite3.Error as e:
            print(f"Ошибка при подсчете пользователей: {e}")
            return 0

    def get_all_ids(self):
        """Возвращает список всех ID из таблицы users."""
        try:
            self.cursor.execute("SELECT id FROM users")
            ids = [row[0] for row in self.cursor.fetchall()]
            return ids
        except sqlite3.Error as e:
            print(f"Ошибка при получении ID: {e}")
            return []

    def close(self):
        """Закрывает соединение с базой данных."""
        self.conn.close()
db = Database()


def escape_markdown(text):
    # Шаблон для поиска блоков кода ```code```
    code_pattern = r"```(.*?)```"

    # Сохраняем блоки кода в список и заменяем их в тексте временными плейсхолдерами
    code_blocks = re.findall(code_pattern, text, re.DOTALL)
    for i, block in enumerate(code_blocks):
        text = text.replace(f"```{block}```", f"{{CODEBLOCK{i}}}")

    pattern = [
        (r"\*\*(.*?)\*\*", r"\1"),  # Убираем двойные звездочки
        (r"\$(.*?)\$", r"\1"),  # Убираем символы доллара
        (r"([_*\~])", r"\\\1")  # Экранируем специальные символы
    ]

    for pat, repl in pattern:
        text = re.sub(pat, repl, text)

    # Восстанавливаем блоки кода обратно в текст
    for i, block in enumerate(code_blocks):
        text = str(text.replace(f"{{CODEBLOCK{i}}}", f"```{block}```"))

    return text


def preprocess_image(image):
    if not image.mode == "RGB":
        image = image.convert('RGB')
    image = image.convert('L')
    image = image.resize((image.width * 2, image.height * 2))  # Увеличение разрешения
    image = image.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(3.0)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    return image  # Максимальное улучшение контраста


def send_request_to_chatgpt(prompt: str, user=int):
    try:
        prompt_text = {
            "modelUri": f"gpt://{project_id}/yandexgpt/latest",
            "completionOptions": {
                "stream": False,
                "temperature": 0,
                "maxTokens": "8190"
            },
            "messages": [
                {
                    "role": "system",
                    "text": "Ты гений, способный решить задачу любой сложности, отвечать на вопросы и писать тексты. "
                            "Нужно проанализировать основной текст и ответить на вопросы, не используя ссылки на сайты."
                            " Если в запросе нет задания, объясняй текст."
                },
                {
                    "role": "user",
                    "text": f"{prompt}"
                }
            ]
        }

        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {yagpt_api}"
        }

        response = requests.post(url, headers=headers, json=prompt_text)
        if response.status_code == 200:

            result = response.json()
            text = str(result['result']['alternatives'][0]['message']['text'])
            esc_markdown = escape_markdown(text)

            info = db.get_user_info(user_id=user)
            info = json.loads(info['info'])
            info["GPT-запросы"] += 1
            info["GPT-лимит"] -= 1
            db.update_user_info(user_id=user, info=json.dumps(info))

            return esc_markdown
        else:
            return 'Произошла ошибка.'

    except requests.exceptions.RequestException as e:
        print(e)
        return 'Произошла ошибка.'


def delete_msg(chat_id, message_id, delay):
    time.sleep(delay)
    try:
        bot.delete_message(chat_id, message_id=message_id)
    except telebot.apihelper.ApiTelegramException:
        pass


def transliterate(text):  # Словарь для замены русских букв на английские
    text_lower = text.lower()
    translit_dict = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
        'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
        'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'x', 'ц': 'c',
        'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }

    transliterated_text = ''.join([translit_dict.get(char, char) for char in text_lower])
    return transliterated_text


def gdz_check(page, feaut, chap):
    url = None
    if feaut == 'ge':
        url = f'https://reshak.ru/otvet/otvet11.php?otvet1={page}'

    elif feaut == 'al':
        url = f'https://reshak.ru/otvet/otvet24.php?otvet1={page}'

    elif feaut == 'phybook':
        url = 'https://reshak.ru/reshebniki/fizika/9/perishkin/index.html'

    elif feaut == 'phy':
        url = f'https://reshak.ru/otvet/otvet10.php?otvet1={page}&var=1var'

    elif feaut == 'rus':
        url = f'https://reshak.ru/otvet/reshebniki.php?otvet={page}&predmet=barh_new9'

    elif feaut == 'info_copybook':
        url = f'https://reshak.ru/otvet/otvet19.php?otvet1={page}'

    elif feaut == 'info' or feaut == 'eng':
        chapter = re.sub(r'\D+', '', chap)
        letter_match = None
        try:
            letter_match = transliterate(chap)
            chap1, chap2 = chapter[0], chapter[1]
            if feaut == 'info':
                url = f'https://reshak.ru/otvet/reshebniki.php?otvet={chap1}-{chap2}/{page}&predmet=bosova9'
        except IndexError:
            if feaut == 'info':
                return None

        if feaut == 'eng':
            try:
                if letter_match:
                    letter_match = re.search(r'[a-zA-Z]', letter_match)
                    first_letter = letter_match.group() if letter_match else None
                    chap1, chap2 = chapter[0], first_letter
                    url = (f'https://reshak.ru/otvet/otvet_txt.php?otvet1=/'
                           f'spotlight9/images/module{chap1}/{chap2}/{page}')
            except IndexError:
                return None
    else:
        return None


    def resp(url):
        for u in range(2):
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                if u + 1 == 2:
                    return None
            else:
                return BeautifulSoup(response.text, 'html.parser')


    soup = resp(url)
    if soup is None:
        return None
    if feaut == 'phybook':  # это парсер на нужный учебник
        try:
            page_num = 0
            razdel_elements = soup.find_all('div', class_='razdel')
            len_elem = len(razdel_elements)
            pat = re.compile(fr"Упражнение (\d+)\({page}\)", re.MULTILINE)
            for element in razdel_elements:
                text = element.get_text()
                if f"({page})" in text:
                    match = pat.search(text)
                    if match:
                        url = f'https://reshak.ru/otvet/reshebniki.php?otvet=new/Upr/{match.group(1)}&predmet=per9'
                        soup = resp(url)
                        if soup is None:
                            return None
                        else:
                            break
                else:
                    page_num += 1
                    print(page_num, len_elem)
                    if page_num == len_elem:
                        url = f'https://reshak.ru/otvet/reshebniki.php?otvet=new/Upr/{page}&predmet=per9'
                        soup = resp(url)
                        if soup is None:
                            return None
        except AttributeError as e:
            print(e)

    if feaut == 'eng':
        text_container = soup.find('div', class_="mainInfo")
        if text_container:
            texts = [element.get_text() for element in text_container.find_all(['div', 'h1', 'h2', 'h3', 'b'])]
            if texts:
                lines = str(texts[0]).strip()
                if '« Назад' not in lines:
                    unique_lines = []
                    seen = set()
                    for line in texts:
                        if line not in seen or re.match(r'^[1-9a-zA-Z\s]{1,2}$', line):
                            unique_lines.append(line)
                            seen.add(line)
                    clean_text = '\n'.join(unique_lines).replace('Решение #', '\n<b><i>#Решение:\t</i></b>').strip()
                    return clean_text
    else:
        article = soup.find('article', class_='lcol')
        if article:
            src_values = []
            # Ищем все <div>, у которых класс начинается с "pic_otvet"
            divs = article.find_all('div', class_=re.compile(r'^pic_otvet'))
            for div in divs:
                img_tag = div.find('img')
                if img_tag:
                    # Используем регулярное выражение для поиска атрибута "src" или подобных
                    matching_attrs = [value for key, value in img_tag.attrs.items() if re.match(r'^.*?src$', key)][0]
                    if matching_attrs:
                        src_values.append(requests.compat.urljoin(url, matching_attrs))
            return src_values if src_values != list() else None


def send_long_message(chat_id, message, reply_markup, parse_mode, feaut):
    chunk_size = 4096  # Максимальный размер сообщения
    message_parts = [message[i:i + chunk_size] for i in range(0, len(message), chunk_size)]

    for i, part in enumerate(message_parts):
        if feaut == 'Type1':
            if i == len(message_parts) - 1:
                sent_message = bot.send_message(chat_id=chat_id, text=part, parse_mode=parse_mode,
                                                reply_markup=reply_markup)
                mess_id[chat_id] = [part, sent_message.message_id, parse_mode]
            else:
                bot.send_message(chat_id=chat_id, text=part, parse_mode=parse_mode)
                time.sleep(0.1)
        elif feaut == 'Type2':
            if chat_id in mess_id:
                if i == len(message_parts) - 1:
                    if i == 0:
                        sent_message = bot.edit_message_text(chat_id=chat_id, text=part, parse_mode=parse_mode,
                                                             reply_markup=reply_markup, message_id=mess_id[chat_id][1])
                        mess_id[chat_id] = [part, sent_message.message_id, parse_mode]
                    else:
                        sent_message = bot.send_message(chat_id=chat_id, text=part, parse_mode=parse_mode,
                                                        reply_markup=reply_markup)
                        mess_id[chat_id] = [part, sent_message.message_id, parse_mode]
                else:
                    bot.edit_message_text(chat_id=chat_id, text=part, parse_mode=parse_mode,
                                          message_id=mess_id[chat_id][1])
                    time.sleep(0.1)


def finder(page, feaut, chap, us_id, res_text, sent_mess):
    echo_enabled[us_id] = False
    img_answers = gdz_check(page, feaut, chap)
    if img_answers is not None:
        bot.edit_message_text(text=res_text, chat_id=us_id, message_id=sent_mess)
        if feaut == 'eng':
            print(f'{us_id}: book: {len(img_answers)}s')
            send_long_message(us_id, img_answers, markup2, 'html', 'Type1')
            # сюда можно добавлять учебники, ответы в которых выдаются в виде текста
        else:
            print(f"\n{res_text}\n{img_answers}")
            for num, value in enumerate(img_answers):
                text = f'<a href="{str(value)}">{num + 1}:</a>'
                if num + 1 == len(img_answers):
                    edit_mess = bot.send_message(us_id, text, parse_mode='HTML', reply_markup=markup2)
                    mess_id[us_id] = [text, edit_mess.message_id, 'HTML']
                else:
                    bot.send_message(us_id, text, parse_mode='HTML')
                    time.sleep(0.1)

    elif img_answers is None:
        edit_mess = bot.edit_message_text("Неверный номер задания!", chat_id=us_id,
                                          message_id=sent_mess, reply_markup=markup2)
        mess_id[us_id] = ["Неверный номер задания!", edit_mess.message_id]
    time.sleep(0.5)
    echo_enabled[us_id] = True


def chap_finder(user_id, mess):
    if user_states[user_id] == FIRST_NUMBER:  # сначала получим параграф
        user_states[user_id] = SECOND_NUMBER  # Переход к следующему состоянию
        bot.send_message(user_id, "<i>Введите номер задания:</i>", parse_mode='html')
        user_inputs[user_id] = [mess]  # Сохраняем первую цифру
        return FIRST_NUMBER
    elif user_states[user_id] == SECOND_NUMBER:  # Сохраняем номер задания и обрабатываем результат
        user_inputs[user_id].append(mess)
        return SECOND_NUMBER
    else:
        return None


def delete_messages(chat_id):
    if chat_id in user_messages:
        for d in user_messages[chat_id]:
            delete_msg(chat_id, message_id=d, delay=0)  # Удаление предыдущего сообщения, если оно существует
    user_messages[chat_id] = list()


def edit_util(user_id):
    try:
        if user_id in mess_id:
            if mess_id[user_id][0] and len(mess_id[user_id]) == 2:
                bot.edit_message_text(text=mess_id[user_id][0], chat_id=user_id,
                                      message_id=mess_id[user_id][1], parse_mode='html')
    except (TypeError, IndexError, telebot.apihelper.ApiTelegramException) as e:
        print('Based:', e)


def edit_gpt(user_id):
    try:
        if user_id in mess_id:
            if len(mess_id[user_id]) == 3:
                print(len(mess_id[user_id]))
                bot.edit_message_text(text=mess_id[user_id][0], chat_id=user_id,
                                      message_id=mess_id[user_id][1], parse_mode=mess_id[user_id][2])
    except (TypeError, IndexError, telebot.apihelper.ApiTelegramException) as e:
        print('Based_gpt:', e)


markup = types.InlineKeyboardMarkup(row_width=2)
button1 = types.InlineKeyboardButton(text="Геометрия", callback_data="/Геометрия")
button2 = types.InlineKeyboardButton(text="Алгебра", callback_data="/Алгебра")
button3 = types.InlineKeyboardButton(text="Физика", callback_data="/Физика")
button4 = types.InlineKeyboardButton(text="Информатика", callback_data="/Информатика")
button5 = types.InlineKeyboardButton(text="Англ.яз", callback_data="/Англ.яз")
button6 = types.InlineKeyboardButton(text="Русский", callback_data="/Русский")
button7 = types.InlineKeyboardButton(text="Вернуться назад", callback_data="go_to_start")
markup.add(button1, button2, button3, button4, button5, button6, button7)

markupcopy = types.InlineKeyboardMarkup(row_width=2)
markupcopy.add(button1, button2, button3, button4, button5, button6)

markup2 = types.InlineKeyboardMarkup()
button8 = types.InlineKeyboardButton(text="Вернуться назад", callback_data="go_to_start_textbook")
markup2.add(button8)

markup3 = types.InlineKeyboardMarkup(row_width=1)
button_book = types.InlineKeyboardButton(text="Решить из учебника (ФГОС)", callback_data="answers_textbook")
button_gpt = types.InlineKeyboardButton(text="Спросить у YaGPT", callback_data="answers_gpt")
markup3.add(button_book, button_gpt)

markup4 = types.InlineKeyboardMarkup()
button9 = types.InlineKeyboardButton(text="Вернуться назад", callback_data='go_to_menu')
markup4.add(button9)

markup5 = types.InlineKeyboardMarkup(row_width=2)
buttonPHY1 = types.InlineKeyboardButton(text="Учебник", callback_data='textbook')
buttonPHY2 = types.InlineKeyboardButton(text="Задачник", callback_data='taskbook')
markup5.add(buttonPHY1, buttonPHY2, button8)

markup6 = types.InlineKeyboardMarkup(row_width=2)
buttonINFO1 = types.InlineKeyboardButton(text="Учебник", callback_data='/Информатика/уч')
buttonINFO2 = types.InlineKeyboardButton(text="Задачник", callback_data='/Информатика/рт')
markup6.add(buttonINFO1, buttonINFO2, button8)

markup7 = types.ReplyKeyboardMarkup(resize_keyboard=True)
button10 = types.InlineKeyboardButton(text="/start")
markup7.add(button10)

markup8 = types.InlineKeyboardMarkup()
button11 = types.InlineKeyboardButton(text="Готово", callback_data='call_gpt')
button12 = types.InlineKeyboardButton(text="Отменить", callback_data='call_gpt2')
markup8.add(button11, button12)

copymark = types.InlineKeyboardMarkup()
copybut = types.InlineKeyboardButton(text="Скопировать текст", callback_data="copy")
copymark.add(copybut)

profmark = types.InlineKeyboardMarkup()
butclose = types.InlineKeyboardButton(text="Закрыть", callback_data="go_to_start")
profmark.add(butclose)

bot.set_my_commands([
    telebot.types.BotCommand("/start", "Выбор решения"),
    telebot.types.BotCommand("/start_textbook", "Решить из учебника"),
    telebot.types.BotCommand("/start_gpt", "Спросить у YaGPT"),
    telebot.types.BotCommand("/profile", "Профиль")
])


@bot.message_handler(commands=['profile'])
def profile(profile_info):
    user_id = profile_info.from_user.id
    chat_id = profile_info.chat.id
    message_mem[user_id] = profile_info
    echo_enabled[user_id] = False
    echo_enabled2[user_id] = False

    db.add_user(user_id=user_id, info=profile_info)  # Добавляем пользователя в базу данных

    delete_messages(chat_id)
    if user_id in mess_id:
        print(len(mess_id[user_id]))
        if len(mess_id[user_id]) >= 3:
            edit_gpt(user_id)
        else:
            edit_util(user_id)
    try:
        data = db.get_user_info(user_id=user_id)
        info = json.loads(data['info'])
        profile_text = text_mark4.format(data['id'], str(info['Ник']).replace('`', '').lstrip(),
                                         str(info['Юзернейм']).replace('`', ''), **info)
        del_mess = bot.reply_to(profile_info, text=profile_text, parse_mode='markdown', reply_markup=profmark)
        user_messages[chat_id].append(del_mess.message_id)
        mess_id[user_id] = [None, del_mess.message_id]
    except Exception as e:
        print(e)


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    message_mem[user_id] = message
    echo_enabled[user_id] = False
    echo_enabled2[user_id] = False

    db.add_user(user_id=user_id, info=message)  # Добавляем пользователя в базу данных
    info = db.get_user_info(user_id)
    print(json.loads(info['info']))

    user_count = db.get_user_count()  # Получаем количество пользователей
    if user_id == admin_id:  # Отправляем сообщение с количеством пользователей токо для админа
        adm_mess = bot.send_message(message.chat.id, f"Добро пожаловать! Количество пользователей бота: {user_count}")
        delete_msg(chat_id, message_id=adm_mess.message_id, delay=1)

    delete_messages(chat_id)
    if user_id in mess_id:
        if len(mess_id[user_id]) - 1 >= 2:
            edit_gpt(user_id)
        else:
            edit_util(user_id)

    del_mess = bot.reply_to(message, text=text_mark1, parse_mode='html', reply_markup=markup3)
    user_messages[chat_id].append(del_mess.message_id)
    mess_id[user_id] = [None, del_mess.message_id]


@bot.message_handler(commands=['start_textbook'])
def start_textbook(message):
    user_id = message.from_user.id  # Получаем ID пользователя
    message_mem[user_id] = message  # Здесь все данные о сообщении хранятся
    chat_id = message.chat.id
    echo_enabled[user_id] = False
    echo_enabled2[user_id] = False

    if user_id in mess_id:
        if len(mess_id[user_id]) - 1 >= 2:
            edit_gpt(user_id)
        else:
            edit_util(user_id)

    delete_messages(chat_id)

    del_mess = bot.reply_to(message, text=text_mark2, parse_mode='html', reply_markup=markup)
    user_messages[chat_id].append(del_mess.message_id)
    mess_id[user_id] = [text_mark2, del_mess.message_id]


@bot.message_handler(commands=['start_gpt'])
def start_gpt(message_gpt):
    chat_id = message_gpt.chat.id
    user_id_gpt = message_gpt.from_user.id
    message_mem[user_id_gpt] = message_gpt
    echo_enabled[user_id_gpt] = False
    echo_enabled2[user_id_gpt] = True

    if user_id_gpt in mess_id:
        if len(mess_id[user_id_gpt]) - 1 >= 2:
            edit_gpt(user_id_gpt)
        elif mess_id[user_id_gpt][0] in {text_mark1, text_mark2, text_mark3}:
            delete_messages(chat_id)
        else:
            edit_util(user_id_gpt)

    bot.send_message(chat_id=chat_id, text="<i>Отправьте текст или изображение с текстом:</i>", parse_mode='html')

    @bot.message_handler(func=lambda photo_gpt: echo_enabled2.get(photo_gpt.from_user.id), content_types=['photo'])
    # Обработчик изображений
    def handle_image(message):
        user_id = message.from_user.id
        echo_enabled2[user_id] = False
        try:
            message_mem[user_id] = message
            edit_util(user_id)
            delete_messages(user_id)

            file_info = bot.get_file(message.photo[-1].file_id)
            file_url = f"https://api.telegram.org/file/bot{api_bot}/{file_info.file_path}"

            response = requests.get(file_url)
            img = Image.open(BytesIO(response.content))
            preprocessed_image = preprocess_image(img)

            extracted_text = pytesseract.image_to_string(preprocessed_image, config=r'--oem 3 --psm 6', lang='rus+eng')
            # Извлекаем текст с изображения

            if extracted_text.strip():
                img_text[user_id] = extracted_text
                copy = bot.reply_to(message, f"Извлечённый текст:\n{extracted_text[:80]}...",
                                    reply_markup=copymark)
                del_mess = bot.send_message(user_id, "<i>Введите доп. текст\nили жмите <b>\"Готово\"</b>:</i>",
                                            parse_mode='html', reply_markup=markup8)
                user_messages[chat_id].append(del_mess.message_id)
                user_copy[chat_id] = [copy.message_id, f"```Извлечённый_текст:\n{(str(extracted_text).replace
                                                                                  ('`', ''))[:4096]}```"]
            else:
                del_mess = bot.reply_to(message, "К сожалению, не удалось распознать текст с изображения.",
                                        reply_markup=markup4)
                user_messages[chat_id].append(del_mess.message_id)
        except Exception as e:
            print('ErrGPT', e)
            del_mess = bot.reply_to(message, f"Произошла ошибка.", reply_markup=markup4)
            user_messages[chat_id].append(del_mess.message_id)
        echo_enabled2[user_id] = True


@bot.message_handler(func=lambda mess_gpt: echo_enabled2.get(mess_gpt.from_user.id) is True)
def echo_gpt(mess_gpt):
    user_id = mess_gpt.from_user.id

    echo_enabled2[user_id] = False
    chat_id = mess_gpt.chat.id
    user_message = mess_gpt.text
    delete_messages(chat_id)

    if user_id in mess_id:
        if len(mess_id[user_id]) - 1 >= 2:
            edit_gpt(user_id)
        else:
            edit_util(user_id)

    data = db.get_user_info(user_id=user_id)
    info = json.loads(data['info'])
    if info["GPT-лимит"] <= 0:
        edit_mess = bot.reply_to(mess_gpt, text='<i>К сожалению, на сегодня вы исчерпали лимит запросов. Возвращайтесь '
                                                'завтра⏳</i>', parse_mode='html', reply_markup=profmark)
        user_messages[chat_id].append(edit_mess.message_id)
    else:
        edit_mess = bot.reply_to(mess_gpt, text='<i>Обработка запроса...</i>', parse_mode='html')
        mess_id[user_id] = [None, edit_mess.message_id]
        try:
            if img_text.get(user_id):
                if user_message:
                    text = f'{img_text[user_id]} — ЗАДАНИЕ: {user_message}'
                else:
                    text = img_text[user_id]
                result = send_request_to_chatgpt(text, user_id)
                del img_text[user_id]
            else:
                result = send_request_to_chatgpt(user_message, user_id)

            print(f'{user_id}: {len(result)}s')
            send_long_message(user_id, result, markup4, 'markdown', 'Type2')

        except Exception as e:
            print('ErrGPT', e)
        echo_enabled2[user_id] = True


@bot.callback_query_handler(func=lambda gpt: gpt.data in {'call_gpt', 'call_gpt2', 'go_to_menu', 'copy'})
def gpt_call(gpt):
    bot.answer_callback_query(gpt.id)
    mess2 = gpt.data
    user_id = gpt.from_user.id

    if user_id in message_mem:
        try:
            if mess2 == 'call_gpt':
                echo_gpt(message_mem[user_id])

            elif mess2 == 'call_gpt2':
                delete_messages(user_id)
                del img_text[user_id]
                start_gpt(message_mem[user_id])

            elif mess2 == 'go_to_menu':
                start(message_mem[user_id])
        except Exception as e:
            print(f"Ошибка2: {e}")

        try:
            if mess2 == 'copy':
                if user_id in user_copy:
                    bot.edit_message_text(text={user_copy[user_id][1]}, message_id=user_copy[user_id][0],
                                          chat_id=user_id, parse_mode='markdown')
                    del user_copy[user_id]
        except Exception as mark_err:
            if user_id in user_copy:
                del user_copy[user_id]
            print(f"Ошибка3: {mark_err}")
    else:
        handle_old_request(user_id)


@bot.callback_query_handler(func=lambda message_drop: echo_enabled2.get(message_drop.from_user.id) is not True)
def gdz(message_drop):
    bot.answer_callback_query(message_drop.id)
    mess2 = message_drop.data
    user_id_drop = message_drop.from_user.id

    if user_id_drop in message_mem:
        try:
            # Определяем действия для команд
            commands = {
                "go_to_start_textbook": lambda: start_textbook(message_mem[user_id_drop]),
                "answers_textbook": lambda: start_textbook(message_mem[user_id_drop]),
                "answers_gpt": lambda: (
                    bot.edit_message_text(text='<b><i>YaGPT — нейросеть, идеально подходящая для написания текстов и '
                                               'решения задач.</i></b>',
                                          chat_id=user_id_drop,
                                          message_id=mess_id[user_id_drop][1], parse_mode='HTML', reply_markup=markup4),
                    start_gpt(message_mem[user_id_drop])
                ),
                "go_to_start": lambda: start(message_mem[user_id_drop])
            }

            # Обрабатываем команды
            if mess2 in commands:
                commands[mess2]()
            else:
                # Обработка предметов
                if mess2 == '/Англ.яз':
                    bot.send_message(user_id_drop, "<i>Введите номер и букву модуля:</i>", parse_mode='html')

                elif mess2 in ['/Физика', '/Информатика']:
                    process_subject(mess2, user_id_drop)

                elif mess2 == 'textbook':
                    bot.send_message(text='<i>Введите номер упражнения:</i>', chat_id=user_id_drop, parse_mode='HTML')

                elif mess2 == 'taskbook':
                    bot.send_message(text='<i>Введите номер задания:</i>', chat_id=user_id_drop, parse_mode='HTML')

                elif mess2 in ['/Информатика/уч', '/Информатика/рт']:
                    bot.send_message(text=f'<i>Введите номер {"параграфа" if mess2 == "/Информатика/уч" else "задания"}'
                                          f':</i>', chat_id=user_id_drop, parse_mode='HTML')

                else:
                    bot.send_message(user_id_drop, "<i>Введите номер задания:</i>", parse_mode='html')

                # Обновление состояния пользователя
                user_prop[user_id_drop] = mess2
                echo_enabled2[user_id_drop] = False
                echo_enabled[user_id_drop] = True
                user_states[user_id_drop] = FIRST_NUMBER

        except Exception as e:
            print(f"Ошибка: {e}")
    else:
        handle_old_request(user_id_drop)

    @bot.message_handler(
        func=lambda mess: echo_enabled.get(mess.from_user.id) is True and user_prop.get(mess.from_user.id) not in [
            '/Физика', '/Информатика'])
    def echo_all(mess):
        user_id = mess.from_user.id
        chat_id = mess.chat.id

        user_message_id = user_messages.get(user_id)
        if user_message_id:
            delete_msg(user_id, message_id=user_message_id, delay=0)

        if echo_enabled.get(user_id):
            if user_id in mess_id:
                if mess_id.get(user_id)[0] == "Неверный номер задания!":
                    delete_msg(user_id, message_id=mess_id[user_id][1], delay=0)
                elif len(mess_id.get(user_id)) == 3:
                    edit_gpt(user_id)
                elif len(mess_id.get(user_id)) == 2:
                    edit_util(user_id)
                del mess_id[user_id]

            nonlocal mess2
            mess2 = user_prop.get(chat_id)
            ex = mess.text

            try:
                if mess2 not in ['/Информатика/уч', '/Англ.яз']:
                    ex = int(ex)

                if mess2 in ['/Информатика/уч', '/Англ.яз'] and user_inputs.get(user_id) is None:
                    sent_message = None
                else:
                    sent_message = bot.reply_to(mess, f"Поиск по номеру: {ex}...").message_id

                # Определяем поведение для разных предметов
                nonlocal commands
                commands = {
                    '/Геометрия': {'feaut': 'ge', 'res_text': "Геометрия|>Решения:"},
                    '/Алгебра': {'feaut': 'al', 'res_text': "Алгебра|>Решения:"},
                    'textbook': {'feaut': 'phybook', 'res_text': "Физика.уч|>Решения:"},
                    'taskbook': {'feaut': 'phy', 'res_text': "Физика.зд|>Решения:"},
                    '/Русский': {'feaut': 'rus', 'res_text': "Русский|>Решения:"},
                    '/Информатика/рт': {'feaut': 'info_copybook', 'res_text': "Инфо.рт|>Решения:"}
                }

                if mess2 in commands:
                    params = commands[mess2]
                    finder(page=ex, feaut=params['feaut'], chap=None, us_id=user_id, res_text=params['res_text'],
                           sent_mess=sent_message)

                elif mess2 == '/Англ.яз':
                    process_english_task(user_id, mess, sent_message)

                elif mess2 == '/Информатика/уч':
                    process_informatics_task(user_id, mess, sent_message)

            except ValueError:
                handle_invalid_number(mess, user_id, chat_id, mess2, None)


def process_english_task(user_id, mess, sent_message):
    replay = chap_finder(user_id, mess.text)
    if replay == SECOND_NUMBER:
        chap, page = str(user_inputs[user_id][0]), str(user_inputs[user_id][1])
        del user_inputs[user_id]
        finder(page=page, feaut='eng', chap=chap, us_id=user_id, res_text="Англ.яз|>Решения:", sent_mess=sent_message)
        user_states[user_id] = FIRST_NUMBER
        bot.send_message(text="<i>Введите номер и букву модуля:</i>", chat_id=user_id, parse_mode='HTML')


def process_informatics_task(user_id, mess, sent_message):
    replay = chap_finder(user_id, mess.text)
    if replay == SECOND_NUMBER:
        chap, page = str(user_inputs[user_id][0]), str(user_inputs[user_id][1])
        del user_inputs[user_id]
        finder(page=page, feaut='info', chap=chap, us_id=user_id, res_text="Инфо.уч|>Решения:", sent_mess=sent_message)
        user_states[user_id] = FIRST_NUMBER
        bot.send_message(text='<i>Введите номер параграфа:</i>', chat_id=user_id, parse_mode='HTML')


def handle_invalid_number(mess, user_id, chat_id, mess2, sent_message):
    user_states[user_id] = FIRST_NUMBER
    if mess2 in ['/Информатика/уч', '/Англ.яз'] and sent_message is not None:
        edit_mess = bot.edit_message_text("Неверный номер задания!", chat_id, sent_message, reply_markup=markup2)
    else:
        edit_mess = bot.reply_to(mess, "Неверный номер задания!", reply_markup=markup2)
    mess_id[user_id] = ["Неверный номер задания!", edit_mess.message_id]


def process_subject(subject, user_id_drop):  # Функция обработки сообщений для предметов /Физика и /Информатика.
    bot.edit_message_text(text=mess_id[user_id_drop][0], chat_id=user_id_drop,
                          message_id=mess_id[user_id_drop][1], parse_mode='HTML', reply_markup=markupcopy)
    subject_text = f"<b><i>{subject.split('/')[1].capitalize()}:</i></b>"
    edit_mess = bot.send_message(text=subject_text, chat_id=user_id_drop, parse_mode='HTML',
                                 reply_markup=(markup5 if subject == '/Физика' else markup6))
    mess_id[user_id_drop] = [subject_text, edit_mess.message_id]
    user_messages[user_id_drop].append(edit_mess.message_id)


def handle_old_request(user_id_drop):  # Функция обработки старых запросов.
    delete_messages(user_id_drop)
    del_mess = bot.send_message(text=text_mark3, chat_id=user_id_drop, parse_mode='html', reply_markup=markup7)
    user_messages[user_id_drop].append(del_mess.message_id)
    mess_id[user_id_drop] = [text_mark3]


def load_data():
    """Загрузка данных из файла, если он существует."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    return {"value": 10, "last_update": None}  # Лимит для всех


def save_data(data):
    """Сохранение данных в файл."""
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file)


async def wait_until_midnight():
    """Рассчитать время до следующего 00:00"""
    data = load_data()
    current_date = datetime.now().date().isoformat()
    if data["last_update"] != current_date:
        data["last_update"] = current_date
        save_data(data)

        for user in db.get_all_ids():
            info = db.get_user_info(user_id=user)
            info = json.loads(info['info'])
            info["GPT-лимит"] = data["value"]
            db.update_user_info(user_id=user, info=json.dumps(info))

        print(f"[{datetime.now().replace(microsecond=0)}] Значение обновлено: {data['value']}")

    now = datetime.now()
    # Рассчитываем, сколько осталось до полуночи
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    seconds_until_midnight = (tomorrow - now).total_seconds()

    print(f"До полуночи осталось: {seconds_until_midnight:.0f} секунд")
    await asyncio.sleep(seconds_until_midnight)  # Ожидание до 00:00


async def daily_task():
    """Асинхронная задача. Выполняется каждый день от 00:00. Обновление переменной на 10, если сегодня новый день."""
    data = load_data()
    current_date = datetime.now().date().isoformat()
    data["last_update"] = current_date
    save_data(data)

    for user in db.get_all_ids():
        info = db.get_user_info(user_id=user)
        info = json.loads(info['info'])
        info["GPT-лимит"] = data["value"]
        db.update_user_info(user_id=user, info=json.dumps(info))

    print(f"[{datetime.now().replace(microsecond=0)}] Значение обновлено: {data['value']}")


async def scheduled_task():
    """Цикл для выполнения задач каждый день."""
    while True:
        await wait_until_midnight()
        await daily_task()


def run_background_task():
    """Запускает asyncio loop в отдельном потоке."""
    asyncio.run(scheduled_task())


if __name__ == "__main__":
    try:
        print("Бот запущен.")
        background_thread = Thread(target=run_background_task, daemon=True)
        background_thread.start()

        bot.polling(none_stop=True)
    except KeyboardInterrupt:
        print("Бот остановлен.")
    db.close()
