# coding: utf-8

import czsc
import json
import os
import time
import pandas as pd
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from tornado.options import define, options, parse_command_line
from tornado.web import RequestHandler, Application
from tornado.web import StaticFileHandler
import tushare as ts
from datetime import datetime, timedelta
import czsc
from czsc import KlineAnalyze

# 首次使用，需要在这里设置你的 tushare token，用于获取数据；在同一台机器上，tushare token 只需要设置一次
# 没有 token，到 https://tushare.pro/register?reg=7 注册获取
# ts.set_token("your tushare token")

assert czsc.__version__ == "0.5.8", "当前 czsc 版本为 {}，请升级为 0.5.8 版本".format(czsc.__version__)


def _get_start_date(end_date, freq):
    end_date = datetime.strptime(end_date, '%Y%m%d')
    if freq == '1min':
        start_date = end_date - timedelta(days=60)
    elif freq == '5min':
        start_date = end_date - timedelta(days=150)
    elif freq == '30min':
        start_date = end_date - timedelta(days=1000)
    elif freq == 'D':
        start_date = end_date - timedelta(weeks=1000)
    elif freq == 'W':
        start_date = end_date - timedelta(weeks=1000)
    else:
        raise ValueError("'freq' value error, current value is %s, "
                         "optional valid values are ['1min', '5min', '30min', "
                         "'D', 'W']" % freq)
    return start_date


def get_kline(ts_code, end_date, freq='30min', asset='E'):
    """获取指定级别的前复权K线

    :param ts_code: str
        股票代码，如 600122.SH
    :param freq: str
        K线级别，可选值 [1min, 5min, 15min, 30min, 60min, D, M, Y]
    :param end_date: str
        日期，如 20190610
    :param asset: str
        交易资产类型，可选值 E股票 I沪深指数 C数字货币 FT期货 FD基金 O期权 CB可转债（v1.2.39），默认E
    :return: pd.DataFrame
        columns = ["symbol", "dt", "open", "close", "high", "low", "vol"]
    """
    start_date = _get_start_date(end_date, freq)
    start_date = start_date.date().__str__().replace("-", "")
    end_date = datetime.strptime(end_date, '%Y%m%d')
    end_date = end_date + timedelta(days=1)
    end_date = end_date.date().__str__().replace("-", "")

    df = ts.pro_bar(ts_code=ts_code, freq=freq, start_date=start_date, end_date=end_date,
                    adj='qfq', asset=asset)

    # 统一 k 线数据格式为 6 列，分别是 ["symbol", "dt", "open", "close", "high", "low", "vr"]
    if "min" in freq:
        df.rename(columns={'ts_code': "symbol", "trade_time": "dt"}, inplace=True)
    else:
        df.rename(columns={'ts_code': "symbol", "trade_date": "dt"}, inplace=True)

    df.drop_duplicates(subset='dt', keep='first', inplace=True)
    df.sort_values('dt', inplace=True)
    df['dt'] = df.dt.apply(str)
    if freq.endswith("min"):
        # 清理 9:30 的空数据
        df['not_start'] = df.dt.apply(lambda x: not x.endswith("09:30:00"))
        df = df[df['not_start']]
    df.reset_index(drop=True, inplace=True)

    k = df[['symbol', 'dt', 'open', 'close', 'high', 'low', 'vol']]

    for col in ['open', 'close', 'high', 'low']:
        k[col] = k[col].apply(round, args=(2,))
    return k


def get_stock_basic(ts_code=None):
    """获取股票的基本信息"""
    file_cache = "stock_basic.csv"
    if os.path.exists(file_cache) and time.time() - os.path.getmtime(file_cache) < 3600:
        df = pd.read_csv(file_cache, dtype={"list_date": str}, encoding="utf-8")
    else:
        pro = ts.pro_api()
        df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,area,industry,list_date')
        df.to_csv(file_cache, index=False, encoding="utf-8")

    if not ts_code:
        return df
    else:
        share = df[df["ts_code"] == ts_code].iloc[0].to_dict()
        return share


# 端口固定为 8005，不可以调整
define('port', type=int, default=8005, help='服务器端口')
current_path = os.path.dirname(__file__)


class BaseHandler(RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")  # 这个地方可以写域名
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

    def post(self):
        self.write('some post')

    def get(self):
        self.write('some get')

    def options(self):
        self.set_status(204)
        self.finish()


class BasicHandler(BaseHandler):
    """股票基本信息"""
    def get(self):
        ts_code = self.get_argument('ts_code')
        basic = get_stock_basic(ts_code)
        basic['symbol'] = basic['ts_code']
        results = {"msg": "success", "basic": [basic]}
        self.write(json.dumps(results, ensure_ascii=False))


class KlineHandler(BaseHandler):
    """K 线"""
    def get(self):
        ts_code = self.get_argument('ts_code')
        freq = self.get_argument('freq')
        asset = self.get_argument('asset', "E")
        trade_date = self.get_argument('trade_date')
        if trade_date == 'null':
            trade_date = datetime.now().date().__str__().replace("-", "")
        kline = get_kline(ts_code=ts_code, end_date=trade_date, freq=freq, asset=asset)
        kline.loc[:, "dt"] = pd.to_datetime(kline.dt)

        ka = KlineAnalyze(kline, bi_mode="new", verbose=False, use_xd=True, max_count=5000)
        kline = ka.to_df(ma_params=(5, 20), use_macd=True, max_count=5000, mode='new')
        kline = kline.fillna("")
        kline.loc[:, "dt"] = kline.dt.apply(str)
        columns = ["dt", "open", "close", "low", "high", "vol", 'fx_mark', 'fx', 'bi', 'xd']

        self.finish({'kdata': kline[columns].values.tolist()})


if __name__ == '__main__':
    parse_command_line()
    app = Application([
            ('/kline', KlineHandler),
            ('/basic', BasicHandler),
            (r'^/(.*?)$', StaticFileHandler, {"path": os.path.join(current_path, "web"),
                                              "default_filename": "index.html"}),
        ],
        static_path=os.path.join(current_path, "web"),
        dubug=True
    )
    http_server = HTTPServer(app)
    http_server.listen(options.port)
    IOLoop.current().start()


# http://localhost:8005/?ts_code=000001.SH&asset=I&trade_date=20200613&freqs=D,30min,5min,1min

