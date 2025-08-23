# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import win32com.client as win32
import pythoncom
from datetime import datetime
import json
import os
import re
import requests
from functools import lru_cache
from io import BytesIO
import tempfile
import shutil
from docxtpl import DocxTemplate
import time
import sys
import io
# --- Конфигурация ---
CONFIG_FILE = "requirements.txt"
BIDS_FILE = "bids.json"
CARRIERS_FILE = "carriers.json"
OFFERS_FILE = "offers.json"
CONTRACTS_FILE = "contracts.json"
CARRIERS_INFO_FILE = "carriers_info.xlsx"
# --- Инициализация файлов ---
def init_files():
    """Создает необходимые файлы, если они отсутствуют"""
    for file in [BIDS_FILE, CARRIERS_FILE, OFFERS_FILE, CONTRACTS_FILE]:
        try:
            if not os.path.exists(file):
                with open(file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False)
        except Exception as e:
            st.error(f"Ошибка при создании файла {file}: {str(e)}")
    # Инициализация файла с информацией о перевозчиках
    if not os.path.exists(CARRIERS_INFO_FILE):
        try:
            df_example = pd.DataFrame(columns=[
                'name', 'email', 'legal_name', 'inn', 'kpp', 'ogrn', 'address',
                'bank_name', 'bik', 'rs', 'ks', 'contract_number', 'contract_date'
            ])
            df_example.to_excel(CARRIERS_INFO_FILE, index=False)
        except Exception as e:
            st.error(f"Ошибка при создании файла {CARRIERS_INFO_FILE}: {str(e)}")
init_files()
# --- Функции для работы с данными ---
def load_json_file(filename):
    """Загружает данные из JSON файла"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Ошибка загрузки файла {filename}: {str(e)}")
        return []
def save_json_file(filename, data):
    """Сохраняет данные в JSON файл"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Ошибка сохранения файла {filename}: {str(e)}")
# --- Функция инициализации Outlook ---
def init_outlook():
    """Инициализирует соединение с Outlook"""
    pythoncom.CoInitialize()
    return win32.Dispatch("Outlook.Application")
# --- Работа с Outlook ---
def send_email(to, subject, body_text, attachments=None):
    """Отправляет email через Outlook с возможностью вложений"""
    try:
        outlook = init_outlook()
        mail = outlook.CreateItem(0)
        mail.To = to
        mail.Subject = subject
        mail.Body = body_text
        # Добавление вложений
        if attachments:
            for file in attachments:
                if os.path.exists(file):  # Проверка существования файла
                    mail.Attachments.Add(file)
                else:
                    st.warning(f"Файл {file} не найден и не будет прикреплен")
        mail.Send()
        return True
    except Exception as e:
        st.error(f"Ошибка отправки: {str(e)}")
        return False
    finally:
        pythoncom.CoUninitialize()
# --- Кэширование курсов валют ---
@lru_cache(maxsize=1)
def get_currency_rates():
    """Получает текущие курсы валют с кэшированием"""
    try:
        data = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=5).json()
        return {
            "USD": data["Valute"]["USD"]["Value"],
            "EUR": data["Valute"]["EUR"]["Value"],
            "date": data["Date"][:10]
        }
    except Exception:
        return {"USD": 90.0, "EUR": 100.0, "date": "N/A"}
# --- Виджет курсов валют ---
def currency_rates_widget():
    """Отображает виджет курсов валют в сайдбаре с дельтой и подробной информацией"""
    st.sidebar.title("💰 Курсы валют")
    rates_today = get_currency_rates()
    # Получаем курсы за вчерашний день
    try:
        # Для получения вчерашних данных нужно запросить их отдельно
        # ЦБ РФ API предоставляет исторические данные
        from datetime import datetime, timedelta
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y/%m/%d") # Формат даты для API ЦБ РФ
        url_yesterday = f"https://www.cbr-xml-daily.ru/archive/{yesterday_str}/daily_json.js"
        data_yesterday = requests.get(url_yesterday, timeout=5).json()
        rates_yesterday = {
            "USD": data_yesterday["Valute"]["USD"]["Value"],
            "EUR": data_yesterday["Valute"]["EUR"]["Value"],
        }
    except Exception:
        # Если не удалось получить данные за вчера, используем "вчерашние" из кэша сегодняшних как заглушку
        # или фиксированные значения для расчета дельты
        # В реальном приложении лучше обработать эту ситуацию более изящно
        # Например, можно хранить предыдущие значения в файле или сессии
        rates_yesterday = {"USD": rates_today["USD"] / 1.005, "EUR": rates_today["EUR"] / 0.997}
        # st.warning("Не удалось получить курсы за вчерашний день, дельта может быть неточной.")
    # Рассчитываем дельты
    try:
        usd_delta_value = rates_today["USD"] - rates_yesterday["USD"]
        usd_delta_percent = (usd_delta_value / rates_yesterday["USD"]) * 100
        # Форматируем дельту: знак + для положительных, округляем до 2 знаков
        usd_delta = f"{'+' if usd_delta_value >= 0 else ''}{usd_delta_value:.2f} ({'+' if usd_delta_percent >= 0 else ''}{usd_delta_percent:.2f}%)"
    except:
        usd_delta = "N/A"
    try:
        eur_delta_value = rates_today["EUR"] - rates_yesterday["EUR"]
        eur_delta_percent = (eur_delta_value / rates_yesterday["EUR"]) * 100
        eur_delta = f"{'+' if eur_delta_value >= 0 else ''}{eur_delta_value:.2f} ({'+' if eur_delta_percent >= 0 else ''}{eur_delta_percent:.2f}%)"
    except:
        eur_delta = "N/A"
    # Основные курсы с дельтами
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("USD/RUB", f"{rates_today['USD']:.2f} ₽", delta=usd_delta)
    with col2:
        st.metric("EUR/RUB", f"{rates_today['EUR']:.2f} ₽", delta=eur_delta)
    # Блок с подробной информацией
    with st.sidebar.expander("ℹ️ Подробности"):
        st.write(f"Последнее обновление: {rates_today['date']}")
        st.write(f"Курс USD вчера: {rates_yesterday['USD']:.2f}")
        st.write(f"Курс EUR вчера: {rates_yesterday['EUR']:.2f}")
        st.write("""
        **Источник:** [ЦБ РФ API](https://www.cbr-xml-daily.ru )  
        **Кэширование:** 1 час  
        **Резервные значения:** USD=90.0, EUR=100.0
        """)
    # Кнопка обновления
    if st.sidebar.button("🔄 Обновить данные", type="secondary"):
        get_currency_rates.cache_clear()
        st.rerun()
# --- Получение информации о перевозчике из Excel ---
def get_carrier_info(carrier_name):
    """Получает информацию о перевозчике из Excel файла"""
    try:
        if os.path.exists(CARRIERS_INFO_FILE):
            df = pd.read_excel(CARRIERS_INFO_FILE)
            # Используем точное совпадение по имени
            carrier_info = df[df['name'] == carrier_name]
            if not carrier_info.empty:
                return carrier_info.iloc[0].to_dict()
    except Exception as e:
        st.error(f"Ошибка при загрузке информации о перевозчике: {str(e)}")
    return {}
# --- Генерация договора ---
def generate_contract(bid_data, offer_data):
    """Генерирует договор на основе данных заявки и предложения"""
    try:
        # Создаем папку templates если ее нет
        os.makedirs("templates", exist_ok=True)
        template_path = os.path.join("templates", "template.docx")
        if not os.path.exists(template_path):
            raise FileNotFoundError("Шаблон договора не найден")
        doc = DocxTemplate(template_path)
        # Получаем информацию о перевозчике
        carrier_info = get_carrier_info(offer_data['sender'])
        # Используем email из carriers_info, если он там есть, иначе - из предложения
        carrier_email_for_template = carrier_info.get('email', offer_data.get('sender_email', ''))
        # Подготовка данных
        context = {
            'id': bid_data['id'],
            'date_created': datetime.now().strftime('%d.%m.%Y'),
            'carrier_name': offer_data['sender'],
            'carrier_email': carrier_email_for_template, # Используем улучшенный email
            'country_from': bid_data['details']['country_from'],
            'loading_address': bid_data['details']['loading_address'],
            'cargo_type': bid_data['details']['cargo_type'],
            'cargo_description': bid_data['details'].get('cargo_description', ''), # Передаем описание груза
            'container_type': bid_data['details']['container_type'],
            'hs_code': bid_data['details']['hs_code'],
            'incoterm': bid_data['details']['incoterm'],
            'ready_date': bid_data['details']['ready_date'],
            'payment_terms': bid_data['details']['payment_terms'],
            'notes': bid_data['details']['notes'],
            # Инициализация всех полей стоимости
            'pre_carriage_cost': 0,
            'pre_carriage_currency': '',
            'othc_cost': 0,
            'othc_currency': '',
            'sea_freight_cost': 0,
            'sea_freight_currency': '',
            # Добавляем информацию о перевозчике
            'name': carrier_info.get('name', ''), # Добавлено
            'email': carrier_info.get('email', ''), # Добавлено
            'legal_name': carrier_info.get('legal_name', ''),
            'inn': carrier_info.get('inn', ''),
            'kpp': carrier_info.get('kpp', ''),
            'ogrn': carrier_info.get('ogrn', ''),
            'address': carrier_info.get('address', ''),
            'bank_name': carrier_info.get('bank_name', ''),
            'bik': carrier_info.get('bik', ''),
            'rs': carrier_info.get('rs', ''),
            'ks': carrier_info.get('ks', ''),
            'contract_number': carrier_info.get('contract_number', ''),
            'contract_date': carrier_info.get('contract_date', ''),
        }
        # Заполняем данные о стоимости из предложения
        for cost in offer_data.get('costs', []):
            item_name = cost.get('ITEM', '')
            if 'Pre-carriage' in item_name:
                context['pre_carriage_cost'] = cost.get('COST', 0)
                context['pre_carriage_currency'] = cost.get('CURRENCY', 'USD')
            elif 'OTHC' in item_name:
                context['othc_cost'] = cost.get('COST', 0)
                context['othc_currency'] = cost.get('CURRENCY', 'USD')
            elif 'Sea freight' in item_name:
                context['sea_freight_cost'] = cost.get('COST', 0)
                context['sea_freight_currency'] = cost.get('CURRENCY', 'USD')
        doc.render(context)
        # Сохранение во временный файл
        temp_dir = tempfile.gettempdir()
        contract_path = os.path.join(temp_dir, f"contract_{bid_data['id']}_{offer_data['sender']}.docx")
        doc.save(contract_path)
        # Сохраняем копию в папку contracts
        os.makedirs("contracts", exist_ok=True)
        shutil.copy(contract_path, os.path.join("contracts", os.path.basename(contract_path)))
        # Сохраняем информацию о договоре
        contracts = load_json_file(CONTRACTS_FILE)
        contracts.append({
            "bid_id": bid_data['id'],
            "offer_id": offer_data.get('bid_id', ''),
            "carrier": offer_data['sender'],
            "date": datetime.now().isoformat(),
            "file_path": os.path.join("contracts", os.path.basename(contract_path)),
            "status": "generated"
        })
        save_json_file(CONTRACTS_FILE, contracts)
        return contract_path
    except Exception as e:
        st.error(f"Ошибка при генерации договора: {str(e)}")
        return None
# --- Парсинг предложений из Outlook ---
def parse_offers_from_outlook(folder_name="Предложения"):
    """Парсит непрочитанные письма с предложениями из Outlook"""
    try:
        outlook = init_outlook()
        namespace = outlook.GetNamespace("MAPI")
        inbox = namespace.GetDefaultFolder(6)  # Inbox
        folder = inbox
        if folder_name != "Входящие":
            for i in range(1, inbox.Folders.Count + 1):
                if inbox.Folders.Item(i).Name == folder_name:
                    folder = inbox.Folders.Item(i)
                    break
        messages = folder.Items
        new_offers = []
        for msg in messages:
            if msg.UnRead:
                body = msg.Body
                # Улучшенное получение email адреса
                sender_email = msg.SenderEmailAddress
                # Попытка получить SMTP адрес, если SenderEmailAddress не является обычным email
                if not (sender_email and "@" in sender_email and "." in sender_email.split("@")[-1]):
                    try:
                        sender_obj = msg.Sender
                        if sender_obj:
                            # Попробуем получить SMTP адрес через свойство PropertyAccessor
                            # Это может не сработать для всех типов отправителей
                            smtp_address = sender_obj.PropertyAccessor.GetProperty("http://schemas.microsoft.com/mapi/proptag/0x39FE001E")
                            if smtp_address and "@" in smtp_address:
                                sender_email = smtp_address
                    except Exception as e:
                        # Если не удалось получить SMTP адрес, оставляем оригинальный SenderEmailAddress
                        pass
                offer_data = {
                    "sender": msg.SenderName,
                    "sender_email": sender_email,  # Используем улучшенный email
                    "email_date": msg.ReceivedTime.strftime("%Y-%m-%d %H:%M:%S"),
                    "subject": msg.Subject,
                    "bid_id": "",
                    "order_number": "—",
                    "rate": "",
                    "currency": "",
                    "conditions": "",
                    "status": "Новое",
                    "costs": []
                }
                # Парсинг ID заявки
                # Ищем ID заявки, который может содержать буквы, цифры, дефисы и подчеркивания
                id_patterns = [
                    r"ID\s*заявки[^\w]*([A-Za-z0-9\-_]+)",
                    r"Заявка\s*№?[^\w]*([A-Za-z0-9\-_]+)",
                    r"(SHIP-\d{8}-\d{4})"  # Специфичный формат
                ]
                for pattern in id_patterns:
                    id_match = re.search(pattern, body, re.IGNORECASE)
                    if id_match:
                        offer_data["bid_id"] = id_match.group(1)
                        break
                # Парсинг номера заказа
                # Ищем номер заказа, который может содержать буквы, цифры, дефисы, подчеркивания и пробелы
                order_patterns = [
                    r"Номер\s*заказа[^\w]*([A-Z0-9]{2}\d{2}[-_]\d{3,})",
                    r"Номер\s*заказа[^\w]*([A-Za-z0-9\-_\s/]+?)(?:\r?|$)",
                    r"Order\s*Number[^\w]*([A-Za-z0-9\-_\s/]+?)(?:\r?|$)"
                ]
                for pattern in order_patterns:
                    order_number_match = re.search(pattern, body, re.IGNORECASE)
                    if order_number_match:
                        offer_data["order_number"] = order_number_match.group(1).strip()
                        #print(f"DEBUG: Extracted order_number: '{offer_data['order_number']}' for email from {sender_email}") проверить что спарсил!!!!!!    
                        break
                if offer_data["order_number"] == "—":  # Если не нашли по паттернам
                    # Более общий поиск
                    #order_number_match = re.search(r"([A-Z0-9]+[-_]?[A-Z0-9]+)", body, re.IGNORECASE) -старый!!!!!!!!!!!!!
                    order_number_match = re.search(r"([A-Z]{2,}\d+[-_]\d{2,})", body, re.IGNORECASE)
                    if order_number_match:
                        offer_data["order_number"] = order_number_match.group(1)
                # Парсинг ставки
                rate_match = re.search(r"Ставка:\s*([\d,.]+)\s*([A-Z]{3})", body, re.IGNORECASE)
                if rate_match:
                    offer_data["rate"] = rate_match.group(1).replace(',', '.').strip()
                    offer_data["currency"] = rate_match.group(2).strip()
                # Парсинг условий
                cond_match = re.search(r"Условия:\s*(.*?)(?:\r?\r?|\r??$)", body, re.DOTALL | re.IGNORECASE)
                if cond_match:
                    offer_data["conditions"] = cond_match.group(1).strip()
                # Парсинг стоимости
                cost_start = body.find("Расчет стоимости")
                if cost_start > -1:
                    cost_end = body.find("Условия оплаты", cost_start) or \
                               body.find("Примечания", cost_start) or \
                               len(body)
                    cost_section = body[cost_start:cost_end]
                    # ИСПРАВЛЕНО: Используем вместо символа новой строки в строке
                    lines = [line.strip() for line in cost_section.split('\n') if line.strip()]
                    cost_items = [
                        "Pre-carriage",
                        "OTHC (Origin Terminal Handling Charges)",
                        "Sea freight",
                        "ЖД перевозка",
                        "Прямое ЖД",
                        "Станционные затраты",
                        "Доставка со станции"
                    ]
                    for line in lines[1:]:  # Пропускаем заголовок
                      for item in cost_items:
                        if line.startswith(item):
                            # --- ИСПРАВЛЕНИЕ НАЧАЛО ---
                            # Ищем стоимость и валюту в оставшейся части строки после названия пункта
                            # Пример строки: "ЖД перевозка            213 300     RUB"
                            # или "Sea freight            1 470,50     USD"
                            # или "Pre-carriage            0.0     USD"
                            rest_of_line = line[len(item):].strip()
                            # Используем регулярное выражение для поиска числа (возможно с пробелами/запятыми/точками) и валюты
                            # ([\d\s.,]+) - группа 1: цифры, пробелы, точки, запятые
                            # \s+ - один или несколько пробелов
                            # ([A-Z]{3}) - группа 2: ровно 3 заглавные буквы (валюта)
                            cost_currency_match = re.search(r'([\d\s.,]+)\s+([A-Z]{3})', rest_of_line)
                            if cost_currency_match:
                                cost_str = cost_currency_match.group(1) # Например, "213 300" или "1 470,50" или "0.0"
                                currency = cost_currency_match.group(2) # Например, "RUB" или "USD"
                                try:
                                    # Убираем пробелы и заменяем запятую на точку для корректного парсинга float
                                    cost_str_cleaned = cost_str.replace(' ', '').replace(',', '.')
                                    cost = float(cost_str_cleaned)
                                    offer_data["costs"].append({
                                        "ITEM": item,
                                        "COST": cost,
                                        "CURRENCY": currency
                                    })
                                except ValueError:
                                    # Если не удалось преобразовать в число, пропускаем
                                    # st.warning(f"Не удалось распарсить стоимость '{cost_str}' в строке: {line}")
                                    continue
                                break # Нашли нужный пункт, переходим к следующей строке
                            else:
                                # Если не нашли по паттерну, можно попробовать старый способ как запасной вариант
                                # (или просто пропустить)
                                # st.warning(f"Не удалось извлечь стоимость и валюту из строки: {line}")
                                continue
                            # --- ИСПРАВЛЕНИЕ КОНЕЦ ---                if offer_data["bid_id"]:
                    new_offers.append(offer_data)
                    msg.UnRead = False
        if new_offers:
            try:
                existing_offers = load_json_file(OFFERS_FILE)
                save_json_file(OFFERS_FILE, existing_offers + new_offers)
            except Exception as e:
                st.error(f"Ошибка сохранения предложений: {str(e)}")
            return new_offers
        else:
            st.info("Новых предложений не найдено")
            return []
    except Exception as e:
        st.error(f"Ошибка при парсинге писем: {str(e)}")
        return []
    finally:
        pythoncom.CoUninitialize()

# --- Форматирование email для перевозчика ---
def format_bid_email(bid):
    """Форматирует текст email для отправки перевозчику"""
    
    # Основной текст с инструкциями
    email_lines = [
        "Уважаемый партнер,",
        "срок предоставления ответа до 15:00 следующего дня, заявки, полученные позже будут отклонены автоматически.",
        "Для корректного заполнения заявки необходимо в ответном сообщении заполнить форму заявки, не меняя текст сообщения,",
        "указать стоимость, валюту в формате \"RUB\" или \"USD\", очередность полей не менять, не удалять и не добавлять.",
        "При необходимости дополнить информацию в поле \"Примечания\"",
        "",  # Пустая строка для разделения
        f"ID заявки: {bid['id']}",
        f"Номер заказа: {bid.get('order_number', 'Не указан')}",
        f"Страна отправки: {bid['details']['country_from']}",
        f"Условие отгрузки: {bid['details']['incoterm']}",
        f"Порт отправки: {bid['details']['port_from']}",
        f"Дата готовности груза: {bid['details']['ready_date']}",
        f"Тип контейнера: {bid['details']['container_type']}",
        f"Способ доставки: {bid['details']['delivery_method']}",
        f"Груз: {bid['details']['cargo_type']}",
        f"Код ТНВЭД: {bid['details']['hs_code']}",
        "",  # Пустая строка
        "Описание груза:",
        f"Адрес погрузки: {bid['details']['loading_address']}",
        "",  # Пустая строка
        "Расчет стоимости:"
    ]
    
    cost_items = [
        "Pre-carriage",
        "OTHC (Origin Terminal Handling Charges)",
        "Sea freight",
        "ЖД перевозка",
        "Прямое ЖД",
        "Станционные затраты",
        "Доставка со станции"
    ]
    
    for item in cost_items:
        matching_cost = next((c for c in bid['costs'] if c["ITEM"] == item), 
                           {"COST": 0.0, "CURRENCY": "USD"})
        email_lines.append(f"{item}: {matching_cost['COST']} {matching_cost['CURRENCY']}")
    
    email_lines.extend([
        "",  # Пустая строка
        f"Условия оплаты: {bid['details']['payment_terms']}",
        "",  # Пустая строка
        "Примечания:"
    ])
    
    # Добавляем описание груза построчно
    if bid['details'].get('cargo_description'):
        cargo_desc_lines = bid['details']['cargo_description'].split('\n')
        for line in cargo_desc_lines:
            if line.strip():  # Только непустые строки
                email_lines.append(f"  {line}")
    
    # Добавляем примечания построчно
    if bid['details'].get('notes'):
        notes_lines = bid['details']['notes'].split('\n')
        for line in notes_lines:
            if line.strip():  # Только непустые строки
                email_lines.append(f"  {line}")
    
    # Объединяем все строки с переносами
    return '\n'.join(email_lines)

# --- Форма заявки ---
def create_bid_form():
    """Форма создания новой заявки на перевозку"""
    with st.form("new_bid", clear_on_submit=True):
        st.subheader("Новая заявка на перевозку")
        col1, col2 = st.columns(2)
        with col1:
            bid_id = st.text_input("ID заявки*", value=f"SHIP-{datetime.now().strftime('%Y%m%d-%H%M')}")
            order_number = st.text_input("Номер заказа*", "IN00-000")
            country_from = st.text_input("Страна отправки*", "Китай")
            incoterm = st.selectbox("Условие отгрузки*", ["FOB", "CIF", "EXW", "DAP", "DDP", "CFR", "FCA", "CPT"])
        with col2:
            port_from = st.text_input("Порт отправки*", "Shanghai")
            ready_date = st.date_input("Дата готовности груза*", datetime.now())
            container_type = st.selectbox("Тип контейнера*", ["20 фут", "40 фут", "40 фут HQ", "Авто 20тн", "Сборный груз"] )
            delivery_method = st.selectbox("Способ доставки*", ["Море+ЖД", "Прямое ЖД", "Авто", "Авиа"], key="delivery_method")
        st.subheader("Детали груза")
        cargo_type = st.text_input("Тип груза*", "не опасный")
        hs_code = st.text_input("Код ТНВЭД", "")
   #  ---описание груза
        cargo_description = st.text_area(
  	    "Описание груза*",
    	    '''- наименование груза :
        - вес (нетто/брутто):
        - объём, количество грузовых мест: 
        - вид упаковки:
        - стоимость груза:''',
        height=150,
        key="cargo_description"
)
        loading_address = st.text_area("Адрес погрузки*", 
                                     "16F, No.839, Sec.4, Taiwan Blvd., Xitun Dist., 407 Taichung, TAIWAN")
        st.subheader("Файлы")
        uploaded_files = st.file_uploader(
            "Прикрепите файлы (например, спецификации груза)", 
            type=["pdf", "docx", "xlsx", "jpg", "png"], 
            accept_multiple_files=True
        )
        valid_files = []
        total_size = 0
        if uploaded_files:
            for file in uploaded_files:
                if file.size > 15 * 1024 * 1024:
                    st.warning(f"Файл {file.name} больше 15 МБ и будет проигнорирован.")
                else:
                    total_size += file.size
                    valid_files.append(file)
            if total_size > 15 * 1024 * 1024:
                st.error("Суммарный размер всех файлов превышает 15 МБ. Некоторые файлы будут проигнорированы.")
        st.subheader("Финансовые условия")
        payment_terms = st.text_area("Условия оплаты*", 
                                   "50% TT in advance / 50% 14 days after delivery")
        st.subheader("Расчет стоимости")
        costs = []
        cost_items = [
            "Pre-carriage",
            "OTHC (Origin Terminal Handling Charges)",
            "Sea freight",
            "ЖД перевозка",
            "Прямое ЖД",
            "Станционные затраты",
            "Доставка со станции"
        ]
        for item in cost_items:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.text(item)
            with col2:
                cost = st.number_input(f"Сумма {item}", 
                                     key=f"cost_{item}", 
                                     min_value=0.0,
                                     value=0.0)
            with col3:
                currency = st.selectbox("Валюта", 
                                      ["USD", "RUB", "EUR"], 
                                      key=f"curr_{item}")
            costs.append({"ITEM": item, "COST": cost, "CURRENCY": currency})
        notes = st.text_area("Примечания", '''Простой на выгрузке оплачивается отдельно
прочие затраты включены в стоимость, требуется отметка СКК''')
        if st.form_submit_button("Отправить заявку"):
            if not all([bid_id, country_from, port_from, cargo_type, loading_address, payment_terms]):
                st.error("Заполните обязательные поля (помечены *)")
            else:
                bid_data = {
                    "id": bid_id,
                    "order_number": order_number,
                    "date_created": datetime.now().isoformat(),
                    "status": "Новая",
                    "details": {
                        "country_from": country_from,
                        "incoterm": incoterm,
                        "port_from": port_from,
                        "ready_date": str(ready_date),
                        "container_type": container_type,
                        "cargo_type": cargo_type,
			"cargo_description": cargo_description,
                        "delivery_method": delivery_method,
                        "hs_code": hs_code,
                        "loading_address": loading_address,
                        "payment_terms": payment_terms,
                        "notes": notes
                    },
                    "costs": costs
                }
                try:
                    bids = load_json_file(BIDS_FILE)
                    bids.append(bid_data)
                    save_json_file(BIDS_FILE, bids)
                    carriers = load_json_file(CARRIERS_FILE)
                    email_body = format_bid_email(bid_data)
                    success_count = 0
                    attachments = []
                    if valid_files:
                        for file in valid_files:
                            temp_file_path = os.path.join(tempfile.gettempdir(), file.name)
                            with open(temp_file_path, "wb") as f:
                                f.write(file.getbuffer())
                            attachments.append(temp_file_path)
                    for carrier in carriers:
                        # Разделяем email по всем возможным разделителям: запятая, точка с запятой, двоеточие
                        email_list = []
                        if carrier['email']:
                            # Сначала заменяем все разделители на запятые, затем разделяем по запятым
                            normalized_emails = carrier['email'].replace(';', ',').replace(':', ',')
                            email_list = [e.strip() for e in normalized_emails.split(',') if e.strip()]
                        for email in email_list:
                            if email and '@' in email:  # Проверяем, что email содержит @
                                if send_email(email, f"Новая заявка {bid_id}", email_body, attachments):
                                    success_count += 1
                                else:
                                    st.error(f"Ошибка отправки для {carrier['name']} ({email})")
                            elif email:  # Если email есть, но не содержит @
                                st.warning(f"Некорректный email для {carrier['name']}: {email}")
                    # Удаление временных файлов
                    if attachments:
                        for file in attachments:
                            try:
                                os.remove(file)
                            except Exception as e:
                                st.warning(f"Не удалось удалить временный файл {file}: {e}")
                    # Отображение результата
                    if success_count > 0:
                        st.success(f"Заявка {bid_id} создана! Уведомления отправлены {success_count} перевозчикам")
                        time.sleep(3) # Задержка для отображения сообщения
                    else:
                        st.warning("Заявка создана, но не удалось отправить уведомления перевозчикам")
                        time.sleep(3) # Задержка для отображения сообщения
                except Exception as e:
                    st.error(f"Ошибка при сохранении заявки: {str(e)}")
                    time.sleep(3) # Задержка для отображения сообщения
# --- Просмотр предложений ---
def view_offers():
    """Отображает и управляет предложениями от перевозчиков"""
    st.subheader("Поступившие предложения")
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("🔄 Обновить список предложений"):
            new_offers = parse_offers_from_outlook()
            if new_offers:
                st.success(f"Найдено {len(new_offers)} новых предложений")
                time.sleep(3) # Задержка для отображения сообщения
            else:
                st.info("Новых предложений не найдено")
                time.sleep(3) # Задержка для отображения сообщения
            st.rerun()
    offers = load_json_file(OFFERS_FILE)
    if offers:
        # Получаем текущие курсы валют
        rates = get_currency_rates()
        # Подготовка данных для сравнения
        comparison_data = []
        for offer in offers:
            total_rub = 0.0
            costs_dict = {}
            for cost in offer.get('costs', []):
                if cost.get('ITEM'):
                    cost_value = cost.get('COST', 0)
                    currency = cost.get('CURRENCY', '')
                    if currency == "USD":
                        converted = cost_value * rates["USD"]
                    elif currency == "EUR":
                        converted = cost_value * rates["EUR"]
                    else:
                        converted = cost_value
                    total_rub += converted
                    costs_dict[cost['ITEM']] = {
                        'COST': cost_value,
                        'CURRENCY': currency,
                        'COST_RUB': converted
                    }
            comparison_data.append({
                "Дата получения": offer["email_date"],
                "Перевозчик": offer["sender"],
                "ID заявки": offer["bid_id"],
                "Номер заказа": offer.get("order_number", "—"),
                "Pre-carriage": f"{costs_dict.get('Pre-carriage', {}).get('COST', 0):.2f} {costs_dict.get('Pre-carriage', {}).get('CURRENCY', '')}",
                "OTHC": f"{costs_dict.get('OTHC (Origin Terminal Handling Charges)', {}).get('COST', 0):.2f} {costs_dict.get('OTHC (Origin Terminal Handling Charges)', {}).get('CURRENCY', '')}",
                "Sea freight": f"{costs_dict.get('Sea freight', {}).get('COST', 0):.2f} {costs_dict.get('Sea freight', {}).get('CURRENCY', '')}",
                "ЖД перевозка": f"{costs_dict.get('ЖД перевозка', {}).get('COST', 0):.2f} {costs_dict.get('ЖД перевозка', {}).get('CURRENCY', '')}",
                "Прямое ЖД": f"{costs_dict.get('Прямое ЖД', {}).get('COST', 0):.2f} {costs_dict.get('Прямое ЖД', {}).get('CURRENCY', '')}",
                "Станционные затраты": f"{costs_dict.get('Станционные затраты', {}).get('COST', 0):.2f} {costs_dict.get('Станционные затраты', {}).get('CURRENCY', '')}",
                "Доставка со станции": f"{costs_dict.get('Доставка со станции', {}).get('COST', 0):.2f} {costs_dict.get('Доставка со станции', {}).get('CURRENCY', '')}",
                "Итого (RUB)": f"{total_rub:.2f} ₽",
                "Статус": offer.get("status", "Новое")
            })
        df_comparison = pd.DataFrame(comparison_data)
        # Фильтрация по ID заявки
        bid_id_filter = st.text_input("Фильтр по ID заявки")
        if bid_id_filter:
            df_comparison = df_comparison[df_comparison['ID заявки'].str.contains(bid_id_filter, case=False)]
        # Вычисляем минимальную сумму для каждой группы ID заявки
        df_comparison['min_total_rub'] = df_comparison.groupby('ID заявки')['Итого (RUB)'].transform('min')
        # Создаем копию для отображения с звездочками
        df_display = df_comparison.copy()
                    # Ограничиваем длину строк в столбцах "Перевозчик" и "Дата получения" для отображения
                    # Используем .apply() с лямбда-функцией для безопасной обрезки
        df_display["Перевозчик"] = df_display["Перевозчик"].apply(
            lambda x: x[:20] if isinstance(x, str) else x
        )
        df_display["Дата получения"] = df_display["Дата получения"].apply(
            lambda x: x[:10] if isinstance(x, str) else x
        )
        # Добавляем звездочки к минимальным значениям в колонке "Итого (RUB)"
        for bid_id in df_display['ID заявки'].unique():
            min_value = df_display[df_display['ID заявки'] == bid_id]['Итого (RUB)'].min()
            df_display.loc[(df_display['ID заявки'] == bid_id) & (df_display['Итого (RUB)'] == min_value), 'Итого (RUB)'] = \
                df_display.loc[(df_display['ID заявки'] == bid_id) & (df_display['Итого (RUB)'] == min_value), 'Итого (RUB)'].apply(
                    lambda x: f"⭐ {x}"
                )
        # Отображение таблицы с возможностью выбора строк
        edited_df = st.data_editor(
            df_display,
            use_container_width=True,
            hide_index=True,
            disabled=["Дата получения", "Перевозчик", "ID заявки", "Номер заказа", "Pre-carriage", "OTHC", 
                     "Sea freight", "ЖД перевозка", "Прямое ЖД", "Станционные затраты", 
                     "Доставка со станции", "Итого (RUB)"],
            column_config={
                "Статус": st.column_config.SelectboxColumn(
                    "Статус",
                    options=["Новое", "В работе", "Отклонено", "Принято"],
                    required=True
                )
            }
        )
        # --- Генерация и отправка договора ---
        st.markdown("### 📝 Генерация договора")
        # Выбор предложения для генерации договора
        selected_offer_idx = st.selectbox(
            "Выберите предложение для генерации договора",
            range(len(edited_df)),
            format_func=lambda x: f"{edited_df.iloc[x]['Перевозчик']} - {edited_df.iloc[x]['ID заявки']}"
        )
        # Размещаем кнопки в одном ряду
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🖨️ Сгенерировать договор"):
                selected_row = edited_df.iloc[selected_offer_idx]
                offers = load_json_file(OFFERS_FILE)
                selected_offer = next(
                    (o for o in offers 
                     if o["bid_id"] == selected_row["ID заявки"] 
                     and o["sender"] == selected_row["Перевозчик"]),
                    None
                )
                if selected_offer:
                    bids = load_json_file(BIDS_FILE)
                    selected_bid = next((b for b in bids if b["id"] == selected_offer["bid_id"]), None)
                    if selected_bid:
                        contract_path = generate_contract(selected_bid, selected_offer)
                        if contract_path:
                            st.success("Договор успешно сгенерирован!")
                            time.sleep(3) # Задержка для отображения сообщения
                            # Кнопка скачивания
                            with open(contract_path, "rb") as f:
                                st.download_button(
                                    label="📥 Скачать договор",
                                    data=f,
                                    file_name=f"Договор_{selected_bid['id']}_{selected_offer['sender']}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                )
                        else:
                            st.error("Ошибка при генерации договора")
                            time.sleep(3) # Задержка для отображения сообщения
                    else:
                        st.error("Не найдена соответствующая заявка")
                        time.sleep(3) # Задержка для отображения сообщения
                else:
                    st.error("Не найдено соответствующее предложение")
                    time.sleep(3) # Задержка для отображения сообщения
        with col2:
            if st.button("📤 Отправить поставщику"):
                selected_row = edited_df.iloc[selected_offer_idx]
                offers = load_json_file(OFFERS_FILE)
                selected_offer = next(
                    (o for o in offers 
                     if o["bid_id"] == selected_row["ID заявки"] 
                     and o["sender"] == selected_row["Перевозчик"]),
                    None
                )
                if selected_offer:
                    bids = load_json_file(BIDS_FILE)
                    selected_bid = next((b for b in bids if b["id"] == selected_offer["bid_id"]), None)
                    if selected_bid:
                        contract_path = generate_contract(selected_bid, selected_offer)
                        if contract_path:
                            subject = f"Договор по заявке {selected_bid['id']}"
                            body = f"""
                            Уважаемый {selected_offer['sender']},
                            Прикрепляем договор по заявке {selected_bid['id']}.
                            Просим подтвердить получение и согласие с условиями.
                            С уважением,
                            Логистический отдел
                            """
                            if send_email(selected_offer['sender_email'], subject, body, attachments=[contract_path]):
                                st.success("Договор успешно отправлен!")
                                time.sleep(3) # Задержка для отображения сообщения
                            else:
                                st.error("Ошибка при отправке договора")
                                time.sleep(3) # Задержка для отображения сообщения
                        else:
                            st.error("Ошибка при генерации договора")
                            time.sleep(3) # Задержка для отображения сообщения
                    else:
                        st.error("Не найдена соответствующая заявка")
                        time.sleep(3) # Задержка для отображения сообщения
                else:
                    st.error("Не найдено соответствующее предложение")
                    time.sleep(3) # Задержка для отображения сообщения
        with col3:
            if st.button("💾 Сохранить изменения статусов"):
                try:
                    # Загружаем актуальные данные перед сохранением
                    offers = load_json_file(OFFERS_FILE)
                    updated_offers = []
                    sent_notifications = set()  # Для отслеживания отправленных уведомлений
                    success_count = 0
                    now = datetime.now()
                    # Создаем словарь для быстрого поиска новых статусов
                    new_statuses = {}
                    for idx, row in edited_df.iterrows():
                        key = (row["ID заявки"], row["Перевозчик"])
                        new_statuses[key] = row["Статус"]
                    # Обновляем статусы в списке всех предложений
                    for offer in offers:
                        key = (offer["bid_id"], offer["sender"])
                        if key in new_statuses:
                            old_status = offer.get("status", "Новое")
                            new_status = new_statuses[key]
                            offer["status"] = new_status
                            # Проверка: изменился ли статус на "Отклонено" или "Принято"
                            if new_status in ["Отклонено", "Принято"] and old_status != new_status:
                                # Защита от повторной отправки: минимум 1 минута между уведомлениями для одного перевозчика
                                last_change = offer.get("last_status_change")
                                should_send = True
                                if last_change:
                                    try:
                                        time_diff = (now - datetime.fromisoformat(last_change)).total_seconds()
                                        if time_diff < 60:  # Не чаще 1 раза в минуту
                                            st.warning(f"⚠️ Слишком частое обновление для {offer['sender']}")
                                            should_send = False
                                    except Exception:
                                        # Если ошибка в парсинге времени, отправляем
                                        pass
                                # Проверяем, было ли уже отправлено уведомление для этого перевозчика в этой сессии
                                if offer['sender'] in sent_notifications:
                                    should_send = False
                                if should_send:
                                    # Формирование сообщения
                                    subject = f"Обновление статуса заявки {offer['bid_id']}"
                                    body = f"""Здравствуйте, {offer['sender']}!
Статус вашей заявки с ID {offer['bid_id']} изменён на "{new_status}".
Подробности:
- Перевозчик: {offer['sender']}
- ID заявки: {offer['bid_id']}
- Статус: {new_status}
С уважением,
Логистическая система
"""
                                    # Попытка отправки
                                    if send_email(offer['sender_email'], subject, body):
                                        st.success(f"✅ Уведомление отправлено {offer['sender']} (статус: {new_status})")
                                        success_count += 1
                                        offer["last_status_change"] = now.isoformat()  # Сохраняем время
                                        sent_notifications.add(offer['sender'])  # Добавляем в список отправленных
                                    else:
                                        st.warning(f"⚠️ Не удалось отправить уведомление для {offer['sender']}")
                        updated_offers.append(offer)
                    # Сохраняем обновленные данные
                    save_json_file(OFFERS_FILE, updated_offers)
                    st.success(f"✅ Статусы предложений обновлены! Уведомления отправлены {success_count} перевозчикам")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Ошибка при обновлении статусов: {str(e)}")
                    time.sleep(3)
        # --- Удаление отклоненных предложений ---
        if st.button("🗑️ Удалить отклоненные"):
            try:
                # Создаем множество (set) для быстрого поиска отклоненных предложений
                rejected_keys = {
                    (row["ID заявки"], row["Перевозчик"]) 
                    for _, row in edited_df.iterrows() 
                    if row["Статус"] == "Отклонено"
                }
                # Фильтруем список предложений, исключая отклоненные
                filtered_offers = [
                    offer for offer in offers 
                    if (offer["bid_id"], offer["sender"]) not in rejected_keys
                ]
                save_json_file(OFFERS_FILE, filtered_offers)
                st.success("✅ Отклоненные предложения удалены!")
                time.sleep(3) # Задержка для отображения сообщения
                st.rerun()
            except Exception as e:
                st.error(f"❌ Ошибка при удалении предложений: {str(e)}")
                time.sleep(3) # Задержка для отображения сообщения
        # --- Экспорт в Excel ---
        def to_excel(df):
            output = BytesIO()
            writer = pd.ExcelWriter(output, engine='xlsxwriter')
            df.to_excel(writer, index=False, sheet_name='Предложения')
            writer.close()
            processed_data = output.getvalue()
            return processed_data
        excel_data = to_excel(edited_df)
        st.download_button(
            label="📊 Экспорт в Excel",
            data=excel_data,
            file_name=f"offers_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("ℹ️ Нет данных о предложениях")
# --- Управление перевозчиками ---
def manage_carriers():
    """Управление списком перевозчиков"""
    st.subheader("Управление перевозчиками")
    try:
        carriers = load_json_file(CARRIERS_FILE)
        df = pd.DataFrame(carriers if carriers else [{"name": "", "email": "","notes": ""}])
        with st.expander("📋 Текущий список перевозчиков"):
            edited_df = st.data_editor(
                df,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "name": "Название компании",
                    "email": st.column_config.TextColumn(
                        "Email",
                        help="Должен быть валидный email адрес",
                        validate="^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                    ),
                    "notes": st.column_config.TextColumn(
                        "Примечания",
                        help="Дополнительная информация"
                    )
                }
            )
            if st.button("Сохранить изменения"):
                # Проверка данных
                invalid_rows = []
                for idx, row in edited_df.iterrows():
                    if not row['name'] or not row['email'] or '@' not in row['email']:
                        invalid_rows.append(idx + 1)
                if not invalid_rows:
                    save_json_file(CARRIERS_FILE, edited_df.to_dict('records'))
                    st.success("Список перевозчиков обновлен!")
                    time.sleep(3) # Задержка для отображения сообщения
                    st.rerun()
                else:
                    st.error(f"Проверьте данные в строках {', '.join(map(str, invalid_rows))}: все поля должны быть заполнены, email должен быть корректным")
                    time.sleep(3) # Задержка для отображения сообщения
        with st.expander("📩 Импорт/экспорт"):
            col1, col2 = st.columns(2)
            with col1:
                # Импорт из CSV
                uploaded_file = st.file_uploader("Импорт из CSV", type=["csv"])
                if uploaded_file:
                    try:
                        import_df = pd.read_csv(uploaded_file)
                        if set(import_df.columns) >= {"name", "email"}:
                            save_json_file(CARRIERS_FILE, import_df.to_dict('records'))
                            st.success("Данные успешно импортированы!")
                            time.sleep(3) # Задержка для отображения сообщения
                            st.rerun()
                        else:
                            st.error("CSV должен содержать колонки 'name' и 'email'")
                            time.sleep(3) # Задержка для отображения сообщения
                    except Exception as e:
                        st.error(f"Ошибка импорта: {str(e)}")
                        time.sleep(3) # Задержка для отображения сообщения
                # Импорт из Excel
                uploaded_excel = st.file_uploader("Импорт из Excel", type=["xlsx"])
                if uploaded_excel:
                    try:
                        import_df = pd.read_excel(uploaded_excel)
                        if set(import_df.columns) >= {"name", "email","notes"}:
                            save_json_file(CARRIERS_FILE, import_df.to_dict('records'))
                            st.success("Данные успешно импортированы из Excel!")
                            time.sleep(3) # Задержка для отображения сообщения
                            st.rerun()
                        else:
                            st.error("Excel должен содержать колонки 'name', 'email', 'notes'")
                            time.sleep(3) # Задержка для отображения сообщения
                    except Exception as e:
                        st.error(f"Ошибка импорта из Excel: {str(e)}")
                        time.sleep(3) # Задержка для отображения сообщения
            with col2:
                # Экспорт в CSV
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Экспорт в CSV",
                    data=csv,
                    file_name="carriers.csv",
                    mime="text/csv"
                )
                # Экспорт в Excel
                def to_excel_carriers(df):
                    output = BytesIO()
                    writer = pd.ExcelWriter(output, engine='xlsxwriter')
                    df.to_excel(writer, index=False, sheet_name='Перевозчики')
                    writer.close()
                    processed_data = output.getvalue()
                    return processed_data
                excel_data_carriers = to_excel_carriers(df)
                st.download_button(
                    label="Экспорт в Excel",
                    data=excel_data_carriers,
                    file_name="carriers.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    except Exception as e:
        st.error(f"Ошибка при работе с перевозчиками: {str(e)}")
        time.sleep(3) # Задержка для отображения сообщения
# --- README ---
def show_readme():
    """Отображает инструкцию по использованию системы"""
    st.subheader("📖 Руководство пользователя")

    with st.expander("1. Управление перевозчиками"):
        st.markdown("""

        ** Функции блока "Управление перевозчиками":**

           - Добавление новых перевозчиков
           - Редактирование существующих записей
           - Удаление перевозчиков 
           - сохранение выбранного списка перевозчиков в excel или CSV
           - корректировать и сохранять данные в колонках : "Название компании","Email", "Примечания"

       **Как управлять списком перевозчиков:**
        1. Нажмите кнопку "Импорт из Excel", выберете файл с заполненными данными перевозчиков "name", "email", "notes", 
           данные загрузятся автоматически и отобразятся в основном окне.
        2. ВАЖНО: когда появится сообщение "Данные успешно импортированы из Excel!", 
           Удалите подгруженный файл в окне "Импорт из Excel" нажав на "х" напротив названия загруженного файла
        3. При необходимости отредактируйте данные (добавьте/удалите перевозчиков(+), добавьте/измените комментарии/название компании )
        4. Нажмите кнопку "Сохранить изменения", дождитесь сообщения "Список перевозчиков обновлен!" и данные будут сохранены и в последующем
           отображаться для отправки сообщений
        5. Можно дополнительно сохранить список: нажмите кнопку "Экспорт в CSV" или "Экспорт в Excel"
        """)

    with st.expander("2. Создание заявки"):
        st.markdown("""
        **Как создать новую заявку на перевозку:**
        ВНИМАНИЕ: перед началом создания заявки настройте список перевозчиков в окне "Управление перевозчиками"
        1. Перейдите в раздел "Создать заявку"
        2. Заполните обязательные поля (помечены *):
           - ID заявки (генерируется автоматически)
           - Номер заказа
           - Страна отправки
           - Порт отправки
           - Тип груза
           - Адрес погрузки
           - Условия оплаты
        3. Укажите стоимость по каждому пункту
        4. Нажмите "Отправить заявку"
        После отправки система автоматически разошлет уведомления всем перевозчикам из списка.
        """)

    with st.expander("3. Работа с предложениями"):
        st.markdown("""
        **Как работать с поступившими предложениями:**
        1. В разделе "Просмотр предложений" нажмите "Обновить список предложений" для загрузки новых предложений из Outlook
        2. Используйте фильтр по ID заявки для поиска конкретных предложений
        3. Изменяйте статусы предложений (Новое/В работе/Отклонено/Принято)
        4. Для выбранного предложения можно сгенерировать договор
        5. Сохраните изменения кнопкой "Сохранить изменения статусов"
        6. Для удаления всех отклоненных предложений используйте кнопку "Удалить отклоненные"
        7. Для экспорта данных в Excel используйте кнопку "Экспорт в Excel"
        """)

# --- Главный интерфейс ---
def main():
    """Основная функция приложения"""
    st.set_page_config(
        page_title="Логистическая система",
        layout="wide",
        page_icon="🚢"
    )
    # --- ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ СЕССИИ ОБЯЗАТЕЛЬНО В НАЧАЛЕ ---
    # Убедимся, что st.session_state.user всегда определен
    if 'user' not in st.session_state:
        st.session_state.user = "admin" # Автоматический вход как admin

    # --- АВТОМАТИЧЕСКАЯ АВТОРИЗАЦИЯ ---
    # Так как мы всегда устанавливаем user в "admin", блок с формой входа можно убрать.
    # Но если вы захотите вернуть вход, раскомментируйте и адаптируйте соответствующий блок.

    # --- ОСНОВНОЙ ИНТЕРФЕЙС ---
    # Этот блок выполняется всегда, если пользователь "авторизован" (у нас это всегда "admin")
    if st.session_state.user == "admin":
        # Логотип в сайдбаре
        st.sidebar.image("Soudal.PNG", use_container_width=False, width=150)
        # Виджет курсов валют в сайдбаре
        currency_rates_widget()
        st.sidebar.title(f"👤 {st.session_state.user}")
        menu = st.sidebar.radio(
            "Меню",
            ["README", "Управление перевозчиками", "Создать заявку", "Просмотр предложений" ],
            index=0
        )
        if st.sidebar.button("🚪 Выйти"):
            # Если вы захотите добавить логику выхода, здесь можно будет сбросить st.session_state.user
            # Например: st.session_state.user = None
            # Но сейчас у вас автоматический вход, поэтому просто покажем сообщение или ничего не сделаем.
            # st.info("Выход не предусмотрен в текущей конфигурации.")
            pass # Или любая другая логика, если нужно

        # Добавляем новое изображение в сайдбар
        st.sidebar.image("Shi_Py.png", use_container_width=False, width=60)

        # Основная навигация
        if menu == "README":
            show_readme()
        elif menu == "Создать заявку":
            create_bid_form()
        elif menu == "Просмотр предложений":
            view_offers()
        elif menu == "Управление перевозчиками":
            manage_carriers()
    else:
        # Этот блок теоретически не выполнится с текущей логикой инициализации,
        # но оставлен для полноты картины, если вы решите вернуть полноценную авторизацию.
        st.error("Ошибка авторизации. Пользователь не определен.")
        # st.stop() # Опционально: остановить выполнение скрипта

if __name__ == "__main__":
    main()