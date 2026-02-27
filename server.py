"""
台股查詢工具 - 雲端版（自動安裝 yfinance）
"""

import http.server
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

# 自動安裝 yfinance
try:
    import yfinance as yf
except ImportError:
    print("安裝 yfinance...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance"])
    import yfinance as yf

PORT = int(os.environ.get('PORT', 8888))

def get_stock_data(code, months):
    ticker_tw  = f"{code}.TW"
    ticker_two = f"{code}.TWO"

    end   = datetime.now()
    start = end - timedelta(days=30 * months + 10)

    for ticker_code in [ticker_tw, ticker_two]:
        try:
            ticker = yf.Ticker(ticker_code)
            hist   = ticker.history(start=start.strftime('%Y-%m-%d'),
                                    end=end.strftime('%Y-%m-%d'))
            if hist.empty:
                continue

            info = ticker.info
            name = info.get('longName') or info.get('shortName') or code
            name = name.replace(' Inc.', '').replace(' Inc', '').strip()

            data = []
            for date, row in hist.iterrows():
                data.append({
                    'date':  date.strftime('%Y-%m-%d'),
                    'open':  round(float(row['Open']),  2),
                    'high':  round(float(row['High']),  2),
                    'low':   round(float(row['Low']),   2),
                    'close': round(float(row['Close']), 2),
                    'vol':   round(int(row['Volume']) / 1000)
                })

            if data:
                return {'code': code, 'name': name, 'data': data}

        except Exception as e:
            print(f"嘗試 {ticker_code} 失敗：{e}")
            continue

    return None


class StockHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]}")

    def send_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        import urllib.parse
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == '/':
            self.serve_html()
        elif parsed.path == '/api/stock':
            code   = params.get('code',   [''])[0].strip().upper()
            months = int(params.get('months', ['1'])[0])
            self.handle_stock(code, months)
        elif parsed.path == '/health':
            self.send_json({'status': 'ok'})
        else:
            self.send_response(404)
            self.end_headers()

    def serve_html(self):
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_cors()
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def handle_stock(self, code, months):
        if not code:
            self.send_json({'error': '請輸入股票代號'}, 400)
            return
        try:
            result = get_stock_data(code, months)
            if not result:
                self.send_json({'error': f'找不到 {code} 的資料，請確認股票代號'}, 404)
                return
            self.send_json(result)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_cors()
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    print(f'✅ 台股伺服器啟動，PORT={PORT}')
    server = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), StockHandler)
    server.serve_forever()
