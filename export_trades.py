import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from algo_trader import AlgoTrader

class ExportTrades:
    def __init__(self, pair:str, strategy_name:str, file_format:str, since_days:int, filename:str) -> None:
        load_dotenv()
        self.BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
        self.BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
        self.SLACK_TOKEN = os.getenv('SLACK_TOKEN')
        self.exchange = AlgoTrader.exchange_connection()

        self.pair = pair
        self.strategy_name = strategy_name
        self.file_format = file_format
        self.since_days = since_days
        self.filename = filename

        self.path_to_save =  os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'AlgoTrader', 'trades', f'{self.file_format}')
        self.trade_list = []

        self.timestamp_difference_for_24h = 86400000
        self.current_timestamp = int(datetime.timestamp(datetime.strptime(str(datetime.now()).split('.')[0], '%Y-%m-%d %H:%M:%S'))) * 1000
        self.since = self.current_timestamp - (self.timestamp_difference_for_24h * self.since_days)


    def fetch_trades_through_exchange(self):
        '''
        Summary: Binance api returns following 7 days trades according to since parameter. So, if more trades needed the function iterates until current timestamp and fetches all trades then returns them
        :return: trades
        '''
        since = self.since
        trades = self.exchange.fetch_my_trades(symbol=self.pair, since=since)
        try:
            since = int(trades[-1]['timestamp']) + 1
        except IndexError:
            since += (self.timestamp_difference_for_24h * 6)

        while since < self.current_timestamp:
            try:
                trades2 = self.exchange.fetch_my_trades(symbol=self.pair, since=since)
                trades = trades + trades2
            except:
                break
            try:
                since = int(trades2[-1]['timestamp']) + 1
            except IndexError:
                since += (self.timestamp_difference_for_24h * 6)
                if since >= self.current_timestamp:
                    break
        return trades
    

    def format_trades_list(self, trades:list):
        '''
        Summary: Edits the trades list for excel and csv file.
        - trades (list): trades list which is created by fetch_trades_through_exchange function.
        '''
        for trade in trades:
            trade['strategy_name'] = self.strategy_name
            info_dict = trade['info']
            del trade['info']

            fee = trade['fee']['cost']
            del trade['fee']
            del trade['fees']
            trade['fee'] = fee

            trade_dict = {**trade, **info_dict}
            self.trade_list.append(trade_dict)


    def export(self):
        '''
        Summary: Export trades into file acording to the given format.
        '''
        df = pd.DataFrame(self.trade_list)
        if self.file_format.lower() == 'excel':
            df.to_excel(f'{self.path_to_save}/{self.filename}.xlsx', index=False)
        elif self.file_format.lower() == 'csv':
            df.to_csv(f'{self.path_to_save}/{self.filename}.csv', index=False)
        elif self.file_format.lower == 'json':
            df.to_json(f'{self.path_to_save}/{self.filename}.json', index=False)
        else:
            print('Error - Invalid file format!')
        print(f'Trades exported into {self.filename} named file!')
        

if __name__ == '__main__':
    exporter = ExportTrades(pair='BTC/USDT', strategy_name='super_mfi_rsi', file_format='csv', since_days=30, filename='super_mfi_rsi_trades')
    trades = exporter.fetch_trades_through_exchange()
    exporter.format_trades_list(trades=trades)
    exporter.export()

