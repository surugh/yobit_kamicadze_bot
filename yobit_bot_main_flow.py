#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
    Code was writen by Oleg Volkov https://github.com/oavolkov
    Algo idea by Lebedev Siarhei  https://github.com/surugh

"""
import yobit
from yobit_bot_functions import *


# --------------------------  Главная функция алгоритма торгов  ------------------------
def main_flow(stock_api, curr_pair, pair_data):
    """
    Функция, в которой реализуется алгоритм торгов по выбранной валютной паре.

    :param stock_api: Объект API биржи
    :type stock_api: yobit.YobitAPI

    :param curr_pair: Пара валют, например 'LTC_BTC'.
    :type curr_pair: str

    :param pair_data: Данные по параметрам валютных пар на бирже
    :type pair_data: dict

    :return: Ответ не предусмотрен (всегда True)
    :rtype : bool

    """
    # Выделяем из пары базовую и котируемую валюты
    base_curr, quote_curr = curr_pair.split('_')
    dec_places = pair_data[curr_pair.lower()]['decimal_places']

    # Получаем список активных ордеров
    ps = 'Пара {pair:s}. Получаем список активных ордеров.'
    print(ps.format(pair=curr_pair))
    sell_orders = []
    buy_orders = []
    opened_orders = get_opened_orders(stock_api, curr_pair)

    for order in opened_orders:
        order_id = order['order_id']

        # Получаем информацию об исполнении ордера
        order_info = stock_api.order_info(order_id)['return'][str(order_id)]
        order_life = CONFIG['ORDER_LIFE_TIME']

        if order['type'] == 'sell':     # Есть ордера на продажу
            # Получаем состояние ордера, если он еще не исполнен (return: True), отменяем
            if order_expired(order_info, order_life * 60):
                stock_api.cancel_order(order_id)

                # И выходим, на следующую итерацию
                ps = 'Пара {pair:s}. Отменяем ордер на продажу - id: {order_id:s}\n' \
                     ' за {time:0.2f} минут не удалось продать {b_curr:s}'
                raise ScriptQuitCondition(ps.format(pair=curr_pair, order_id=order_id, time=float(order_life),
                                                    b_curr=base_curr))

            else:
                sell_orders.append(order)

                # Есть частично исполненные ордера на продажу
                # На этом витке выходим, ждем пока не исполнятся/закроются все ордера на продажу
                # (один ордер может быть разбит биржей на несколько и исполняться частями)
                ps = 'Пара {pair:s}. Частично исполненный ордер - id: {order_id:s}\n' \
                     ' на продажу {b_curr} по курсу {rate:0.8f} {b_curr}/{q_curr}. Ждем его исполнения.'
                raise ScriptQuitCondition(ps.format(pair=curr_pair, order_id=order_id, rate=order['rate'],
                                                    b_curr=base_curr, q_curr=quote_curr))

        else:                           # Есть ордера на покупку, обрабатываем их.
            # Получаем состояние ордера, если он еще не исполнен (return: True), отменяем
            if order_expired(order_info, order_life * 60):
                stock_api.cancel_order(order_id)

                # И выходим, на следующую итерацию
                ps = 'Пара {pair:s}. Отменяем ордер на покупку - id: {order_id:s}\n' \
                     ' за {time:0.2f} минут не удалось купить {b_curr:s}'
                raise ScriptQuitCondition(ps.format(pair=curr_pair, order_id=order_id, time=order_life,
                                                    b_curr=base_curr))

            else:
                buy_orders.append(order)

                # Есть частично исполненные ордера на продажу
                # На этом витке выходим, продолжаем надеяться купить валюту по указанному ранее курсу
                ps = 'Пара {pair:s}. Частично исполненный ордер - id: {order_id:s}\n' \
                     ' на покупку {b_curr} по курсу {rate:0.8f} {b_curr}/{q_curr}. Ждем его исполнения'
                raise ScriptQuitCondition(ps.format(pair=curr_pair, order_id=order_id, rate=order['rate'],
                                                    b_curr=base_curr, q_curr=quote_curr))

    # Список ордеров на продажу и покупку пустой. Сейчас насоздаем новых!!! :)
    if not (sell_orders and buy_orders):
        ps = 'Пара {pair:s}. Список ордеров пуст.'
        print(ps.format(pair=curr_pair))

        # Определяем процент биржи по текущей валютной паре
        stock_fee = get_stock_fee(pair_data, curr_pair)
        # ps = 'Пара {pair:s}. Биржа забирает {perc:0.2f}% от каждой сделки.'
        # print(ps.format(pair=curr_pair, perc=stock_fee * 100))

        # Запрашиваем балансы по всем валютам в паре
        ps = 'Пара {pair:s}. Получаем балансы:'
        print(ps.format(pair=curr_pair))
        # -----
        balances = get_balances(stock_api, [base_curr, quote_curr])
        # -----
        ps = ' {base_amnt:0.8f} {base_curr:s}\n{quote_amnt: 0.8f} {quote_curr}'
        print(ps.format(base_amnt=balances[base_curr], quote_amnt=balances[quote_curr],
                        base_curr=base_curr, quote_curr=quote_curr))

        # Получаем информацию по предложениям из стакана по выбранной валютной паре
        ps = 'Пара {pair:s}. Получаем Depth of Market ("стакан"). {amnt:d} предложений.'
        print(ps.format(pair=curr_pair, amnt=CONFIG['OFFERS_AMOUNT']))
        # -----
        dom_data = get_depth_of_market(stock_api, curr_pair, CONFIG['OFFERS_AMOUNT'])

        # Запрашиваем сделки по выбранной валютной паре
        ps = 'Пара {pair:s}. Получаем историю сделок.'
        print(ps.format(pair=curr_pair))
        history_data = get_history(stock_api, curr_pair, count=1, order='ASC')


    # -------------------------------------------------------------------------------------------------
    #  Вот тут можно писать свой алгоритм  торговли !!! 
    # -------------------------------------------------------------------------------------------------
        if balances[base_curr] > 0.0:     # Есть что продать. :)
            # Инфа об ордере на продажу всего купленного
            print("* Ждем условий для продажи:")
            s_wanna_get = wanna_get(history_data, stock_fee)
            s_rate = s_wanna_get / balances[base_curr]
            s_invest = s_wanna_get - (spended(history_data, stock_fee) * CONFIG['ROI'])

            ps = ' ASK: {rate:0.8f} amount: {amnt:0.8f} {b_curr:s}\n ' \
                 ' Инвестировал: {invest:0.8f} {q_curr:s}\n ' \
                 ' Итого вернем: {q_wg:0.8f} {q_curr:s} .'
            print(ps.format(pair=curr_pair, amnt=balances[base_curr], rate=s_rate,
                            q_wg=s_wanna_get - (s_wanna_get * stock_fee), invest=s_invest,
                            b_curr=base_curr, q_curr=quote_curr))

            # Если не можем продать в спреде, то будем усредняться
            if depth_first_ask_rate(dom_data) < (wanna_get(history_data, stock_fee) / float(balances[base_curr])):
                # Есть доступные средства на подстраховку ?
                if balances[quote_curr] >= amount_ins(history_data, stock_fee):     # Да, есть

                    ps = ' Шаг усреднения не менее {step:0.2f}% от предыдущей цены покупки.'
                    print(ps.format(step=CONFIG['MARTIN_STEP'] * 100))

                    if rate_ins(history_data) > depth_first_bid_rate(dom_data):
                        print(' * Медведи напирают, трейлим ордер страховки')
                        # Трейлим ордер подстраховки, пытаемся купить как можно дешевле
                        i_rate = round(depth_first_bid_rate(dom_data), dec_places) # - SATOSHI
                        i_amount = round(amount_ins(history_data, stock_fee) / rate_ins(history_data), dec_places)
                        # -----
                        # Тут некотрорые пары с ценой e-05 меня ставили в тупик
                        # Апи отчечал что сумма ставки менее допустимой 0.0001- но это была цена 0.00009!
                        new_order = stock_api.trade(curr_pair, "buy", i_rate, i_amount)['return']
                        # -----
                        ps = ' Создан ордер подстраховки ID: {order_id}\n' \
                             ' BID: {rate:0.8f} amount: {amount:0.8f} {curr}'
                        print(ps.format(rate=i_rate, amount=i_amount, curr=base_curr, order_id=new_order['order_id']))

                    else:
                        print(' * Рынок падает, выставляем ордер страховки')
                        # Создаем ордер подстраховки, поддерживаем быков
                        i_rate = round(rate_ins(history_data), dec_places)
                        i_amount = round(amount_ins(history_data, stock_fee) / rate_ins(history_data), dec_places)
                        # -----
                        new_order = stock_api.trade(curr_pair, "buy", i_rate, i_amount)['return']
                        # -----
                        ps = ' Создан ордер подстраховки ID: {order_id}\n' \
                             ' BID: {rate:0.8f} amount: {amount:0.8f} {curr}'
                        print(ps.format(rate=i_rate, amount=i_amount, curr=base_curr, order_id=new_order['order_id']))

                else:       # Не, денег нет, от слова "совсем". :)
                    ps = ' * Для усреднения необходимо: {amount:0.8f} {curr:s} и курс: {rate:0.8f}\n' \
                         ' но, остаток базовой валюты : {quote_amnt:0.8f} {curr:s} и это ЗАМАЗКА!!!'
                    print(ps.format(rate=rate_ins(history_data), quote_amnt=balances[quote_curr],
                                    amount=amount_ins(history_data, stock_fee),
                                    curr=quote_curr))
                    print(' * Долгосрочная инвестиция')
                    # Выставляем ордер
                    s_amount = round(balances[base_curr], dec_places)
                    s_rate = round(s_wanna_get / balances[base_curr], dec_places)
                    # -----
                    new_order = stock_api.trade(curr_pair, "sell", s_rate, s_amount)['return']
                    # -----
                    ps = ' Создан ордер на продажу ID: {order_id}\n' \
                         ' ASK: {rate:0.8f} amount: {amount:0.8f} {curr}'
                    print(ps.format(rate=s_rate, amount=s_amount, curr=quote_curr, order_id=new_order['order_id']))

            else:
                print(' * Продаем по лучшей цене в стакане')
                # Выставляем ордер на продажу по лучшей цене
                s_amount = round(balances[base_curr], dec_places)
                s_rate = round(depth_first_ask_rate(dom_data) - SATOSHI, dec_places)
                # -----
                new_order = stock_api.trade(curr_pair, "sell", s_rate, s_amount)['return']
                # -----
                ps = ' Создан ордер на продажу ID: {order_id}\n' \
                     ' ASK: {rate:0.8f} amount: {amount:0.8f} {curr}'
                print(ps.format(rate=s_rate, amount=s_amount, curr=quote_curr, order_id=new_order['order_id']))

                if CONFIG['DEBUG']:
                    print('Создан ордер на продажу', base_curr, new_order['order_id'])

        else:       # Продать нечего, надо докупить.
            # Достаточно ли денег на балансе в валюте (больше, чем минимально возможны для покупки лот)
            if balances[quote_curr] >= can_spend():
                # Получаем информацию по предложениям из стакана
                if depth_first_ask_rate(dom_data) / depth_first_bid_rate(dom_data) < CONFIG['MIN_SPREAD']:
                    raise ScriptQuitCondition(" * Узкий спред, пропускаем...")
                else:
                    print(' * Спред широкий, заходим в рынок')
                try:
                    # avg_price = sum(prices) / len(prices)
                    """
                        Посчитать, сколько валюты tApi.BASE можно купить.
                        На сумму tApi.can_spend за минусом tApi.stock_fee(), и с учетом tApi.ROI
                        ( = ниже средней цены рынка, с учетом комиссии и желаемого профита)
                    """
                    my_need_price = depth_first_bid_rate(dom_data) - SATOSHI
                    my_price_first = depth_first_bid_rate(dom_data) + SATOSHI
                    my_need_amount = can_spend() / my_need_price

                    # Сужаем спред
                    a_rate = round(my_price_first, dec_places)
                    a_amount = round(my_need_amount, dec_places)
                    # -----
                    new_order = stock_api.trade(curr_pair, "buy", a_rate, a_amount)['return']
                    # -----
                    ps = ' Создан ордер на покупку ID: {order_id}\n' \
                         ' BID: {rate:0.8f} amount: {amount:0.8f} {curr}'
                    print(ps.format(rate=a_rate, amount=a_amount, curr=quote_curr, order_id=new_order['order_id']))

                    if CONFIG['DEBUG']:
                        print('Создан ордер на покупку. ID:', new_order['order_id'])

                except ZeroDivisionError:
                    # print('Не удается вычислить среднюю цену', prices)
                    print('Удачное деление на ноль!')
            else:
                raise ScriptQuitCondition('Выход, не хватает денег. :(')

    return True
