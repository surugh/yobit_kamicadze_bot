#!/usr/bin/env python
"""
    See https://yobit.net/en/api/
    Thanks for https://github.com/NanoBjorn/yobit
    Best regards to Oleg Volkov https://github.com/oavolkov

"""
import os
import hmac
import hashlib
try:
    from urllib import urlencode
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urlencode
    from urllib.parse import urljoin
import requests


__version__ = '0.2.6'


class YobitException(Exception):
    def __init__(self, errtext=''):
        self.__errtext = errtext

    def __str__(self, *args, **kwargs):
        return self.__errtext


class YobitAPI(object):
    # __public_api_url = 'https://yobit.net/api/3'
    # __trade_api_url = 'https://yobit.net/tapi'
    __public_api_url = 'https://yobit.io/api/3'
    __trade_api_url = 'https://yobit.io/tapi'

    def __init__(self, api_key, api_secret, api_filepath='~/appdata/'):
        self.__filepath = api_filepath
        self.__api_key = api_key
        self.__api_secret = bytes(api_secret, encoding='utf-8')
        __filename = 'yobit_' + self.__api_key.lower() + '.nonce'
        self.__nonce_file = os.path.expanduser(self.__filepath + __filename)
        if not os.path.exists(self.__nonce_file):
            with open(self.__nonce_file, "w") as nncf:
                nncf.write('1')

    def nonce(self):
        with open(self.__nonce_file, "r+") as nncf:
            nonceval = int(nncf.read())
            nncf.seek(0)
            nncf.write(str(nonceval + 1))
            nncf.truncate()
        return nonceval

    def sha512(self, data):
        hmd = hmac.new(key=self.__api_secret, digestmod=hashlib.sha512)
        hmd.update(data.encode('utf-8'))
        return hmd.hexdigest()

    @staticmethod
    def __check_trade_api_response(resp_json):
        """
        Raise exception, if data from stock exchange contain error

        :param resp_json: Data from stock exchange in JSON format
        :type resp_json: dict

        :return: True, if data from stock is success
        :rtype : bool

        """
        try:
            retval = True if resp_json['success'] == 1 else False
        except KeyError:
            retval = False
        try:
            estr = resp_json['error'] if not retval else ''
        except KeyError:
            estr = 'Unknown error.'

        if not retval:
            raise YobitException(estr)

        return retval

    def __query_public_api(self, method, pair=None, options=None):
        """
        Queries YoBit Public API with given method, pair and options.

        :param method: Query method for getting info from Public API
        :type method: str

        :param pair: Pair of currencies, example 'ltc_btc'
        :type pair: str

        :param options: Extra options for query
        :type options: dict

        :return: JSON response from YoBit Public API
        :rtype : dict

        """
        if not options:
            options = {}
        if not pair:
            pair = ''

        hdrs = {
            'Content-type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:60.0) Gecko/20100101 Firefox/60.0'
        }

        request_url = self.__public_api_url + "/" + method
        if pair != '':
            request_url += '/' + pair.lower()
        if options != {}:
            request_url += '?'
            request_url += urlencode(options)

        resp = requests.post(request_url, headers=hdrs)
        resp.raise_for_status()
        obj = resp.json()
        return obj

    def __query_trade_api(self, method, options=None):
        """
        Queries YoBit Trade API with given method and options.

        :param method: Query method  for getting info from Trade API
        :type method: str

        :param options: Extra options for query
        :type options: dict

        :return: JSON response from YoBit Trade API
        :rtype : dict

        """
        hdrs = {
            'Content-type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:60.0) Gecko/20100101 Firefox/60.0',
            'Cache-Control': 'no-cache, no-store, must-revalidate'
        }

        if options is None:
            options = {}

        request_url = self.__trade_api_url + '/'
        options['method'] = method
        options['nonce'] = self.nonce()
        sign = self.sha512(urlencode(options))
        hdrs['Key'] = self.__api_key
        hdrs['Sign'] = sign

        resp = requests.post(request_url, data=options, headers=hdrs)
        resp.raise_for_status()
        obj = resp.json()
        self.__check_trade_api_response(obj)
        return obj

    def info(self):
        """
        Used to get about server time and coin pares of the YoBit market.
        Response contains min_price, max_price, min_amount, and fee for each pair.

        :return: JSON of pairs with info
        :rtype : dict

        """
        obj = self.__query_public_api('info')
        return obj

    def ticker(self, pair):
        """
        Used to get statistic data for the last 24 hours for selected pair.
        Response contains hight, low, avg, vol, vol_cur, last, buy, sell fields for the pair.

        :param pair: Pair of currencies, example 'ltc_btc'
        :type pair: str

        :return: Statistic
        :rtype : dict

        """
        obj = self.__query_public_api('ticker', pair.lower())
        return obj

    def depth(self, pair, limit=150):
        """
        Used to get information about lists of active orders for selected pair.
        Response contains asks and bids lists for the pair.

        :param pair: Pair of currencies, example 'ltc_btc'
        :type pair: str

        :param limit: Size of response (on default 150 to 2000 max)
        :type limit: int

        :return: Current information about active orders
        :rtype : dict

        """
        obj = self.__query_public_api('depth', pair.lower(), {'limit': limit})
        return obj

    def trades(self, pair, limit=150):
        """
        Used to get information about the last transactions of selected pair.
        Response contains type, price, amount, tid, timestamp for each transaction.

        :param pair: Pair of currencies, example 'ltc_btc'
        :type pair: str

        :param limit: Size of response (on default 150 to 2000 max)
        :type limit: int

        :return: Current information about transactions
        :rtype : dict
        """
        obj = self.__query_public_api('trades', pair.lower(), {'limit': limit})
        return obj

    def get_info(self):
        """
        Used to get information about user's balances and priviledges of API-key
        as well as server time. Response contains funds, fund_incl_orders, rights,
        transaction_count, open_orders, server time.

        :return: JSON with info
        :rtype : dict

        """
        obj = self.__query_trade_api('getInfo')
        return obj

    def trade(self, pair, trade_type, rate, amount):
        """
        Used to create new orders for stock exchange trading

        :param pair: Pair of currencies, example 'ltc_btc'
        :type pair: str

        :param trade_type: 'buy' or 'sell'
        :type trade_type: str

        :param rate: Exchange rate for buying or selling
        :type rate: float

        :param amount: Amount of needed for buying or selling
        :type amount: float

        :return: Success, info about the order, order_id.
        :rtype : dict

        """
        obj = self.__query_trade_api('Trade', {'pair': pair.lower(),
                                               'type': trade_type,
                                               'rate': rate,
                                               'amount': amount})
        return obj

    def active_orders(self, pair):
        """
        Used to get list of user's active orders.

        :param pair: Pair of currencies, example 'ltc_btc'
        :type pair: str

        :return: List of orders byu order_id
        :rtype : dict

        """
        obj = self.__query_trade_api('ActiveOrders', {'pair': pair.lower()})
        return obj

    def order_info(self, order_id):
        """
        Used to get detailed information about the chosen order.
        Response contains pair, type, start_amount, amount, rate,
        timestamp_created, status for the order.

        :param order_id: Order ID
        :type order_id: int

        :return: JSON of the order
        :rtype : dict

        """
        obj = self.__query_trade_api('OrderInfo', {'order_id': order_id})
        return obj

    def cancel_order(self, order_id):
        """
        Used to cancel the choosen order.

        :param order_id: Order ID
        :type order_id: int

        :return: Success and balances active after request
        :rtype : dict

        """
        obj = self.__query_trade_api('CancelOrder', {'order_id': order_id})
        return obj

    def trade_history(self, pair, from_start=0, count=1000, from_id=0, end_id=100000000000,
                      order='DESC', since=None, end=None):
        """
        Used to retrieve transaction history.
        Response contains list of transactions with pair, type,
        amount, rate, order_id, is_your_order and timestamp for each transaction.

        :param pair: Pair of currencies, example 'ltc_btc'
        :type pair: str

        :param from_start: Number of transaction from which response starts (default 0)
        :type from_start: int

        :param count: Quantity of transactions in response (default 1000)
        :type count: int

        :param from_id: ID of transaction from which response start (default 0)
        :type from_id: int

        :param end_id: ID of trnsaction at which response finishes (default inf)
        :type end_id: int

        :param order: Sorting order, 'ASC' for ascending and 'DESC' for descending
        :type order: str

        :param since: The time to start the display (unix time, default 0)
        :type since: int, None

        :param end: The time to end the display (unix time, default inf)
        :type end: int, None

        :return: List of transactions
        :rtype : dict

        """
        options = {
            'pair': pair.lower(),
            'from': from_start,
            'count': count,
            'from_id': from_id,
            'end_id': end_id,
            'order': order
        }

        if since:
            options['since'] = int(since)

        if end:
            options['end'] = int(end)

        obj = self.__query_trade_api('TradeHistory', options)
        return obj

    def get_deposit_address(self, coin_name, need_new=False):
        """
        Used to get deposit address.

        :param coin_name: The name of a coin, example 'BTC'
        :type coin_name: str

        :param need_new: True or False
        :type need_new: bool

        :return: Wallet address
        :rtype : dict

        """
        options = {'coinName': coin_name, 'need_new': 1 if need_new else 0}
        obj = self.__query_trade_api('GetDepositAddress', options)
        return obj

    def withdraw_coins_to_address(self, coin_name, amount, address):
        """
        Used to create withdrawal request.

        :param coin_name: The name of a coin, example 'BTC'
        :type coin_name: str

        :param amount: Amount to withdraw
        :type amount: float

        :param address: Destination address
        :type address: str

        :return: Success and server time
        :rtype : dict

        """
        options = {'coinName': coin_name, 'amount': amount, 'address': address}
        obj = self.__query_trade_api('WithdrawCoinsAddress', options)
        return obj


# Example
if __name__ == "__main__":
    print("Class YobitAPI. version:", __version__)
