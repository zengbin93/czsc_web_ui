# 缠中说禅技术分析工具网页

使用 Tushare Pro / 聚宽 / 掘金 / 天勤 的数据进行缠中说禅技术分析结果展示

## 启动方法

1. 执行 `pip install -r requirements.txt` 安装环境
2. 确定所要使用的数据源，完成相关设置
3. 执行对应的数据源的脚本启动服务，不要改端口！！！

     `python run_ts_web.py`  - 启动使用 `Tushare Pro` 数据的前端页面
     
     `python run_jq_web.py`  - 启动使用 `聚宽` 数据的前端页面
     
     `python run_gm_web.py`  - 启动使用 `掘金` 数据的前端页面
     
     `python run_tq_web.py`  - 启动使用 `天勤` 数据的前端页面

启动后在本地 8005 端口访问服务，在对应的脚本中可以看到示例；
其中，ts_code 为对应的标的代码；trade_date 为交易日期，freqs 为K线周期



