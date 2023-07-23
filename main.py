import json
import locale
import re
import time
from datetime import datetime, date, timedelta
import os

import psycopg2
import telebot
import xlsxwriter
from config import host, database, user, password, port, admins, token
from geopy import Yandex
from telebot import types
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton

#Токен бота
bot = telebot.TeleBot(token, parse_mode=None, threaded=False)
# Локаль для вывода на русском языке
locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
# Создание таблицы пользователей
conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
conn.autocommit = True
cur = conn.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS users ('
            'user_id bigint, '
            'username VARCHAR (50))')
cur.close()
conn.close()



@bot.message_handler(commands=['start'])
def start(message):
    global admins
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
    user_data = cur.fetchone()

    if user_data is None:
        bot.send_message(message.chat.id, 'Привет! Я бот для учета рабочего времени. '
                                          'Чтобы начать пользоваться ботом введите пароль: ')
        bot.register_next_step_handler(message, get_password)
    else:
        if message.from_user.id in admins:
            # Кнопки админам
            markup = types.InlineKeyboardMarkup()
            high_notice_button = types.InlineKeyboardButton(text='Высота/Примечание', callback_data='high_notice_button')
            markup.row(high_notice_button)
            stat_employee = types.InlineKeyboardButton(text='Cформировать отчет', callback_data='stat_employee')
            markup.row(stat_employee)
            drop_user = types.InlineKeyboardButton(text='Удалить сотрудника', callback_data='drop_user')
            markup.row(drop_user)
            bot.send_message(message.chat.id, f'Вы авторизованы как администратор. '
                                              f'Ваш id: {message.from_user.id}\n\n ' ,reply_markup=markup)
        else:
            bot.send_message(message.chat.id, f'Вы авторизованы как пользователь. Ваш id: {message.from_user.id}\n\n '
                                              f'Чтобы начать отсчет рабочего времени, введите - /start_work')

def get_password(message):
    with open("password.txt", "r") as f:
        passwords = f.read().splitlines()
        if message.text in passwords:
            bot.send_message(message.chat.id, f'Пароль верный, теперь ты можешь пользоваться ботом! '
                                              f'Введите свою фамилию и имя в формате "Фамилия Имя"')
            bot.register_next_step_handler(message, get_name)
        else:
            bot.send_message(message.chat.id, f'Вы ввели неверный пароль, повторите попытку - /start')

def get_name(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    user_id = message.from_user.id
    name = message.text

    cur.execute(f"INSERT INTO users (user_id, username) VALUES ('{user_id}', '{name}')")
    conn.commit()
    # Создание персональной таблицы юзера
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS id{message.from_user.id} (id SERIAL PRIMARY KEY, "  
        f"start_time timestamp, end_time timestamp, pause time, total_time time, address VARCHAR, "
        f"high float, notice VARCHAR)")
    conn.commit()
    cur.close()
    conn.close()
    start(message)



@bot.message_handler(commands=['start_work'])
def check_your_pass(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
    user_data = cur.fetchone()
    if user_data:
        address_button_start(message)
    else:
        bot.send_message(message.chat.id, 'Вы не авторизованы, нажмите - /start')

def address_button_start(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM id{message.from_user.id} WHERE id=(SELECT MAX(id) FROM id{message.from_user.id})")
    user_data = cur.fetchone()

    if user_data is not None and user_data[1] is not None and user_data[2] is None:
        bot.send_message(message.chat.id, f'Вы еще незакончили прошлую работу!\n\nЗакончить работу - /end_work')
    else:
        button_location = KeyboardButton('Отправить местоположение', request_location=True)
        keyboard = ReplyKeyboardMarkup([[button_location]], resize_keyboard=True, one_time_keyboard=True)
        json_markup = json.dumps(keyboard.to_dict())
        bot.send_message(message.chat.id, 'Пожалуйста, отправьте свою локацию с помощью кнопки',
                         reply_markup=json_markup)

@bot.message_handler(commands=['end_work'])
def check_your_pass(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
    user_data = cur.fetchone()
    if user_data:
        address_button_stop(message)
    else:
        bot.send_message(message.chat.id, 'Вы не авторизованы, нажмите - /start')

def address_button_stop(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM id{message.from_user.id} WHERE id=(SELECT MAX(id) FROM id{message.from_user.id})")
    user_data = cur.fetchone()

    if user_data is not None:
        if user_data[1] is not None and user_data[2] is None:
            # Кнопка запроса местоположения
            button_location = KeyboardButton('Отправить местоположение', request_location=True)
            keyboard = ReplyKeyboardMarkup([[button_location]], resize_keyboard=True, one_time_keyboard=True)
            json_markup = json.dumps(keyboard.to_dict())
            bot.send_message(message.chat.id, 'Пожалуйста, отправьте свою локацию с помощью кнопки',
                             reply_markup=json_markup)
        else:
            bot.send_message(message.chat.id, f'Вы еще не начали работать!\n\n'
                                              f'Начать отсчет рабочего времени - /start_work')

@bot.message_handler(content_types=['location'])
def check_your_pass(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
    user_data = cur.fetchone()
    if user_data:
        fake_location(message)
    else:
        bot.send_message(message.chat.id, 'Вы не авторизованы, нажмите - /start')

def fake_location(message):
    # реализовано не точно(можно обмануть если отправить через скрепку пересланным сообщением)
    if message.reply_to_message is not None \
            and message.reply_to_message.text == 'Пожалуйста, отправьте свою локацию с помощью кнопки':
        kb_remove = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id, 'Локация установлена', reply_markup=kb_remove)
        start_or_stop(message)
    else:
        kb_remove = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id, f'Локация не принята!\n\n'
                                          'Местоположение нужно отправлять с помощью кнопки "Отправить местоположение"!'
                                          '\n\nПовторите команду: /start_work или /end_work', reply_markup=kb_remove)

def start_or_stop(message):
    place = str(message.location.latitude) + ' ' + str(message.location.longitude)
    my_loc = Yandex(api_key='0699e2eb-2236-432a-a917-1e4333c205c6', user_agent='Telegram').reverse(place)
    my_loc_adress = my_loc.address[:-33]
    bot.send_message(message.chat.id, f'{my_loc_adress}')

    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM id{message.from_user.id} WHERE id=(SELECT MAX(id) FROM id{message.from_user.id})")
    user_data = cur.fetchone()
    if user_data is not None:
        if user_data[1] is not None and user_data[2] is None:
            end_work(message, my_loc_adress)
        else:
            start_work(message, my_loc_adress)
    else:
        start_work(message, my_loc_adress)
    cur.close()
    conn.close()


def start_work(message, my_loc_adress):
    global admins
    bot.send_message(message.chat.id, f'Вы начали работу\n'
                                      f'по адресу {my_loc_adress}\n'
                                      f'Время начала: {datetime.now().strftime("%d.%m.%Y %H:%M")}\n\n\n'
                                      f"Закончить работу, нажмите: /end_work\n\n"
                                      f"Поставить на паузу: /pause\n\n"
                                      f"Ошибочно начали работу: /cancel")

    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
    user_data1 = cur.fetchone()
    for admin in admins:
        bot.forward_message(admin, from_chat_id=message.chat.id, message_id=message.message_id)
        bot.send_message(admin, f'{user_data1[1]} начал работу\n'
                                 f'по адресу {my_loc_adress}\n'
                                 f'Время начала: {datetime.now().strftime("%d.%m.%Y %H:%M")}')
    cur = conn.cursor()
    cur.execute(f"INSERT INTO id{message.from_user.id} (start_time, pause, address) "
                f"VALUES ('{datetime.now().strftime('%d-%m-%Y %H:%M')}:00', TIME '00:00:00', '{my_loc_adress}')")
    conn.commit()


def end_work(message, my_loc_adress):
    global admins
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"UPDATE id{message.from_user.id} SET end_time='{datetime.now().strftime('%d-%m-%Y %H:%M')}:00' "
                f"WHERE id=(SELECT MAX(id) FROM id{message.from_user.id})")
    conn.commit()

    cur.execute(f"SELECT * FROM id{message.from_user.id} WHERE id=(SELECT MAX(id) FROM id{message.from_user.id})")
    user_data = cur.fetchone()
    # Обработка паузы
    if str(user_data[3]) != '00:00:00':
        time_with_pause = user_data[1] + (datetime.combine(date.min, user_data[3]) - datetime.min)
        total_time = datetime.now() - time_with_pause
    else:
        total_time = datetime.now() - user_data[1]

    cur.execute(f"UPDATE id{message.from_user.id} "
                f"SET total_time='{total_time}' "
                f"WHERE id=(SELECT MAX(id) FROM id{message.from_user.id})")
    conn.commit()

    cur.execute(f"SELECT id FROM id{message.from_user.id} WHERE id=(SELECT MAX(id) FROM id{message.from_user.id})")
    id_info = cur.fetchone()[0]

    bot.send_message(message.chat.id,
                     f'Рабочее время завершено: \n{datetime.now().strftime("%d.%m.%Y %H:%M")}\n'
                     f'Общее время работы: {str(total_time)[:-7]}\n'
                     f'ID: {str(id_info)}\n\n'
                     f'Оставить комментарий: /comment\n\n'
                     f'Начать новую работу: /start_work')
    # Конец работы админу
    cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
    user_data1 = cur.fetchone()
    for admin in admins:
        bot.forward_message(admin, from_chat_id=message.chat.id, message_id=message.message_id)
        bot.send_message(admin, f'{user_data1[1]} закончил работу\n'
                                f'в {datetime.now().strftime("%d.%m.%Y %H:%M")}\n'
                                f'по адресу {my_loc_adress}\n'
                                f'Общее время работы: {str(total_time)[:-7]}\n\n'
                                f'ID: {str(id_info)}')
    cur.close()
    conn.close()


@bot.message_handler(commands=['cancel'])
def check_your_pass(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
    user_data = cur.fetchone()
    if user_data:
        # Кнопки подтверждения
        markup = types.InlineKeyboardMarkup()
        yes_cancel_button = types.InlineKeyboardButton(text='Подтвердить', callback_data='yes_cancel')
        markup.row(yes_cancel_button)
        no_cancel_button = types.InlineKeyboardButton(text='Нет', callback_data='no_cancel')
        markup.row(no_cancel_button)
        bot.send_message(message.chat.id, f'Подтвердите, чтобы отменить рабочий день:\n\n ', reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 'Вы не авторизованы, нажмите - /start')



@bot.callback_query_handler(func=lambda call: call.data == 'yes_cancel')
def cancel(call: types.CallbackQuery):
    global admins
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM id{call.from_user.id} WHERE id=(SELECT MAX(id) FROM id{call.from_user.id})")
    user_data1 = cur.fetchone()

    if user_data1[1] is not None and user_data1[2] is None:
        cur.execute(f"DELETE FROM id{call.from_user.id} WHERE id=(SELECT MAX(id) FROM id{call.from_user.id})")
        conn.commit()
        bot.send_message(call.message.chat.id, f"Таймер сброшен. Теперь можете заново начать работу /start_work")
        for admin in admins:
            cur.execute(f"SELECT * FROM users WHERE user_id={call.from_user.id}")
            user_data = cur.fetchone()
            bot.send_message(admin, f"{user_data[1]} отменил свой рабочий день.")
    else:
        bot.send_message(call.message.chat.id, f"Нечего отменять, вы еще не начали работать")

@bot.callback_query_handler(func=lambda call: call.data == 'no_cancel')
def no_cancel(call: types.CallbackQuery):
    bot.send_message(call.message.chat.id, f"Продолжайте работать")



@bot.message_handler(commands=['pause'])
def check_your_pass(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
    user_data = cur.fetchone()
    if user_data:
        pause_start(message)
    else:
        bot.send_message(message.chat.id, 'Вы не авторизованы, нажмите - /start')

def pause_start(message):
    global admins
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()

    cur.execute(f"SELECT * FROM id{message.from_user.id} WHERE id=(SELECT MAX(id) FROM id{message.from_user.id})")
    user_data = cur.fetchone()
    if str(user_data[3]) == '00:00:00':
        if user_data[1] is not None and user_data[2] is None:
            bot.send_message(message.chat.id, f"Перерыв начался:\n{datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                                              f"Продолжить работу: /continue")
            cur.execute(f"UPDATE id{message.from_user.id} SET pause='{datetime.now().strftime('%d-%m-%Y %H:%M')}:00' "
                        f"WHERE id=(SELECT MAX(id) FROM id{message.from_user.id})")
            conn.commit()
            for admin in admins:
                cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
                user_data1 = cur.fetchone()
                bot.send_message(admin, f'{user_data1[1]} нажал паузу:\n{datetime.now().strftime("%d.%m.%Y %H:%M")}')
        else:
            bot.send_message(message.chat.id, f'Вы еще не начали работать!\n\n'
                                              f'Начать отсчет рабочего времени: /start_work')
    else:
        bot.send_message(message.chat.id, f'У Вас была уже пауза в этой смене!\n\n'
                                          f'Чтобы повторно использовать паузу закончите текущую работу '
                                          f'и начните новую: /end_work')


@bot.message_handler(commands=['continue'])
def check_your_pass(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
    user_data = cur.fetchone()
    if user_data:
        pause_end(message)
    else:
        bot.send_message(message.chat.id, 'Вы не авторизованы, нажмите - /start')

def pause_end(message):
    global admins
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM id{message.from_user.id} WHERE id=(SELECT MAX(id) FROM id{message.from_user.id})")
    user_data = cur.fetchone()

    if user_data[1] is not None and user_data[2] is None:
        p_end = datetime.combine(date.today(), datetime.now().time())
        p_start = datetime.combine(date.today(), user_data[3])
        if p_end < p_start:
            p_end += timedelta(days=1)
        pause_time = p_end - p_start

        bot.send_message(message.chat.id, f'Общее время перерыва:\n{str(pause_time)[:7]}\nПродолжение работы...\n\n'
                                          f'Закончить работу: /end_work')
        cur.execute(f"UPDATE id{message.from_user.id} SET pause='{pause_time}' "
                    f"WHERE id=(SELECT MAX(id) FROM id{message.from_user.id})")
        conn.commit()
        for admin in admins:
            cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
            user_data1 = cur.fetchone()
            bot.send_message(admin, f'{user_data1[1]} закончил паузу:\n'
                                    f'{datetime.now().strftime("%d.%m.%Y %H:%M")}\n'
                                    f'Общее время перерыва:\n{str(pause_time)[:7]}')
    else:
        bot.send_message(message.chat.id, f'Вы еще не начали работать!\n\n'
                                          f'Начать отсчет рабочего времени: /start_work')



@bot.message_handler(commands=['comment'])
def check_your_pass(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
    user_data = cur.fetchone()
    if user_data:
        bot.send_message(message.chat.id, f'Введите текст комментария')
        bot.register_next_step_handler(message, set_comment)
    else:
        bot.send_message(message.chat.id, 'Вы не авторизованы, нажмите - /start')

def set_comment(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE user_id={message.from_user.id}")
    user_data = cur.fetchone()
    for admin in admins:
        bot.send_message(admin, f'{user_data[1]} оставил комментарий:\n\n{message.text}')

    bot.send_message(message.chat.id, f'Комментарий отправлен\n\n'
                                      f'Начать отсчет рабочего времени: /start_work')


@bot.message_handler(commands=['stat1_test'])
def stat1(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM id{message.from_user.id} "
                f"WHERE EXTRACT(MONTH FROM start_time) = EXTRACT(MONTH FROM CURRENT_TIMESTAMP)")
    result = cur.fetchall()

    stat_list = []
    for row in result:
        stat_list.append(str(f"{row[1]}   Перерыв: {str(row[3])[:6]}   Отработал: {str(row[4])[:5]}"))
    cur.execute(f"SELECT SUM(total_time) FROM id{message.from_user.id}")
    result = cur.fetchone()[0]

    bot.send_message(message.from_user.id, '\n'.join(stat_list))
    bot.send_message(message.from_user.id, f'Отработано часов в текущем месяце: {result}')
    bot.send_message(message.from_user.id, f'Чтобы начать отсчет рабочего времени, введите - /start_work')

@bot.message_handler(commands=['del1_test'])
def delete_last_string(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"DELETE FROM id{message.from_user.id} WHERE id=(SELECT MAX(id) FROM id{message.from_user.id})")
    conn.commit()
    bot.send_message(message.chat.id, f"Последняя строка в таблице удалена")

@bot.callback_query_handler(func=lambda call: call.data == "stat_employee")
def but_stat_employee(call: types.CallbackQuery):
    markup = types.InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text='Отмена', callback_data='button_cancel'))
    bot.send_message(chat_id=call.message.chat.id, text=f'Чтобы получить статистику за нужный период введите '
                                                   f'дату1 и дату2:\n(Пример: 25.01.23 17.02.23)', reply_markup=markup)
    bot.register_next_step_handler(call.message, stat_employee)

def stat_employee(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    # извлекаем даты из сообщения с помощью re
    date_matches = re.compile(r'\d{2}\.\d{2}\.\d{2}').findall(message.text)

    if len(date_matches) != 2:
        bot.send_message(message.chat.id, 'Неправильный формат дат, попробуйте снова.')
        return
    date1 = date_matches[0]
    date2 = date_matches[1]

    # все таблицы пользователей в бд
    cur.execute("""SELECT table_name FROM information_schema.tables 
                   WHERE table_schema='public' AND table_name LIKE 'id%';""")
    tables = cur.fetchall()

    for table in tables:
        tablename = table[0]
        # запрос данных из текущей таблицы
        cur.execute(f"SELECT id, coalesce(to_char(start_time, 'DD-MM-YYYY HH24:MI:SS'), ''), "
                    f"coalesce(to_char(end_time, 'DD-MM-YYYY HH24:MI:SS'), ''), "
                    f"coalesce(to_char(pause, 'HH24:MI:SS'), ''), coalesce(to_char(total_time, 'HH24:MI:SS'), ''), "
                    f"coalesce(address, ''), high, notice FROM {tablename} "
                    f"WHERE start_time::date >= '{date1}'::date AND start_time::date <= '{date2}'::date")
        result = cur.fetchall()

        cur.execute(f"SELECT username FROM users WHERE user_id = {int(tablename[2:])}")
        name = cur.fetchone()
        if name is not None:
            filename = f'{name[0]}_{datetime.now().strftime("%d-%m-%Y")}.xlsx'
        else:
            filename = f'delete_user_{datetime.now().strftime("%d-%m-%Y")}.xlsx'

        # создание xlsx-файла и запись данных
        workbook = xlsxwriter.Workbook(filename)
        worksheet = workbook.add_worksheet()
        worksheet.write_row(0, 0, [' ', 'Начало', 'Конец', 'Обед', 'Время', 'Объект', 'Высота', 'Примечания'])
        row, column = 1, 0
        for row_data in result:
            for item in row_data:
                worksheet.write(row, column, item)
                column += 1
            row += 1
            column = 0
        workbook.close()

        # отправка в бота и последующее удаление из корневой папки
        bot.send_document(message.chat.id, open(filename, 'rb'))
        os.remove(filename)


@bot.callback_query_handler(func=lambda call: call.data == "drop_user")
def but_drop_user(call: types.CallbackQuery):
    markup = types.InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text='Отмена', callback_data='button_cancel'))
    bot.send_message(chat_id=call.message.chat.id, text=f'Введите имя пользователя, которого хотите удалить:\n\n'
                                                        f'ВНИМАНИЕ: данная операция необратима!', reply_markup=markup)
    bot.register_next_step_handler(call.message, drop_user)

def drop_user(message):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"""SELECT * FROM users WHERE username='{message.text}'""")
    user_data = cur.fetchone()

    if user_data:
        cur.execute(f"DELETE FROM users WHERE username='{message.text}'")
        conn.commit()
        bot.send_message(message.chat.id, f'Вы удалили {message.text}.')
    else:
        bot.send_message(message.chat.id, f'Такого пользователя не существует либо он уже удален.')


@bot.callback_query_handler(func=lambda call: call.data == "high_notice_button")
def high_notice_users(call: types.CallbackQuery):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute("""SELECT username FROM users""")
    users = cur.fetchall()
    # Кнопки сотрудников
    markup = types.InlineKeyboardMarkup()
    for button in users:
        button_name = types.InlineKeyboardButton(text=button[0], callback_data=button[0])
        markup.add(button_name)
    button_cancel = types.InlineKeyboardButton(text='Отмена', callback_data='button_cancel')
    markup.add(button_cancel)

    bot.send_message(chat_id=call.message.chat.id,
                     text=f'Выберите сотрудника или нажмите отмена:',
                     reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def high_notice_button(call):
    if call.data == 'button_cancel':
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text='Отменено')
    else:
        conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
        cur = conn.cursor()
        cur.execute(f"SELECT user_id FROM users WHERE username = '{call.data}'")
        user_id = int(cur.fetchone()[0])

        if user_id:
            bot.send_message(chat_id=call.message.chat.id,
                             text=f'Вы выбрали {call.data}\n\n'
                                  f'Введите ID-строку, чтобы выбрать рабочий день сотрудника')
            bot.register_next_step_handler(call.message, get_id_string, user_id)
        else:
            bot.send_message(chat_id=call.message.chat.id, text=f'Ошибка: пользователь не найден!')


def get_id_string(message, user_id):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM {'id' + str(user_id)}")
    ids = cur.fetchall()

    if message.text in [str(id[0]) for id in ids]:
        upd_id = message.text
        bot.send_message(chat_id=message.chat.id, text='Введите коэффициент по данному рабочему дню '
                                                       'для сотрудника от 0.1 до 10.0.\n\n '
                                                       'По умолчанию: 1.0 (то есть 100%)')
        bot.register_next_step_handler(message, get_high, user_id, upd_id)
    else:
        bot.send_message(chat_id=message.chat.id, text=f'Такой ID-строки нет, повторите попытку')
        bot.register_next_step_handler(message, get_id_string, user_id)


def get_high(message, user_id, upd_id):
    if float(message.text) > 0.1 and float(message.text) < 10.0:

        conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
        cur = conn.cursor()
        coef = float(message.text.strip())
        cur.execute(f"SELECT total_time FROM {'id' + str(user_id)} WHERE id={upd_id}")
        row = cur.fetchone()

        if row:
            old_total_time = row[0]
            old_total_seconds = old_total_time.hour * 3600 + old_total_time.minute * 60
            new_total_seconds = old_total_seconds * coef
            new_total_time = (datetime.min + timedelta(seconds=new_total_seconds)).time()

            cur.execute(f"UPDATE id{user_id} "
                        f"SET high='{coef}', total_time='{new_total_time.strftime('%H:%M')}:00' WHERE id={upd_id}")
            conn.commit()
            bot.send_message(chat_id=message.chat.id, text=f'Установлен коэффициент {float(message.text.strip())}\n\n'
                                                           f'Теперь оставьте примечание:')
            bot.register_next_step_handler(message, get_notice, user_id, upd_id)
        else:
            bot.send_message(chat_id=message.chat.id, text=f"Не найдено для выбранного работника id={upd_id}")
            get_high(message, user_id)


def get_notice(message, user_id, upd_id):
    conn = psycopg2.connect(host=host, database=database, user=user, password=password, port=port)
    cur = conn.cursor()
    cur.execute(f"UPDATE id{user_id} SET notice='{message.text}' "
                f"WHERE id={upd_id}")
    conn.commit()
    bot.send_message(chat_id=message.chat.id, text=f'Примечание успешно сохранено.')



while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(e)
        time.sleep(15)


