"""
    Code was writen by Oleg Volkov https://github.com/oavolkov

"""
import time
import yobit
from yobit_bot_config import *


# --------------------------------  Дополнительные функции  --------------------------------
class ScriptError(Exception):
    """
    Класс для обработки исключений функций

    """
    pass


class ScriptQuitCondition(Exception):
    """
    Класс для обработки исключений функций

    """
    pass


def get_currencies(curr_pairs):
    """
    Получение списка валют из переданных валютных пар.

    :param curr_pairs: Список валютных пар
    :type curr_pairs: list

    :return: Список валют
    :rtype : list

    """
    currs = list()
    for c_pair in curr_pairs:
        base_c, quote_c = c_pair.split('_')
        currs.append(base_c)
        currs.append(quote_c)

    return currs


def get_balances(stock_api, currs):
    """
    Получение балансов каждой из валют в паре из информации с биржи.

    :param stock_api: Объект API биржи
    :type stock_api: yobit.YobitAPI

    :param currs: Список валют, по которым нужно получить баланс
    :type currs: list

    :return: Балансы для указанных валют
    :rtype : dict

    """
    user_info = stock_api.get_info()
    ret_data = {}

    for curr in currs:
        try:
            ret_data[curr] = float(user_info['return']['funds'][curr.lower()])
        except KeyError:  # Если нулевой баланс, он отсутствует совсем. Обходим этот факт
            ret_data[curr] = 0.0

    return ret_data


def get_history(stock_api, curr_pair, count=1, order='ASC'):
    """
    Получение истории торгов с биржи.

    :param stock_api: Объект API биржи
    :type stock_api: yobit.YobitAPI

    :param curr_pair: Пара валют, например 'LTC_BTC'
    :type curr_pair: str

    :param count: Количество строк в возвращаемой истории (по-умолчанию = 1)
    :type count: int

    :param order: Как сортировать результат ('ASC' - по-возрастанию, 'DESC' - по-убыванию)
    :type order: str

    :return: Ответ от YoBit Public API в формате JSON
    :rtype : dict

    """
    hist_data = stock_api.trade_history(curr_pair, count=count, order=order)
    try:
        ret_data = {}
        for item in hist_data['return']:
            ret_data = hist_data['return'][item]

    except KeyError:    # Такого значения нет, история торгов пуста
        ret_data = {}

    return ret_data


def get_pairs_info(stock_api):
    """
    Получение истории торгов с биржи.

    :param stock_api: Объект API биржи
    :type stock_api: yobit.YobitAPI

    :return: Ответ от YoBit Public API в формате JSON
    :rtype : dict

    """
    pairs_data = stock_api.info()['pairs']
    return pairs_data


def get_opened_orders(stock_api, curr_pair):
    """
    Получение списка активных ордеров с биржи.

    :param stock_api: Объект API биржи
    :type stock_api: yobit.YobitAPI

    :param curr_pair: Пара валют, например 'LTC_BTC'
    :type curr_pair: str

    :return: Ответ от YoBit Public API в формате JSON
    :rtype : list

    """
    opened_orders = list()
    try:
        o_data = stock_api.active_orders(curr_pair)['return']
        for order in o_data:
            o = o_data[order]
            o['order_id'] = order
            opened_orders.append(o)

    except KeyError:    # Такого значения нет, Список ордеров пуст
        pass

    return opened_orders


def get_depth_of_market(stock_api, curr_pair, offers_limit=1):
    """
    Получаем информацию по предложениям из "стакана" (Depth_of_Market, DOM).

    :param stock_api: Объект API биржи
    :type stock_api: yobit.YobitAPI

    :param curr_pair: Пара валют, например 'LTC_BTC'.
    :type curr_pair: str

    :param offers_limit: Количество строк в возвращаемой истории (по-умолчанию = 1)
    :type offers_limit: int

    :return: Ответ от YoBit Public API в формате JSONю "Стакан" по указанной паре
    :rtype : dict

    """
    curr_pair = curr_pair.lower()
    offers = stock_api.depth(curr_pair, offers_limit)[curr_pair]
    return offers


def depth_first_ask_rate(d_o_m_data):
    """
    Получаем курс верхнего предложения на продажу из "стакана" (Depth_of_Market, DOM).

    :param d_o_m_data: Данные "стакана" ( результат вызова get_depth_of_market() )
    :type d_o_m_data: dict

    :return: курс верхнего предложения на продажу
    :rtype : float

    """
    return d_o_m_data['asks'][0][0]


def depth_first_ask_amount(d_o_m_data):
    """
    Получаем количество верхнего предложения на продажу из "стакана" (Depth_of_Market, DOM).

    :param d_o_m_data: Данные "стакана" ( результат вызова get_depth_of_market() )
    :type d_o_m_data: dict

    :return: количество верхнего предложения на продажу
    :rtype : float

    """
    return d_o_m_data['asks'][0][1]


def depth_first_bid_rate(d_o_m_data):
    """
    Получаем курс верхнего предложения на покупку из "стакана" (Depth_of_Market, DOM).

    :param d_o_m_data: Данные "стакана" ( результат вызова get_depth_of_market() )
    :type d_o_m_data: dict

    :return: курс верхнего предложения на покупку
    :rtype : float

    """
    return d_o_m_data['bids'][0][0]


def depth_first_bid_amount(d_o_m_data):
    """
    Получаем количество верхнего предложения на покупку из "стакана" (Depth_of_Market, DOM).

    :param d_o_m_data: Данные "стакана" ( результат вызова get_depth_of_market() )
    :type d_o_m_data: dict

    :return: количество верхнего предложения на покупку
    :rtype : float

    """
    return d_o_m_data['bids'][0][1]


def get_stock_fee(pairs_data, curr_pair):
    """
    Получение процента комиссии по данной валютной паре

    :param pairs_data: Настройки валютных пар
    :type pairs_data: dict

    :param curr_pair: Пара валют, например 'LTC_BTC'
    :type curr_pair: str

    :return: Процент комиссии (0.001 - это 0.1%)
    :rtype : float

    """
    return pairs_data[curr_pair.lower()]['fee'] / 100


def spended(hist_data, stock_fee_perc):
    """
    Сколько необходимо потратить.

    :param hist_data: История предыдущих торгов
    :type hist_data: dict, None

    :param stock_fee_perc: Процент биржи
    :type stock_fee_perc: float

    :return: Сколько необходимо купить базовой валюты
    :rtype : float

    """
    if hist_data:
        amount = float(hist_data['amount'])
        rate = float(hist_data['rate'])

        if hist_data['type'] == 'sell':
            get = amount * rate
            get_fee = get * stock_fee_perc
            real_spend = round(get - get_fee, 8)  # Всего для SELL (без комсы)
        else:
            spend = amount * rate  # Всего для BUY (без комсы)
            spend_fee = spend * stock_fee_perc
            real_spend = round(spend + spend_fee, 8)
    else:       # История торгов пуста
        real_spend = 0.0

    return real_spend


def amount_ins(hist_data, stock_fee_perc):
    """
    Определяет, сколько всего было затрачено на покупки и сколько необходимо купить для подстраховки

    :param hist_data: История предыдущих торгов
    :type hist_data: dict, None

    :param stock_fee_perc: Процент биржи
    :type stock_fee_perc: float

    :return: Сколько еще закупить для подстраховки
    :rtype : float

    """
    spend = spended(hist_data, stock_fee_perc)
    ins_spend = spend + (spend * CONFIG['MARTIN'])
    fee = (spend + (spend * CONFIG['MARTIN'])) * stock_fee_perc
    return ins_spend - fee


def rate_ins(hist_data):
    """
    Определяет цену последнего BUY ордера - процент MARTIN_STEP

    :param hist_data: История предыдущих торгов
    :type hist_data: dict, None

    :return: Сколько еще закупить для подстраховки
    :rtype : float

    """
    rate = float(hist_data['rate']) if hist_data else 0.0
    return rate - (rate * CONFIG['MARTIN_STEP'])


def wanna_get(hist_data, stock_fee_perc):
    """
    Определяет, сколько всего необходимо получить котируемой валюты за базовую

    :param hist_data: История предыдущих торгов
    :type hist_data: dict, None

    :param stock_fee_perc: Процент биржи
    :type stock_fee_perc: float

    :return: Сколько нужно получить
    :rtype : float

    """
    spend = spended(hist_data, stock_fee_perc)
    last_spend = (amount_ins(hist_data, stock_fee_perc) - can_spend()) / 2
    markup = spend * CONFIG['ROI']
    fee = spend * stock_fee_perc
    get = last_spend + markup + fee
    return get


def can_spend():
    """
    Определяет, сколько модем потратить котируемой валюты

    :return: Сколько можем потратить
    :rtype : float

    """
    return CONFIG['CAN_SPEND']


def wanna_get_2(hist_data, stock_fee_perc):
    """
    ???

    :param hist_data: История предыдущих торгов
    :type hist_data: dict, None

    :param stock_fee_perc: Процент биржи
    :type stock_fee_perc: float

    :return: Сколько нужно получить
    :rtype : float

    """
    spend = spended(hist_data, stock_fee_perc)
    get = spend * CONFIG['PROFIT_MARKUP_2'] + spend
    return get


def profit(hist_data, stock_fee_perc):
    """
    Возвращает 'навар'

    :param hist_data: История предыдущих торгов
    :type hist_data: dict, None

    :param stock_fee_perc: Процент биржи
    :type stock_fee_perc: float

    :return: Сколько нужно получить
    :rtype : float

    """
    return wanna_get(hist_data, stock_fee_perc) - spended(hist_data, stock_fee_perc)


# --------------------------  Функции работы с ордерами  ------------------------
def order_expired(order_info, ttl):
    """
    Проверка, исполнен ли ордер за указанное время.

    :param order_info: Подробная информация по ордеру
    :type order_info: dict

    :param ttl: Требуемое время исполнения ордера (в секундах).
    :type ttl: int

    :return: Если ордер не исполнен совсем и время жизни вышло - True, если частично или полностью - False
    :rtype : bool

    """
    retval = False
    time_passed = time.time() - int(order_info['timestamp_created'])
    if time_passed > ttl:
        # Ордер не исполнен, по нему ничего не куплено
        if order_info['status'] == 0 and order_info['start_amount'] == order_info['amount']:
            retval = True

    return retval
