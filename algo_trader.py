import ccxt
import pandas as pd
import os
import time
from dotenv import load_dotenv
import logging
import slack

class AlgoTrader:
    def __init__(self, pair:str, position_size:float, interval:str) -> None:
        load_dotenv()
        self.BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
        self.BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
        self.SLACK_TOKEN = os.getenv('SLACK_TOKEN')

        self.exchange = self.exchange_connection()
        self.pair = pair
        self.position_size = position_size
        self.interval = interval
        self.market_fee = 0.0005

    
    def exchange_connection(self) -> ccxt.binance:
        '''
        Summary: Attempts to connect to the exchange using exchange's api key and secret key until the connection is successfuly established.
        :return: ccxt.binance object
        '''
        while True:
            try:
                exchange = ccxt.binance({'enableRateLimit':True, 'apiKey':self.BINANCE_API_KEY, 'secret':self.BINANCE_SECRET_KEY, 'options':{'defaultType':'future'}})
                logging.info('connected to the exchange successfuly!')
                break
            except Exception as e:
                logging.error(str(e))
                time.sleep(1)
        return exchange
    

    def balance_availability(self, entry_price) -> bool:
        '''
        Summary: Checks the balance availability through exchange and returns boolean
        :return: bool
        '''
        balance = self.exchange.fetch_balance()['USDT']['free']
        if float(balance) > (entry_price * self.position_size + (entry_price * self.market_fee * self.position_size)):
            logging.info('Wallet balance is enough to open position.')
            return True
        elif float(balance) < (entry_price * self.position_size + (entry_price * self.market_fee * self.position_size)):
            logging.info('Insufficient balance!')
            return False
        
    
    def fetch_OHLCV(self, since:int=None, limit:int=None, timeframe:str=None) -> pd.DataFrame:
        '''
        Summary: Fetches the Open, High, Low, Close, Volume data of initalized pair and returns the data as DataFrame
        - since (int): Unix timestamp(ms) of start date
        - limit (int): Number of candles (max=1500)
        - timeframe (str): candles frequency (Example: 1m, 3m, 15m, 1h etc.)
        :return: price data as DataFrame
        '''
        try:
            df_ohlcv = self.exchange.fetch_ohlcv(symbol=self.symbol, timeframe=timeframe, limit=limit, since=since)
            df_ohlcv = pd.DataFrame(df_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            logging.info('Fetched the OHLCV data successfuly...')
        except Exception as e:
            logging.error(f'An exception occured when fetching the OHLCV data! Exception: {e}')
        return df_ohlcv
    

    def fetch_entry_price(self) -> float:
        '''
        :returns last order's average entry price as float
        '''
        try:
            entry_price = float(self.exchange.fetch_orders(symbol=self.symbol)[-1]['average'])
        except Exception as e:
            logging.error(f'An exception occured when fetching the last orders entry price! Exception: {e}')
        return entry_price
    

    def fetch_last_candle(self):
        '''
        Summary: Fetches last candles data then returns open, high, low, close
        :return close price
        '''
        try:
            ticker = self.exchange.fetch_ticker(symbol=self.symbol)
            open_price = float(ticker['info']['openPrice'])
            close_price = float(ticker['info']['lastPrice'])
            high_price = float(ticker['info']['highPrice'])
            low_price = float(ticker['info']['lowPrice'])
        except Exception as e:
            logging.error(f'An exception occured when fetching the OHLCV data! Exception: {e}')
        return open_price, high_price, low_price, close_price
    

    def calculate_stop_order_prices(self, side:str, SL:float=None, TP:float=None):
        '''
        Summary: Calculates the stop orders prices according to given side and Stop Loss & Take Profit percentages.
        - side (str): side of the position (long or short)
        - SL (float): Stop Loss percentage
        - TP (float): Take Profit percentage
        :return: Stop Loss price and Take Profit prices
        '''
        sl, tp = None, None
        price = self.fetch_entry_price()
        if SL is not None:
            if side.lower() == 'long':
                sl = price - (price * (SL / 100))
            elif side.lower() == 'short':
                sl = price + (price * (SL / 100))

        if TP is not None:
            if side.lower() == 'long':
                tp = price + (price * (TP / 100))
            elif side.lower() == 'short':
                tp = price - (price * (TP / 100))
        return sl, tp
        
    
    def send_market_order(self, side:str, action:str='OPEN', SL:float=None, TP:float=None, amount:float=None):
        '''
        Summary: Sends an market order to the exchange according to the given parameters. The function can be used for opening and closing positions.
        -
        '''
        position_size = self.position_size
        if amount is not None:
            position_size = amount

        open_price, high_price, low_price, close_price = self.fetch_last_candle()

        is_balance_enough = self.balance_availability(entry_price=close_price)
        if action.upper() == 'CLOSE':
            is_balance_enough = True    # balance is not important when closing position

        if is_balance_enough:
            if side.lower() == 'long':
                try:
                    self.exchange.create_market_buy_order(symbol=self.pair, amount=position_size)
                    time.sleep(2)
                    entry_price = self.fetch_entry_price()
                    logging.info(f'{action} {side} - Entry Price: {entry_price} - Amount: {position_size}')
                except Exception as e:
                    logging.error(f'An exception occured when sending market buy order! Exception: {e}')
            elif side.lower() == 'short':
                try:
                    self.exchange.create_market_sell_order(symbol=self.pair, amount=position_size)
                    time.sleep(2)
                    entry_price = self.fetch_entry_price()
                    logging.info(f'{action} {side} - Entry Price: {entry_price} - Amount: {position_size}')
                except Exception as e:
                    logging.error(f'An exception occured when sending market sell order! Exception: {e}')

            # send stop orders if exists
            sl_price, tp_price = self.calculate_stop_order_prices(side=side, SL=SL, TP=TP)
            if SL != None:
                sl_params = {'stopLossPrice':sl_price}
                if side.lower() == 'long':
                    self.exchange.create_market_sell_order(symbol=self.pair, amount=position_size, params=sl_params)
                elif side.lower() == 'short':
                    self.exchange.create_market_buy_order(symbol=self.pair, amount=position_size, params=sl_params)
                logging.info(f'SL Price: {sl_price} - Side: {side} - Amount: {amount}')
            elif TP != None:
                tp_params = {'takeProfitPrice':tp_price}
                if side.lower() == 'long':
                    self.exchange.create_market_sell_order(symbol=self.pair, amount=position_size, params=tp_params)
                elif side.lower() == 'short':
                    self.exchange.create_market_buy_order(symbol=self.pair, amount=position_size, params=tp_params)
                logging.info(f'TP Price: {tp_price} - Side: {side} - Amount: {amount}')


    def close_positions(self, side:str):
        '''
        Summary: calculates the total open positions' size according to the side, size info then closes them all
        - side (str): trades side (long or short)
        '''
        open_position_size = abs(float(self.exchange.fetch_positions(symbols=[self.symbol])[0]['info']['positionAmt']))
        if side.lower() == 'long':
            try:
                self.send_market_order(side='short', action='CLOSE', amount=open_position_size)
                logging.info(f'CLOSE {side} - Position Size: {open_position_size}')
            except Exception as e:
                logging.error(f'An exception occured when closing the long positions! Exception: {e}')
        elif side.lower() == 'short':
            try:
                self.send_market_order(side='long', action='CLOSE', amount=open_position_size)
                logging.info(f'CLOSE {side} - Position Size: {open_position_size}')
            except Exception as e:
                logging.error(f'An exception occured when closing the short positions! Exception: {e}')


    def cancel_all_orders(self) -> None:
        '''
        Summary: cancels all open orders
        '''
        try:
            self.exchange.cancel_all_orders(symbol=self.symbol)
            logging.info(f'CANCEL ALL ORDERS')
        except Exception as e:
            logging.error(f'An exception occured when canceling open orders! Exception: {e}')


    def send_info_to_slack_channel(self, message:str='The bot has been stopped!'):
        '''
        Summary: Sends the given message to the Slack channel.
        '''
        try:
            client = slack.WebClient(token=self.SLACK_TOKEN)
            client.chat_postMessage(channel='#trade_bot', text=message)
            logging.info('Message sent successfuly to the Slack channel!')
        except Exception as e:
            logging.error(f'An exception occured when sending the message to the Slack channel! Exception: {e}')


    def exit(self, message:str=None):
        '''
        Summary: When the program receives an error and stops running exit function runs to close the bot safely. 
        - gives option to the user to cancel open orders and close open positions
        '''
        self.send_info_to_slack_channel(message=message)
        
        order_choice = input('cancel open orders? (y/n): ')
        if order_choice.lower() == 'y':
            self.cancel_all_orders()
        elif order_choice.lower == 'n':
            pass
        else:
            logging.error('Invalid choice! Order(s) (if exists) are remained open!')

        position_choice = input('close open positions? (y/n): ')
        if position_choice.lower() == 'y':
            self.close_positions(side='long')
            self.close_positions(side='short')
        elif position_choice.lower() == 'n':
            pass
        else:
            logging.error('Invalid choice! Position(s) (if exists) are remained open!')