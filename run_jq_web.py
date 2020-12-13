# coding: utf-8
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from tornado.options import define, options, parse_command_line
from tornado.web import RequestHandler, Application
from tornado.web import StaticFileHandler
from czsc import KlineAnalyze
import os
import pickle
import czsc
import json
import requests
import warnings
import pandas as pd
from datetime import datetime

url = "https://dataapi.joinquant.com/apis"
home_path = os.path.expanduser("~")
file_token = os.path.join(home_path, "jq.token")

assert czsc.__version__ == "0.5.8", "当前 czsc 版本为 {}，请升级为 0.5.8 版本".format(czsc.__version__)

def set_token(jq_mob, jq_pwd):
    """

    :param jq_mob: str
        mob是申请JQData时所填写的手机号
    :param jq_pwd: str
        Password为聚宽官网登录密码，新申请用户默认为手机号后6位
    :return:
    """
    pickle.dump([jq_mob, jq_pwd], open(file_token, 'wb'))


def get_token():
    """获取调用凭证"""
    if not os.path.exists(file_token):
        raise ValueError(f"{file_token} 文件不存在，请先调用 set_token 进行设置")

    jq_mob, jq_pwd = pickle.load(open(file_token, 'rb'))
    body = {
        "method": "get_current_token",
        "mob": jq_mob,  # mob是申请JQData时所填写的手机号
        "pwd": jq_pwd,  # Password为聚宽官网登录密码，新申请用户默认为手机号后6位
    }
    response = requests.post(url, data=json.dumps(body))
    token = response.text
    return token


def text2df(text):
    rows = [x.split(",") for x in text.strip().split('\n')]
    df = pd.DataFrame(rows[1:], columns=rows[0])
    return df


def get_kline(symbol,  end_date: datetime, freq: str, start_date: datetime = None, count=None):
    """获取K线数据

    :param symbol: str
        聚宽标的代码
    :param start_date: datetime
        截止日期
    :param end_date: datetime
        截止日期
    :param freq: str
        K线级别
    :param count: int
        K线数量，最大值为 5000
    :return: pd.DataFrame

    >>> start_date = datetime.strptime("20200701", "%Y%m%d")
    >>> end_date = datetime.strptime("20200719", "%Y%m%d")
    >>> df1 = get_kline(symbol="000001.XSHG", start_date=start_date, end_date=end_date, freq="1min")
    >>> df2 = get_kline(symbol="000001.XSHG", end_date=end_date, freq="1min", count=1000)
    """
    if count and count > 5000:
        warnings.warn(f"count={count}, 超过5000的最大值限制，仅返回最后5000条记录")

    # 1m, 5m, 15m, 30m, 60m, 120m, 1d, 1w, 1M
    freq_convert = {"1min": "1m", "5min": '5m', '15min': '15m',
                    "30min": "30m", "60min": '60m', "D": "1d", "W": '1w'}
    if start_date:
        data = {
            "method": "get_price_period",
            "token": get_token(),
            "code": symbol,
            "unit": freq_convert[freq],
            "date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            # "fq_ref_date": end_date
        }
    elif count:
        data = {
            "method": "get_price",
            "token": get_token(),
            "code": symbol,
            "count": count,
            "unit": freq_convert[freq],
            "end_date": end_date.strftime("%Y-%m-%d"),
            # "fq_ref_date": end_date
        }
    else:
        raise ValueError("start_date 和 count 不能同时为空")

    r = requests.post(url, data=json.dumps(data))
    df = text2df(r.text)
    df['symbol'] = symbol
    df.rename({'date': 'dt', 'volume': 'vol'}, axis=1, inplace=True)
    df = df[['symbol', 'dt', 'open', 'close', 'high', 'low', 'vol']]
    for col in ['open', 'close', 'high', 'low', 'vol']:
        df.loc[:, col] = df[col].apply(lambda x: round(float(x), 2))
    df.loc[:, "dt"] = pd.to_datetime(df['dt'])
    return df


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
        results = {"msg": "success", "basic": None}
        self.write(json.dumps(results, ensure_ascii=False))


class KlineHandler(BaseHandler):
    """K 线"""
    def get(self):
        ts_code = self.get_argument('ts_code')
        freq = self.get_argument('freq')
        trade_date = self.get_argument('trade_date')
        if trade_date == 'null':
            trade_date = datetime.now().date()
        else:
            trade_date = datetime.strptime(trade_date, "%Y%m%d")
        kline = get_kline(symbol=ts_code, end_date=trade_date, freq=freq, count=5000)
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

# 查看聚宽标的编码规范
# https://www.joinquant.com/help/api/help?name=JQData#%E8%8E%B7%E5%8F%96%E6%A0%87%E7%9A%84%E5%9F%BA%E6%9C%AC%E4%BF%A1%E6%81%AF

# 使用聚宽数据，只需要给出正确的标的代码，支持股票和期货，有实时数据，不需要设置 asset 参数
# http://localhost:8005/?ts_code=000001.XSHG&trade_date=20201121&freqs=1min


# 聚宽期货数据：https://www.joinquant.com/help/api/help?name=Future
#
# ```
# 交易市场	        代码后缀	    示例代码	        证券简称
# 上海证券交易所	.XSHG	    '600519.XSHG'	贵州茅台
# 深圳证券交易所	.XSHE	    '000001.XSHE'	平安银行
# 中金所	        .CCFX	    'IC9999.CCFX'	中证500主力合约
# 大商所	        .XDCE	    'A9999.XDCE'	豆一主力合约
# 上期所	        .XSGE	    'AU9999.XSGE'	黄金主力合约
# 郑商所	        .XZCE	    'CY8888.XZCE'	棉纱期货指数
# 上海能源交易所	.XINE	    'SC9999.XINE'	原油主力合约
# ```

