# coding: utf-8
import json
import pandas as pd
from czsc import KlineAnalyze
from datetime import datetime, timedelta
from flask import Flask, request, make_response, jsonify
from tqsdk import TqApi

app = Flask(__name__, static_folder="./web")

# api = TqApi(_stock=True)  # 支持股票数据
api = TqApi()


def format_kline(kline):
    """格式化K线"""
    def __convert_time(t):
        try:
            dt = datetime.utcfromtimestamp(t/1000000000)
            dt = dt + timedelta(hours=8)    # 中国默认时区
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return ""

    kline['dt'] = kline['datetime'].apply(__convert_time)
    kline['vol'] = kline['volume']
    columns = ['symbol', 'dt', 'open', 'close', 'high', 'low', 'vol']
    df = kline[columns]
    df = df.dropna(axis=0)
    df.drop_duplicates(subset=['dt'], inplace=True)
    df.sort_values('dt', inplace=True, ascending=True)
    df.reset_index(drop=True, inplace=True)
    return df


def get_kline(symbol="SHFE.cu2002", freq='1min', k_count=3000):
    """获取K线"""
    freq_map = {'1min': 60, '5min': 300, '15min': 900, '30min': 1800,
                '60min': 3600, 'D': 3600*24, 'W': 86400*7}
    df = api.get_kline_serial(symbol, duration_seconds=freq_map[freq], data_length=k_count)
    df = format_kline(df)
    print(df.head(), df.shape)
    return df


@app.route('/', methods=['GET'])
def index():
    return app.send_static_file('index.html')


@app.route('/kline', methods=['POST', 'GET'])
def kline():
    if request.method == "POST":
        data = json.loads(request.get_data(as_text=True))
    elif request.method == "GET":
        data = request.args
    else:
        raise ValueError
    print(data)
    ts_code = data.get('ts_code')
    freq = data.get('freq')
    k = get_kline(symbol=ts_code, freq=freq, k_count=5000)
    ka = KlineAnalyze(k, bi_mode="new", xd_mode='strict')
    k = pd.DataFrame(ka.kline)
    k = k.fillna("")
    columns = ["dt", "open", "close", "low", "high", "vol", 'fx_mark', 'fx', 'bi', 'xd']
    res = make_response(jsonify({'kdata': k[columns].values.tolist()}))
    res.headers['Access-Control-Allow-Origin'] = '*'
    res.headers['Access-Control-Allow-Method'] = '*'
    res.headers['Access-Control-Allow-Headers'] = '*'
    return res


if __name__ == '__main__':
    app.run(port=8005, debug=True)



