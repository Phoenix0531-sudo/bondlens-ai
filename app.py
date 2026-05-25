import pandas as pd  # 导入pandas库，用于数据处理和分析
import numpy as np  # 导入numpy库，用于数值计算
from statsmodels.tsa.statespace.sarimax import SARIMAX  # 导入SARIMAX模型
from flask import abort, flash, Flask, jsonify, redirect, render_template, request, session  # 导入Flask及其相关模块，用于创建Web应用
import plotly.graph_objects as go  # 导入plotly.graph_objects，用于创建图表
from plotly.subplots import make_subplots  # 导入make_subplots，用于创建子图
from datetime import datetime, timedelta  # 导入datetime和timedelta，用于日期和时间处理
import json  # 导入json模块，用于处理JSON数据
import random  # 导入random模块，用于生成随机数

from ta.momentum import RSIIndicator  # 导入RSIIndicator，用于计算相对强弱指标
from ta.volatility import BollingerBands  # 导入BollingerBands，用于计算布林带
from scipy.stats import zscore  # 导入zscore，用于计算Z-Score
from sklearn.model_selection import train_test_split  # 导入train_test_split，用于数据集划分
from sklearn.ensemble import RandomForestRegressor  # 导入RandomForestRegressor，用于随机森林回归模型
from function import hash_code  # 导入自定义函数hash_code，用于密码哈希
import sqlite3  # 导入sqlite3模块，用于SQLite数据库操作
import os  # 导入os模块，用于操作系统相关功能

app = Flask(__name__)  # 创建Flask应用实例
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')  # 设置会话密钥，生产环境应从环境变量读取
DB_PATH = os.environ.get('DATABASE_PATH', 'db.db')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS USER (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            USERNAME TEXT NOT NULL UNIQUE,
            PASSWORD TEXT NOT NULL,
            college TEXT,
            gender TEXT,
            cet_score TEXT
        )
        '''
    )
    conn.commit()
    conn.close()


init_db()

# 读取Excel数据
def load_data():
    return pd.read_excel('data/testdata.xlsx', header=1)  # 读取Excel文件，并从第二行开始读取数据

# 计算移动平均线
def moving_average(data, window):
    return data.rolling(window=window).mean()  # 计算指定窗口大小的移动平均线

# 计算MACD指标
def macd(data, short_period, long_period, signal_period):
    short_ema = data.ewm(span=short_period, adjust=False).mean()  # 计算短期指数移动平均线
    long_ema = data.ewm(span=long_period, adjust=False).mean()  # 计算长期指数移动平均线
    macd_line = short_ema - long_ema  # 计算MACD线
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()  # 计算信号线
    return macd_line, signal_line  # 返回MACD线和信号线

# 数据预测
def predict(data, steps=30):
    model = SARIMAX(data, order=(5, 1, 0), seasonal_order=(1, 1, 1, 12))
    model_fit = model.fit()
    forecast = model_fit.forecast(steps=steps)
    return forecast

@app.route('/')  # 定义根路由
def index():
    return render_template('login.html')  # 渲染登录页面

@app.route('/home')  # 定义/home路由
def index2():
    return render_template('index.html')  # 渲染主页

@app.route('/api/adduser', methods=['GET', 'POST'])  # 定义添加用户的API路由
def add_user():
    if request.json:  # 判断请求是否为JSON格式
        username = request.json.get('username', '').strip()  # 获取并去除用户名两端空格
        password = request.json.get('password')  # 获取密码
        confirm_password = request.json.get('confirm')  # 获取确认密码
        # 判断所有输入都不为空
        if username and password and confirm_password:
            if password != confirm_password:
                return jsonify({'code': '400', 'msg': '两次密码不匹配！'}), 400  # 如果密码不匹配，返回错误信息
            # 连接数据库
            conn = sqlite3.connect(DB_PATH)  # 连接SQLite数据库
            cur = conn.cursor()  # 创建游标
            # 查询输入的用户名是否已经存在
            sql_same_user = 'SELECT 1 FROM USER WHERE USERNAME=?'
            same_user = cur.execute(sql_same_user, (username,)).fetchone()  # 执行查询
            if same_user:
                return jsonify({'code': '400', 'msg': '用户名已存在'}), 400  # 如果用户名已存在，返回错误信息
            # 通过检查的数据，插入数据库表中
            sql_insert_user = 'INSERT INTO USER(USERNAME, PASSWORD) VALUES (?,?)'
            cur.execute(sql_insert_user, (username, hash_code(password)))  # 插入新用户数据
            conn.commit()  # 提交事务
            sql_new_user = 'SELECT id,username FROM USER WHERE USERNAME=?'
            user_id, user = cur.execute(sql_new_user, (username,)).fetchone()  # 获取新用户的ID和用户名
            conn.close()  # 关闭数据库连接
            return jsonify({'code': '200', 'msg': '账号生成成功！', 'newUser': {'id': user_id, 'user': user}})  # 返回成功信息
        else:
            return jsonify({'code': '404', 'msg': '请求参数不全!'})  # 如果请求参数不全，返回错误信息
    else:
        abort(400)  # 如果请求不是JSON格式，返回400错误

@app.route('/login', methods=['GET', 'POST'])  # 定义登录路由
def login():
    if request.method == 'POST':
        # 获取请求中的数据
        username = request.form.get('username')  # 获取用户名
        password = hash_code(request.form.get('password'))  # 获取并哈希密码

        # 连接数据库，判断用户名+密码组合是否匹配
        conn = sqlite3.connect(DB_PATH)  # 连接SQLite数据库
        cur = conn.cursor()  # 创建游标
        try:
            sql = 'SELECT college, gender, cet_score FROM USER WHERE USERNAME=? AND PASSWORD=?'
            user_info = cur.execute(sql, (username, password)).fetchone()  # 执行查询

        except:
            flash('用户名或密码错误！')  # 如果查询失败，显示错误信息
            return render_template('login.html')  # 渲染登录页面
        finally:
            conn.close()  # 关闭数据库连接

        if user_info is not None:
            session['is_login'] = True
            session['name'] = username
            return render_template('index.html')  # 如果查询结果不为空，渲染主页
        else:
            flash('用户名或密码错误！')  # 如果查询结果为空，显示错误信息
            return render_template('login.html')  # 渲染登录页面
    return render_template('login.html')  # 渲染登录页面

@app.route('/register', methods=['GET', 'POST'])  # 定义注册路由
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()  # 获取并去除用户名两端空格
        password = request.form.get('password')  # 获取密码
        confirm_password = request.form.get('confirm')  # 获取确认密码
        # 判断所有输入都不为空
        if username and password and confirm_password:
            if password != confirm_password:
                flash('两次输入的密码不一致！')  # 如果密码不匹配，显示错误信息
                return render_template('register.html', username=username)  # 渲染注册页面，并保留输入的用户名
            # 连接数据库
            conn = sqlite3.connect(DB_PATH)  # 连接SQLite数据库
            cur = conn.cursor()  # 创建游标
            # 查询输入的用户名是否已经存在
            sql_same_user = 'SELECT 1 FROM USER WHERE USERNAME=?'
            same_user = cur.execute(sql_same_user, (username,)).fetchone()  # 执行查询
            if same_user:
                flash('用户名已存在！')  # 如果用户名已存在，显示错误信息
                return render_template('register.html', username=username)  # 渲染注册页面，并保留输入的用户名
            # 通过检查的数据，插入数据库表中
            sql_insert_user = 'INSERT INTO USER(USERNAME, PASSWORD) VALUES (?,?)'
            cur.execute(sql_insert_user, (username, hash_code(password)))  # 插入新用户数据
            conn.commit()  # 提交事务
            conn.close()  # 关闭数据库连接
            # 重定向到登录页面
            return redirect('/login')  # 重定向到登录页面
        else:
            flash('所有字段都必须输入！')  # 如果所有字段都未输入，显示错误信息
            if username:
                return render_template('register.html', username=username)  # 渲染注册页面，并保留输入的用户名
            return render_template('register.html')  # 渲染注册页面
    return render_template('register.html')  # 渲染注册页面

@app.route('/logout')  # 定义登出路由
def logout():
    # 退出登录，清空session
    if session.get('is_login'):
        session.clear()  # 清空会话
        return redirect('/')  # 重定向到根页面
    return redirect('/')  # 重定向到根页面

@app.route('/visualize')  # 定义数据可视化路由
def visualize():
    data = load_data()  # 读取数据

    # 数据预处理
    data['收盘到期收益率(%)'] = pd.to_numeric(data['收盘到期收益率(%)'], errors='coerce')  # 将列转换为数值类型
    data.dropna(subset=['收盘到期收益率(%)'], inplace=True)  # 删除包含NaN的行

    # 添加 Z-Score 清洗步骤
    data['Z-Score'] = zscore(data['收盘到期收益率(%)'])  # 计算 Z-Score
    data = data[(data['Z-Score'].abs() <= 3)]  # 删除 Z-Score 绝对值大于 3 的行
    data.drop(columns=['Z-Score'], inplace=True)  # 删除 Z-Score 列

    # 描述性统计分析
    stats = data['收盘到期收益率(%)'].describe().round(2)  # 计算描述性统计量
    stats.index = ['样本数', '均值', '标准差', '最小值', '25%分位数', '中位数', '75%分位数', '最大值']  # 重命名索引

    # 生成时间序列
    start_date = datetime(2023, 1, 1)  # 设置开始日期
    end_date = datetime(2024, 12, 31)  # 设置结束日期
    dates = pd.date_range(start=start_date, end=end_date, periods=len(data))  # 生成日期范围
    data['日期'] = dates  # 添加日期列
    data.set_index('日期', inplace=True)  # 设置日期为索引

    # 技术分析
    ma_short = moving_average(data['收盘到期收益率(%)'], window=5)  # 计算5日移动平均线
    ma_long = moving_average(data['收盘到期收益率(%)'], window=20)  # 计算20日移动平均线
    macd_line, signal_line = macd(data['收盘到期收益率(%)'], short_period=12, long_period=26, signal_period=9)  # 计算MACD指标
    rsi_indicator = RSIIndicator(close=data['收盘到期收益率(%)'], window=14)  # 创建RSI指标实例
    rsi = rsi_indicator.rsi()  # 计算RSI

    bb_indicator = BollingerBands(close=data['收盘到期收益率(%)'], window=20, window_dev=2)  # 创建布林带实例
    upper_band = bb_indicator.bollinger_hband()  # 计算布林带上轨
    lower_band = bb_indicator.bollinger_lband()  # 计算布林带下轨

    # 创建图表1: 收盘到期收益率与移动平均线
    fig1 = go.Figure()
    fig1.add_trace(
        go.Scatter(x=data.index, y=data['收盘到期收益率(%)'], name='收盘到期收益率', line=dict(color='#1f77b4')))  # 添加收盘到期收益率线
    fig1.add_trace(go.Scatter(x=data.index, y=ma_short, name='5日移动平均线', line=dict(color='#ff7f0e')))  # 添加5日移动平均线
    fig1.add_trace(go.Scatter(x=data.index, y=ma_long, name='20日移动平均线', line=dict(color='#2ca02c')))  # 添加20日移动平均线
    fig1.update_layout(
        xaxis=dict(title='日期', tickformat='%Y-%m-%d', gridcolor='#f0f0f0', showgrid=True),  # 设置x轴属性
        yaxis=dict(title='收盘到期收益率(%)', gridcolor='#f0f0f0', showgrid=True),  # 设置y轴属性
        plot_bgcolor='#ffffff',  # 设置背景颜色
        legend=dict(x=0, y=1, orientation='h', bgcolor='#f0f0f0', bordercolor='#000000', borderwidth=1),  # 设置图例属性
        height=400,  # 设置图表高度
        margin=dict(l=50, r=50, t=50, b=50)  # 设置图表边距
    )
    fig1.update_xaxes(tickangle=-45, tickfont=dict(size=10), nticks=10)  # 更新x轴刻度属性

    # 创建图表2: MACD指标
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=data.index, y=macd_line, name='MACD', line=dict(color='#d62728')))  # 添加MACD线
    fig2.add_trace(go.Scatter(x=data.index, y=signal_line, name='Signal', line=dict(color='#9467bd')))  # 添加信号线
    fig2.update_layout(
        xaxis=dict(title='日期', tickformat='%Y-%m-%d', gridcolor='#f0f0f0', showgrid=True),  # 设置x轴属性
        yaxis=dict(title='MACD', gridcolor='#f0f0f0', showgrid=True),  # 设置y轴属性
        plot_bgcolor='#ffffff',  # 设置背景颜色
        legend=dict(x=0, y=1, orientation='h', bgcolor='#f0f0f0', bordercolor='#000000', borderwidth=1),  # 设置图例属性
        height=400,  # 设置图表高度
        margin=dict(l=50, r=50, t=50, b=50)  # 设置图表边距
    )
    fig2.update_xaxes(tickangle=-45, tickfont=dict(size=10), nticks=10)  # 更新x轴刻度属性

    # 创建图表3: 相对强弱指数(RSI)
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=data.index, y=rsi, name='RSI', line=dict(color='#9467bd')))  # 添加RSI线
    fig3.add_shape(
        type="line",
        x0=data.index[0],
        y0=30,
        x1=data.index[-1],
        y1=30,
        line=dict(color="#ffa500", width=2, dash="dash"),  # 添加30水平线
    )
    fig3.add_shape(
        type="line",
        x0=data.index[0],
        y0=70,
        x1=data.index[-1],
        y1=70,
        line=dict(color="#ffa500", width=2, dash="dash"),  # 添加70水平线
    )
    fig3.update_layout(
        xaxis=dict(title='日期', tickformat='%Y-%m-%d', gridcolor='#f0f0f0', showgrid=True),  # 设置x轴属性
        yaxis=dict(title='RSI', gridcolor='#f0f0f0', showgrid=True),  # 设置y轴属性
        plot_bgcolor='#ffffff',  # 设置背景颜色
        height=400,  # 设置图表高度
        margin=dict(l=50, r=50, t=50, b=50)  # 设置图表边距
    )
    fig3.update_xaxes(tickangle=-45, tickfont=dict(size=10), nticks=10)  # 更新x轴刻度属性

    # 创建图表4: 布林带
    fig4 = go.Figure()
    fig4.add_trace(
        go.Scatter(x=data.index, y=data['收盘到期收益率(%)'], name='收盘到期收益率', line=dict(color='#1f77b4')))  # 添加收盘到期收益率线
    fig4.add_trace(
        go.Scatter(x=data.index, y=upper_band, name='上轨', line=dict(color='#ff7f0e', width=1, dash='dash')))  # 添加上轨线
    fig4.add_trace(
        go.Scatter(x=data.index, y=lower_band, name='下轨', line=dict(color='#2ca02c', width=1, dash='dash')))  # 添加下轨线
    fig4.update_layout(
        xaxis=dict(title='日期', tickformat='%Y-%m-%d', gridcolor='#f0f0f0', showgrid=True),  # 设置x轴属性
        yaxis=dict(title='收盘到期收益率(%)', gridcolor='#f0f0f0', showgrid=True),  # 设置y轴属性
        plot_bgcolor='#ffffff',  # 设置背景颜色
        legend=dict(x=0, y=1, orientation='h', bgcolor='#f0f0f0', bordercolor='#000000', borderwidth=1),  # 设置图例属性
        height=400,  # 设置图表高度
        margin=dict(l=50, r=50, t=50, b=50)  # 设置图表边距
    )
    fig4.update_xaxes(tickangle=-45, tickfont=dict(size=10), nticks=10)  # 更新x轴刻度属性

    # 将图表转换为HTML
    plot1_html = fig1.to_html(full_html=False)  # 转换图表1为HTML
    plot2_html = fig2.to_html(full_html=False)  # 转换图表2为HTML
    plot3_html = fig3.to_html(full_html=False)  # 转换图表3为HTML
    plot4_html = fig4.to_html(full_html=False)  # 转换图表4为HTML

    return render_template('visualize.html', plot1=plot1_html, plot2=plot2_html, plot3=plot3_html, plot4=plot4_html,
                           stats=stats)  # 渲染可视化页面，并传递图表和统计数据

@app.route('/comment')  # 定义评论页面路由
def comment():
    return render_template('comment.html')  # 渲染评论页面

@app.route('/query', methods=['GET', 'POST'])  # 定义查询路由
def query():
    if request.method == 'POST':
        search_term = request.form['search_term'].lower()  # 获取并转换搜索词为小写

        data = load_data()  # 读取数据

        # 删除任何没有'债券简称'的行。
        data = data.dropna(subset=['债券简称'])  # 删除缺少'债券简称'的行

        # 创建小写版本以进行搜索。
        data['债券简称_lower'] = data['债券简称'].str.lower()  # 创建小写版本的'债券简称'

        filtered_data = data[data['债券简称_lower'].str.contains(search_term)]  # 筛选包含搜索词的行

        print('Filtered data:', filtered_data.to_dict('records'))  # 打印转换后的字典数据

        # 将 NaN 转换为 None，以便正确地序列化为 JSON。
        filtered_data = filtered_data.where(pd.notnull(filtered_data), 0)  # 将NaN替换为0

        return jsonify(filtered_data.to_dict('records'))  # 返回筛选后的数据

    else:
        data = load_data()  # 读取数据

        # 删除任何没有'债券简称'的行。
        data = data.dropna(subset=['债券简称'])  # 删除缺少'债券简称'的行

        random_bonds = random.sample(data['债券简称'].tolist(), 5)  # 随机抽取5个债券简称

        return render_template('query.html', random_bonds=random_bonds)  # 渲染查询页面，并传递随机抽取的债券简称

@app.route('/suggestions')  # 定义建议路由
def suggestions():
    search_term = request.args.get('search_term', '').lower()  # 获取并转换搜索词为小写
    data = load_data()  # 读取数据
    data = data.dropna(subset=['债券简称'])  # 删除缺少'债券简称'的行
    suggestions = data['债券简称'].unique()  # 获取唯一的债券简称
    filtered_suggestions = [s for s in suggestions if search_term in s.lower()]  # 筛选包含搜索词的建议
    return jsonify(filtered_suggestions[:10])  # 返回前10条建议

@app.route('/report')  # 定义报告页面路由
def report():
    return render_template('report.html')  # 渲染报告页面

import random  # 再次导入random模块
from datetime import datetime, timedelta  # 再次导入datetime和timedelta

def generate_stock_code():
    return str(random.randint(100000, 999999))  # 生成随机股票代码

import akshare as ak  # 导入akshare库
from datetime import datetime, timedelta  # 再次导入datetime和timedelta

def generate_kdj_data(stock_code, count):
    # 获取当前日期
    end_date = datetime.now().strftime("%Y%m%d")  # 获取当前日期并格式化
    # 计算30个交易日前的日期
    start_date = (datetime.now() - timedelta(days=count)).strftime("%Y%m%d")  # 计算开始日期

    # 调用 akshare 接口获取指定股票代码和日期范围内的历史行情数据
    stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date=start_date, end_date=end_date,
                                            adjust="")  # 获取股票历史数据

    data = []
    for _, row in stock_zh_a_hist_df.iterrows():
        date = row['日期'].strftime("%Y-%m-%d")  # 将日期转换为字符串格式
        close_price = row['收盘']  # 获取收盘价
        low_price = row['最低']  # 获取最低价
        high_price = row['最高']  # 获取最高价

        # 计算 KDJ 指标
        if len(data) > 0:
            last_k, last_d = data[-1]['k'], data[-1]['d']  # 获取上一个K和D值
        else:
            last_k, last_d = 50, 50  # 初始化K和D值为50

        rsv = (close_price - low_price) / (high_price - low_price) * 100 if high_price != low_price else 0  # 计算RSV
        k = 2 / 3 * last_k + 1 / 3 * rsv  # 计算K值
        d = 2 / 3 * last_d + 1 / 3 * k  # 计算D值
        j = 3 * k - 2 * d  # 计算J值

        data.append({"date": date, "k": round(k, 2), "d": round(d, 2), "j": round(j, 2)})  # 添加计算结果到数据列表

    return data  # 返回KDJ数据

@app.route('/api/kdj_data')  # 定义KDJ数据API路由
def kdj_data():
    stock_code = request.args.get('stock_code', '000001')  # 默认股票代码为 '000001'
    data = generate_kdj_data(stock_code, 100)  # 生成KDJ数据
    return jsonify(data)  # 返回KDJ数据

@app.route('/kdj')  # 定义KDJ页面路由
def kdj():
    return render_template('kdj.html')  # 渲染KDJ页面

if __name__ == '__main__':
    app.run(debug=True)  # 启动Flask应用，开启调试模式
