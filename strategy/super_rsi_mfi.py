import os
import sys

# set the path as main directory's path for imports
main_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
__path__ = [main_path]
sys.path += __path__

from algo_trader import AlgoTrader
from datetime import datetime
import talib
import numpy as np
import pandas as pd
import traceback
import pandas_ta
import logging

class SuperRSIMFI:
    def __init__(self, open_prices:list, high_prices:list, low_prices:list, close_prices:list, volumes:list) -> None:
        self.open_prices = open_prices
        self.high_prices = high_prices
        self.low_prices = low_prices
        self.close_prices = close_prices
        self.volumes = volumes

        self.rsi = None
        self.mfi = None
        self.st_price = None
        self.multiplier = 10
        self.length = 30
    
    def calculate_rsi(self):
        self.rsi = talib.RSI(np.array(self.close_prices), timeperiod=7)
        return self.rsi[-1]
    
    def calculate_mfi(self):
        self.mfi = talib.MFI(np.array(self.high_prices), np.array(self.low_prices), np.array(self.close_prices), np.array(self.volumes), timeperiod=7)
        return self.mfi[-1]
    
    def calculate_supertrend(self):
        df = pd.DataFrame({'open':self.open_prices, 'high':self.high_prices, 'low':self.low_prices, 'close':self.close_prices})
        st_df = pd.DataFrame(pandas_ta.supertrend(high=df['high'], low=df['low'], close=df['close'], length=self.length, multiplier=self.multiplier)[f'SUPERT_{self.length}_{self.multiplier}.0'])
        self.st_price = float(st_df[f'SUPERT_{self.length}_{self.multiplier}.0'][-1])
        return self.st_price
    

if __name__ == '__main__':
    last_minute = None
    minutes = [x for x in range(0, 60) if x % 5 == 1]
    trader = AlgoTrader(pair='BTC/USDT', position_size=0.001, interval='5m')

    while True:
        try:
            minute = datetime.now().minute
            if minute in minutes and minute != last_minute:
                last_minute = minute
                df_ohlcv = trader.fetch_OHLCV(limit=500, timeframe='5m')
                open_prices = list(df_ohlcv['open'])
                high_prices = list(df_ohlcv['high'])
                low_prices = list(df_ohlcv['low'])
                close_prices = list(df_ohlcv['close'])
                volumes = list(df_ohlcv['volume'])

                strategy = SuperRSIMFI(open_prices=open_prices, high_prices=high_prices, low_prices=low_prices, close_prices=close_prices, volumes=volumes)
                rsi = strategy.calculate_rsi()
                mfi = strategy.calculate_mfi()
                st_price = strategy.calculate_supertrend()

                logging.info(f'Close: {close_prices[-1]} - Super Trend Price: {st_price} - RSI: {rsi} - MFI: {mfi}')

                if st_price < close_prices[-1]:
                    # bullish market, open long, close shorts
                    trader.close_positions(side='short')
                    if rsi < 30 and mfi > 55:
                        trader.send_market_order(side='long', SL=10, TP=10)

                elif st_price > close_prices[-1]:
                    # bearish market, open short, close longs
                    trader.close_positions(side='long')
                    if rsi > 70 and mfi > 55:
                        trader.send_market_order(side='short', SL=10, TP=10)

        except Exception as e:
            logging.error(f'An exception occured when trading! Exception: {e}')

        except KeyboardInterrupt:
            error_message = str(traceback.format_exc())
            trader.exit(message=error_message)
            break