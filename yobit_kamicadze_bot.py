#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import sys
import json
import requests
import urllib.parse
import http.client
import hmac
import hashlib
import time

# Вписываем свои ключи
API_KEY = '' 
API_SECRET = b''

# Тонкая настройка
BASE = 'chp' 
QUOTE = 'eth'

ORDER_LIFE_TIME = 0.2   # через сколько минут отменять неисполненный ордер на покупку BASE
STOCK_FEE = 0.002       # Комиссия, которую берет биржа (0.002 = 0.2%)
OFFERS_AMOUNT = 1       # Сколько предложений из стакана берем для расчета средней цены
OFFERS_AMOUNT_2 = 1     # Тоже - для второй пары
SATOSHI = 0.00000001
CAN_SPEND = 0.000101    # Сколько тратить QUOTE каждый раз при покупке BASE
ROI = 0.003             # Какой навар нужен с каждой сделки? (0.001 = 0.1%)
PROFIT_MARKUP_2 = 0.01
MIN_SPREAD = 1.01       # Минимальный спред (1,01 = 1%)
MARTIN = 2              # Мартингейл коэффициент (2 = 100%)
MARTIN_STEP = 0.03      # Шаг мартина в процентах(0.001 = 0.1%)
DEBUG = False           # True - выводить отладочную информацию, False - писать как можно меньше

CURR_PAIR = BASE.lower() + "_" + QUOTE.lower()

"""
    Каждый новый запрос к серверу должен содержать увеличенное число в диапазоне 1-2147483646
    Поэтому храним число в файле поблизости, каждый раз обновляя его
"""
nonce_file = "./nonce"
if not os.path.exists(nonce_file):
    with open(nonce_file, "w") as out:
        out.write('1')


# Будем перехватывать все сообщения об ошибках с биржи
class ScriptError(Exception):
    pass


class ScriptQuitCondition(Exception):
    pass
        

def call_api(**kwargs):
    # При каждом обращении к торговому API увеличиваем счетчик nonce на единицу
    with open(nonce_file, 'r+') as inp:
        nonce = int(inp.read())
        inp.seek(0)
        inp.write(str(nonce+1))
        inp.truncate()

    payload = {'nonce': nonce}

    if kwargs:
        payload.update(kwargs)
    payload = urllib.parse.urlencode(payload)

    hdigest = hmac.new(key=API_SECRET, digestmod=hashlib.sha512)
    hdigest.update(payload.encode('utf-8'))
    sign = hdigest.hexdigest()
    
    headers = {"Content-type": "application/x-www-form-urlencoded", "Key": API_KEY, "Sign": sign}
    conn = http.client.HTTPSConnection("yobit.io", timeout=60)
    conn.request("POST", "/tapi/", payload, headers)
    response = conn.getresponse().read()
    conn.close()

    try:
        obj = json.loads(response.decode('utf-8'))

        if 'error' in obj and obj['error']:
            raise ScriptError(obj['error'])
        return obj
    except json.decoder.JSONDecodeError:
        # raise ScriptError('Ошибка анализа возвращаемых данных, получена строка', response)
        raise ScriptError(' Ошибка анализа возвращаемых данных, йобаны йобит :-)')


# Уменьшено кол-во запросов к апи by Oleg Volkov
def dom():
    # Получаем информацию по предложениям из стакана
    offers = json.loads(requests.get("https://yobit.io/api/3/depth/" + CURR_PAIR + "?limit=" +
                                     str(OFFERS_AMOUNT)).text)[CURR_PAIR]
    ask = float(offers['asks'][0][0])
    ask_amount = float(offers['asks'][0][1])
    bid = float(offers['bids'][0][0])
    bid_amount = float(offers['bids'][0][1])
    # print (' Получаем информацию из стаканов\n ASK: {ask:0.8f} amount: {ask_amount:0.8f}\n
    # BID: {bid:0.8f} amount: {bid_amount:0.8f}'.format(ask = dom()[0], ask_amount = dom()[1], bid = dom()[2],
    # bid_amount = dom()[2]))
    return ask, ask_amount, bid, bid_amount


def can_spend():
    return CAN_SPEND


def history():
    pair = None
    order_type = None
    amount = None
    rate = None
    order_id = None
    timestamp = None

    # Запросили сделки по паре. Выводит видимо за сутки от последней к первой
    history_data = call_api(method="TradeHistory", count=1, pair=CURR_PAIR)['return']
    for items in history_data:
        pair = history_data[items]['pair']
        order_type = history_data[items]['type']
        amount = history_data[items]['amount']
        rate = history_data[items]['rate']
        order_id = history_data[items]['order_id']
        timestamp = history_data[items]['timestamp']
    return pair, order_type, amount, rate, order_id, timestamp


def spended():
    pair, order_type, amount, rate, order_id, timestamp = history()
    if order_type == 'sell':
        get = amount * rate
        get_fee = get * STOCK_FEE
        real_spend = round(get - get_fee, 8)  # Всего для SELL (без комсы)
    else:
        spend = amount * rate  # Всего для BUY (без комсы)
        spend_fee = spend * STOCK_FEE
        real_spend = round(spend + spend_fee, 8)
    return real_spend
    

def amount_ins():
    # Сколько всего было затрачено на покупки?
    # Сколько еще закупить для подстраховки?
    spend = spended()
    ins_spend = spend + (spend * MARTIN)
    fee = (spend + (spend * MARTIN)) * STOCK_FEE
    return ins_spend - fee


def rate_ins():
    # Цена последнего BUY ордера - процент MARTIN_STEP
    pair, order_type, amount, rate, order_id, timestamp = history()
    return rate - (rate * MARTIN_STEP)


def wanna_get():
    spend = spended()
    last_spend = (amount_ins() - can_spend()) / 2
    markup = spend * ROI
    fee = spend * STOCK_FEE
    get = last_spend + markup + fee
    return get


def wanna_get_2():
    get = spended()*PROFIT_MARKUP_2 + spended()
    return get
    

def profit():
    return wanna_get() - spended()


# Реализация алгоритма
def main_flow():
    
    try:
        # Получаем список активных ордеров
        opened_orders = []
        try:
            yobit_orders = call_api(method="ActiveOrders", pair=CURR_PAIR)['return']
            for order in yobit_orders:
                o = yobit_orders[order]
                o['order_id'] = order
                opened_orders.append(o)
                
        except KeyError:
            if DEBUG:
                print('Открытых ордеров нет\n')

        sell_orders = []
        # Есть ли неисполненные ордера на продажу BASE?
        for order in opened_orders:
            if order['type'] == 'sell':
                # Если есть ордера на продажу
                time_passed = time.time() - int(order['timestamp_created'])
                if time_passed > ORDER_LIFE_TIME * 60:
                    # Получаем состояние ордера, если он еще не исполнен, отменяем
                    order_info = call_api(method="OrderInfo",
                                          order_id=order['order_id'])['return'][str(order['order_id'])]

                    # Ордер не исполнен, по нему ничего не куплено
                    if order_info['status'] == 0 and order_info['start_amount'] == order_info['amount']:
                        # Отменяем ордер
                        call_api(method="CancelOrder", order_id=order['order_id'])
                        raise ScriptQuitCondition('Отменяем ордер: за ' + str(ORDER_LIFE_TIME) +
                                                  ' минут не удалось продать ' + str(BASE) + '\n')

                # Выход, ждем пока не исполнятся/закроются все ордера на продажу
                # (один ордер может быть разбит биржей на несколько и исполняться частями)
                # Есть неисполненные ордера на продажу BASE, выход
                raise ScriptQuitCondition(' * Продаем по курсу: {rate:0.8f}'.format(rate=order['rate']))
            else:
                # Запоминаем ордера на покупку BASE
                sell_orders.append(order)
                
        # Проверяем, есть ли открытые ордера на покупку BASE
        if sell_orders:  # Открытые ордера есть
            for order in sell_orders:
                # Проверяем, есть ли частично исполненные
                if DEBUG:
                    print('Проверяем, что происходит с отложенным ордером', order['order_id'])
                # Получаем состояние ордера, если он еще не исполнен, отменяем
                order_info = call_api(method="OrderInfo",
                                      order_id=order['order_id'])['return'][str(order['order_id'])]

                # Проверяем, куплено что-нибудь по ордеру
                if order_info['status'] == 0 and order_info['start_amount'] == order_info['amount']:   # Нет
                    time_passed = time.time() - int(order['timestamp_created'])

                    if time_passed > ORDER_LIFE_TIME * 60:
                        # Ордер уже давно висит, никому не нужен, отменяем
                        call_api(method="CancelOrder", order_id=order['order_id']) 
                        raise ScriptQuitCondition(' Отменяем ордер: за ' + str(ORDER_LIFE_TIME) +
                                                  ' минут не удалось купить ' + str(BASE) + '\n')
                    else:
                        # print('\r * {}'.format(time.strftime("%H:%M:%S")), end='')
                        # 'Выход, продолжаем надеяться купить валюту по указанному ранее курсу
                        raise ScriptQuitCondition('   Покупаем... прошло %s секунд' % str(time_passed))
                else:
                    raise ScriptQuitCondition(str(order_info['status']) +
                                              ' :Статус\n * Ордер на покупку открыт, по нему были торги, ждем\n' +
                                              str(order_info['rate']) + ' :Цена\n' +
                                              str(order_info['start_amount']) + ' :Начальный обьем\n' +
                                              str(order_info['amount']) + ' :Остаточный обьем')
                   
        else:  # Открытых ордеров нет
            balances = call_api(method="getInfo")['return']['funds']
            if float(balances.get(BASE, 0)) > 0:  # Есть ли в наличии BASE, которую можно продать?
                """
                    Высчитываем курс для продажи.
                    Нам надо продать всю валюту, которую купили, на сумму, за которую купили + немного навара 
                    и минус комиссия биржи. При этом важный момент, что валюты у нас меньше, 
                    чем купили - бирже ушла комиссия 
                    0.00134345 1.5045
                    Поэтому курс продажи может получиться довольно высоким
                """
                # Получаем информацию по предложениям из стакана
                # offers = json.loads(requests.get("https://yobit.io/api/3/depth/" +
                # CURR_PAIR + "?limit=" + str(OFFERS_AMOUNT)).text)[CURR_PAIR]
                # Если минимальная цена продажи меньше чем цена нашего ордера - продаем по wanna_get()
                # Не выставляем ордер на продажу а выставляем подстраховку
                if dom()[0] < (wanna_get() / float(balances[BASE])):
                    # Если есть доступные средства на подстраховку    
                    if float(balances.get(QUOTE, 0)) >= amount_ins():
                        prnstr = '\n *************** {pair} ***************\n ' \
                                 'Получаем информацию из стаканов\n ASK: {ask:0.8f} ' \
                                 'amount: {ask_amount:0.8f} {quote}\n ' \
                                 'BID: {bid:0.8f} amount: {bid_amount:0.8f} {base}'
                        print(prnstr.format(pair=CURR_PAIR, ask=dom()[0], ask_amount=dom()[1],
                                            quote=QUOTE, bid=dom()[2], bid_amount=dom()[2], base=BASE))
                        # Инфа об ордере на продажу всего купленного
                        prnstr = ' Ждем условий для подажи:\n ASK: {rate:0.8f} ' \
                                 'amount: {amount_b:0.8f} {base}\n' \
                                 'Инвестировал: {all_spend:0.8f} {quote}\n' \
                                 'Итого вернем: {amount_q:0.8f} {quote}'
                        print(prnstr.format(pair=CURR_PAIR,  amount_b=balances[BASE], base=BASE,
                                            rate=wanna_get() / float(balances[BASE]),
                                            all_spend=wanna_get() - (spended() * ROI),
                                            amount_q=wanna_get() - (wanna_get() * STOCK_FEE),
                                            quote=QUOTE))
                        prnstr = ' Рынок падает, будем докупать с шагом {step:0.2f}% ' \
                                 'от предыдущей цены покупки.'
                        print(prnstr.format(step=MARTIN_STEP * 100))

                        # Создаем ордер подстраховки
                        new_order = call_api(method="Trade", pair=CURR_PAIR, type="buy",
                                             rate=round(rate_ins(), 8),
                                             amount=round(amount_ins() / rate_ins(), 8))['return']
   
                        prnstr = ' Создан ордер подстраховки по курсу {rate:0.8f} затратим: {amount:0.8f} {curr}. ' \
                                 'id ордера = {order_id}'
                        print(prnstr.format(rate=rate_ins(), amount=amount_ins(),
                                            curr=QUOTE, order_id=new_order['order_id']))
                    else:
                        prnstr = ' Создал бы ордер подстраховки по курсу {rate:0.8f} кол-во: {amount:0.8f} {curr}\n' \
                                 'Но нет денег - это ЗАМАЗКА!'
                        print(prnstr.format(rate=rate_ins(), amount=amount_ins(), curr=QUOTE))
                else:
                    prnstr = ' MIN ASK: {rate:0.8f} {curr}\n * Продаем кол-во: {amount:0.8f}'
                    print(prnstr.format(curr=CURR_PAIR, amount=balances[BASE],
                                        rate=wanna_get() / float(balances[BASE])))
                    prnstr = ' * Пробуем продать c Profit более:{profit:0.8f} {curr}'
                    print(prnstr.format(roi=float(ROI * 100), profit=profit(), curr=QUOTE))

                    # Выставляем ордер на продажу по лучшей цене
                    my_amount = float(balances[BASE])
                    new_order = call_api(method="Trade", pair=CURR_PAIR, type="sell",
                                         rate=round(dom()[0] - SATOSHI, 8),
                                         amount=round(my_amount, 8))['return']

                    # Высчитываем курс для продажи
                    sell_rate = wanna_get() / my_amount
                    prnstr = ' Не ставим ордер подстраховки по курсу {rate:0.8f} кол-во: {amount:0.8f} {curr}\n' \
                             'Наша цена лучшая в стакане!'
                    print(prnstr.format(curr=CURR_PAIR, rate=sell_rate - (sell_rate * MARTIN_STEP), amount=my_amount))
                    prnstr = ' ASK: {rate:0.8f} {curr}\n * Продаем кол-во: {amount:0.8f}'
                    print(prnstr.format(curr=CURR_PAIR, amount=my_amount, rate=dom()[0] - SATOSHI))
                    if DEBUG:
                        print('Создан ордер на продажу', BASE, new_order['order_id'])
            else:
                # BASE нет, надо докупить
                # Достаточно ли денег на балансе в валюте QUOTE (Баланс >= CAN_SPEND)
                if float(balances.get(QUOTE, 0)) >= can_spend():
                    # Получаем информацию по предложениям из стакана
                    # offers = json.loads(requests.get("https://yobit.io/api/3/depth/" + CURR_PAIR + "?limit=" +
                    #                                  str(OFFERS_AMOUNT)).text)[CURR_PAIR]
                    if dom()[0]/dom()[2] < MIN_SPREAD:
                        print(" * Узкий спред, пропускаем\n")
                    else:
                        # prices = ([bid[0] for bid in offers['bids']])
                        # prices = dom()[2]
                        ask = dom()[0]

                    try:        
                        # avg_price = sum(prices) / len(prices)
                        """
                            Посчитать, сколько валюты BASE можно купить.
                            На сумму CAN_SPEND за минусом STOCK_FEE, и с учетом ROI
                            ( = ниже средней цены рынка, с учетом комиссии и желаемого профита)
                        """
                        my_need_price = dom()[2]
                        my_prise_first = dom()[2] + SATOSHI
                        my_amount = can_spend() / my_need_price
                        sell = wanna_get() / my_amount
                        sell_2 = wanna_get_2() / my_amount
                        roi = ROI * 100
                        if dom()[0] < float(sell_2):
                            prnstr = '\n *************** {pair} ***************\n' \
                                     ' {curr} {rate:0.8f} :price BUY amount: {amount:0.8f} '
                            print(prnstr.format(pair=CURR_PAIR, amount=my_amount, rate=my_need_price, curr=BASE))
                            # Информация
                            prnstr = ' {curr} {spend:0.8f} :spend funds: {funds:0.8f}'
                            print(prnstr.format(pair=CURR_PAIR, funds=float(balances.get(QUOTE, 0)),
                                                curr=QUOTE, spend=can_spend()))

                            # Допускается ли покупка такого кол-ва валюты (т.е. не нарушается минимальная сумма сделки)
                            new_order = call_api(method="Trade", pair=CURR_PAIR, type="buy",
                                                 rate=round(my_need_price, 8),
                                                 amount=round(my_amount, 8))['return']
                        else:
                            prnstr = '\n *************** {pair} ***************\n' \
                                     '{curr} {rate:0.8f} :price BUY amount: {amount:0.8f}'
                            print(prnstr.format(pair=CURR_PAIR, amount=my_amount, rate=my_prise_first, curr=BASE))
                            # Информация
                            prnstr = '{curr} {spend:0.8f} :spend funds: {funds:0.8f}'
                            print(prnstr.format(pair=CURR_PAIR, funds=float(balances.get(QUOTE, 0)),
                                                curr=QUOTE, spend=can_spend()))
                            # Сужаем спред
                            new_order = call_api(method="Trade", pair=CURR_PAIR, type="buy",
                                                 rate=round(my_prise_first, 8),
                                                 amount=round(my_amount, 8))['return']

                        if DEBUG:
                            print('Создан ордер на покупку ID:', new_order['order_id'])

                    except ZeroDivisionError:
                        # print('Не удается вычислить среднюю цену', prices)
                        print('Удачное деление на ноль!')
                else:
                    raise ScriptQuitCondition('Выход, не хватает денег')
        
    except ScriptError as err:
        print(err)

    except ScriptQuitCondition as err:
        print(err)
    except Exception as err:
        print("!!!!", err)


try:
    alt_balance = call_api(method="getInfo")['return']['funds'].get(BASE.lower(), 0)
    if alt_balance > 0:
        decision = input("""
            {amount:0.8f} {curr1} :Баланс
            Продавать по курсу {rate:0.8f} ?
            {wanna_get:0.8f} {curr2} :Всего-ком
            
            Потрачено в последнем BUY ордере
            {spended:0.8f} {curr2} :Всего+ком
            
            C минимальным профитом
            {profit:0.8f} {curr2}
            Введите Д/Y или Н/N
        """.format(
            amount=alt_balance,
            curr1=BASE,
            curr2=QUOTE,
            wanna_get=wanna_get() - wanna_get() * STOCK_FEE,
            spended=spended() * 1,
            rate=wanna_get() / alt_balance,
            profit=profit()
        ))
        if decision in ('N', 'n', 'Н', 'н'):
            print("Тогда избавьтесь от {curr} и перезапустите бота".format(curr=BASE))
            sys.exit(0)

except Exception as errex:
    print(str(errex))


# ------ Главный цикл -----
while True:
    main_flow()
    time.sleep(1)
