#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import tApi
import time


class ScriptError(Exception):
    pass


class ScriptQuitCondition(Exception):
    pass


# Реализация алгоритма
def main_flow():
    try:
        # Получаем список активных ордеров
        opened_orders = []
        try:
            yobit_orders = tApi.call_api(method="ActiveOrders", pair=tApi.CURR_PAIR)['return']
            for order in yobit_orders:
                o = yobit_orders[order]
                o['order_id'] = order
                opened_orders.append(o)

        except KeyError:
            if tApi.DEBUG:
                print('Открытых ордеров нет\n')

        sell_orders = []
        # Есть ли неисполненные ордера на продажу tApi.BASE?
        for order in opened_orders:
            if order['type'] == 'sell':
                # Если есть ордера на продажу
                time_passed = time.time() - int(order['timestamp_created'])
                if time_passed > tApi.ORDER_LIFE_TIME * 60:
                    # Получаем состояние ордера, если он еще не исполнен, отменяем
                    order_info = tApi.call_api(method="OrderInfo",
                                               order_id=order['order_id'])['return'][str(order['order_id'])]

                    # Ордер не исполнен, по нему ничего не куплено
                    if order_info['status'] == 0 and order_info['start_amount'] == order_info['amount']:
                        # Отменяем ордер
                        tApi.call_api(method="CancelOrder", order_id=order['order_id'])
                        raise ScriptQuitCondition('Отменяем ордер: за ' + str(tApi.ORDER_LIFE_TIME) +
                                                  ' минут не удалось продать ' + str(tApi.BASE) + '\n')

                # Выход, ждем пока не исполнятся/закроются все ордера на продажу
                # (один ордер может быть разбит биржей на несколько и исполняться частями)
                # Есть неисполненные ордера на продажу tApi.BASE, выход
                raise ScriptQuitCondition(' * Продаем по курсу: {rate:0.8f}'.format(rate=order['rate']))
            else:
                # Запоминаем ордера на покупку tApi.BASE
                sell_orders.append(order)

        # Проверяем, есть ли открытые ордера на покупку tApi.BASE
        if sell_orders:  # Открытые ордера есть
            for order in sell_orders:
                # Проверяем, есть ли частично исполненные
                if tApi.DEBUG:
                    print('Проверяем, что происходит с отложенным ордером', order['order_id'])
                # Получаем состояние ордера, если он еще не исполнен, отменяем
                order_info = tApi.call_api(method="OrderInfo",
                                           order_id=order['order_id'])['return'][str(order['order_id'])]

                # Проверяем, куплено что-нибудь по ордеру
                if order_info['status'] == 0 and order_info['start_amount'] == order_info['amount']:  # Нет
                    time_passed = time.time() - int(order['timestamp_created'])

                    if time_passed > tApi.ORDER_LIFE_TIME * 60:
                        # Ордер уже давно висит, никому не нужен, отменяем
                        tApi.call_api(method="CancelOrder", order_id=order['order_id'])
                        raise ScriptQuitCondition(' Отменяем ордер: за ' + str(tApi.ORDER_LIFE_TIME) +
                                                  ' минут не удалось купить ' + str(tApi.BASE) + '\n')
                    else:
                        # print('\r * {}'.format(time.strftime("%H:%M:%S")), end='')
                        # 'Выход, продолжаем надеяться купить валюту по указанному ранее курсу
                        raise ScriptQuitCondition('   Покупаем... прошло %s секунд' % str(time_passed))
                else:
                    raise ScriptQuitCondition(str(order_info['status']) +
                                              ' :Статус - частичное исполнение ордера\n' +
                                              '* Ордер на покупку открыт, по нему были торги, ждем\n' +
                                              str(order_info['rate']) + ' :Цена\n' +
                                              str(order_info['start_amount']) + ' :Начальный обьем\n' +
                                              str(order_info['amount']) + ' :Остаточный обьем')

        else:  # Открытых ордеров нет
            balances = tApi.call_api(method="getInfo")['return']['funds']

            if float(balances.get(tApi.BASE, 0)) > 0:  # Есть ли в наличии tApi.BASE, которую можно продать?

                if tApi.dom()[0] < (tApi.wanna_get() / float(balances[tApi.BASE])):
                    # Если есть доступные средства на подстраховку
                    if float(balances.get(tApi.QUOTE, 0)) >= tApi.amount_ins():
                        prnstr = '\n *************** {pair} ***************\n ' \
                                 'Получаем информацию из стаканов\n ASK: {ask:0.8f} ' \
                                 'amount: {ask_amount:0.8f} {base}\n ' \
                                 'BID: {bid:0.8f} amount: {bid_amount:0.8f} {quote}'
                        print(prnstr.format(pair=tApi.CURR_PAIR, ask=tApi.dom()[0], ask_amount=tApi.dom()[1],
                                            quote=tApi.QUOTE, bid=tApi.dom()[2], bid_amount=tApi.dom()[2],
                                            base=tApi.BASE))
                        # Инфа об ордере на продажу всего купленного
                        prnstr = ' Ждем условий для подажи:\n ASK: {rate:0.8f} ' \
                                 'amount: {amount_b:0.8f} {base}\n' \
                                 'Инвестировал: {all_spend:0.8f} {quote}\n' \
                                 'Итого вернем: {amount_q:0.8f} {quote}'
                        print(prnstr.format(pair=tApi.CURR_PAIR, amount_b=balances[tApi.BASE], base=tApi.BASE,
                                            rate=tApi.wanna_get() / float(balances[tApi.BASE]),
                                            all_spend=tApi.wanna_get() - (tApi.spended() * tApi.ROI),
                                            amount_q=tApi.wanna_get() - (tApi.wanna_get() * tApi.stock_fee()),
                                            quote=tApi.QUOTE))
                        prnstr = ' Будем докупать с шагом не менее {step:0.4f}% ' \
                                 'от предыдущей цены покупки.'
                        print(prnstr.format(step=tApi.MARTIN_STEP * 100))

                        if tApi.rate_ins() > tApi.dom()[2]:
                            # Создаем ордер подстраховки
                            new_order = tApi.call_api(method="Trade", pair=tApi.CURR_PAIR, type="buy",
                                                      rate=round(tApi.dom()[2], 8),
                                                      amount=round(tApi.amount_ins() / tApi.rate_ins(), 8))['return']

                            prnstr = ' Создан ордер подстраховки ID: {order_id}\n' \
                                     ' BID: {rate:0.8f} amount: {amount:0.8f} {curr}' \

                            print(prnstr.format(rate=tApi.dom()[2] + tApi.SATOSHI, amount=tApi.amount_ins(),
                                                curr=tApi.QUOTE, order_id=new_order['order_id']))
                        else:
                            # Создаем ордер подстраховки
                            new_order = tApi.call_api(method="Trade", pair=tApi.CURR_PAIR, type="buy",
                                                      rate=round(tApi.rate_ins(), 8),
                                                      amount=round(tApi.amount_ins() / tApi.rate_ins(), 8))['return']

                            prnstr = ' Создан ордер подстраховки ID: {order_id}\n' \
                                     ' BID: {rate:0.8f} amount: {amount:0.8f} {curr}' \

                            print(prnstr.format(rate=tApi.rate_ins(), amount=tApi.amount_ins(),
                                                curr=tApi.QUOTE, order_id=new_order['order_id']))
                    else:
                        prnstr = ' Создал бы ордер подстраховки\n' \
                                 ' BID: {rate:0.8f} amount: {amount:0.8f} {curr} ' \
                                 'Но нет денег - это ЗАМАЗКА!'

                        print(prnstr.format(rate=tApi.rate_ins(), amount=tApi.amount_ins(), curr=tApi.QUOTE))
                else:
                    prnstr = ' MIN ASK: {rate:0.8f} {curr}\n * Продаем кол-во: {amount:0.8f}'

                    print(prnstr.format(curr=tApi.CURR_PAIR, amount=balances[tApi.BASE],
                                        rate=tApi.wanna_get() / float(balances[tApi.BASE])))

                    prnstr = ' * Пробуем продать c Profit более:{profit:0.8f} {quote}'

                    print(prnstr.format(profit=float(tApi.profit()), quote=tApi.QUOTE))

                    # Выставляем ордер на продажу по лучшей цене
                    my_amount = float(balances[tApi.BASE])
                    new_order = tApi.call_api(method="Trade", pair=tApi.CURR_PAIR, type="sell",
                                              rate=round(tApi.dom()[0] - tApi.SATOSHI, 8),
                                              amount=round(my_amount, 8))['return']
                    # Высчитываем курс для продажи
                    sell_rate = tApi.wanna_get() / my_amount
                    prnstr = ' Не ставим ордер подстраховки по курсу {rate:0.8f} кол-во: {amount:0.8f} {curr}\n' \
                             'Наша цена лучшая в стакане!'
                    print(prnstr.format(curr=tApi.QUOTE, rate=sell_rate - (sell_rate * tApi.MARTIN_STEP),
                                        amount=tApi.amount_ins()))
                    prnstr = ' ASK: {rate:0.8f} {curr}\n * Продаем кол-во: {amount:0.8f}'
                    print(prnstr.format(curr=tApi.CURR_PAIR, amount=my_amount, rate=tApi.dom()[0] - tApi.SATOSHI))
                    if tApi.DEBUG:
                        print('Создан ордер на продажу', tApi.BASE, new_order['order_id'])
            else:
                # tApi.BASE нет, надо докупить
                # Достаточно ли денег на балансе в валюте tApi.QUOTE (Баланс >= tApi.can_spend)
                if float(balances.get(tApi.QUOTE, 0)) >= tApi.can_spend():
                    # Получаем информацию по предложениям из стакана
                    if tApi.dom()[0] / tApi.dom()[2] < tApi.MIN_SPREAD:
                        print(" * Узкий спред, пропускаем...\n")
                    else:
                        # prices = ([bid[0] for bid in offers['bids']])
                        print(' * Спред широкий, заходим в рынок\n')
                    try:
                        # avg_price = sum(prices) / len(prices)
                        """
                            Посчитать, сколько валюты tApi.BASE можно купить.
                            На сумму tApi.can_spend за минусом tApi.stock_fee(), и с учетом tApi.ROI
                            ( = ниже средней цены рынка, с учетом комиссии и желаемого профита)
                        """
                        my_need_price = tApi.dom()[2] - tApi.SATOSHI
                        my_prise_first = tApi.dom()[2] + tApi.SATOSHI
                        my_amount = tApi.can_spend() / my_need_price
                        # sell = tApi.wanna_get() / my_amount
                        sell_2 = tApi.wanna_get_2() / my_amount
                        tApi.ROI = tApi.ROI * 100
                        if tApi.dom()[0] < float(sell_2):
                            prnstr = '\n *************** {pair} ***************\n' \
                                     ' {curr} {rate:0.8f} :price BUY amount: {amount:0.8f} '
                            print(prnstr.format(pair=tApi.CURR_PAIR, amount=my_amount, rate=my_need_price,
                                                curr=tApi.BASE))
                            # Информация
                            prnstr = ' {curr} {spend:0.8f} :spend funds: {funds:0.8f}'
                            print(prnstr.format(pair=tApi.CURR_PAIR, funds=float(balances.get(tApi.QUOTE, 0)),
                                                curr=tApi.QUOTE, spend=tApi.can_spend()))

                            # Допускается ли покупка такого кол-ва валюты (т.е. не нарушается минимальная сумма сделки)
                            new_order = tApi.call_api(method="Trade", pair=tApi.CURR_PAIR, type="buy",
                                                      rate=round(my_need_price, 8),
                                                      amount=round(my_amount, 8))['return']
                        else:
                            prnstr = '\n *************** {pair} ***************\n' \
                                     '{curr} {rate:0.8f} :price BUY amount: {amount:0.8f}'
                            print(prnstr.format(pair=tApi.CURR_PAIR, amount=my_amount, rate=my_prise_first,
                                                curr=tApi.BASE))
                            # Информация
                            prnstr = '{curr} {spend:0.8f} :spend funds: {funds:0.8f}'
                            print(prnstr.format(pair=tApi.CURR_PAIR, funds=float(balances.get(tApi.QUOTE, 0)),
                                                curr=tApi.QUOTE, spend=tApi.can_spend()))
                            # Сужаем спред
                            new_order = tApi.call_api(method="Trade", pair=tApi.CURR_PAIR, type="buy",
                                                      rate=round(my_prise_first, 8),
                                                      amount=round(my_amount, 8))['return']

                        if tApi.DEBUG:
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
