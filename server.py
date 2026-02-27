"""
台股查詢工具 - 雲端版（yfinance 強化版）
"""

import http.server
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

# 自動安裝套件
for pkg in ['yfinance', 'requests']:
    try:
        __import__(pkg)
    except ImportError:
        print(f"安裝 {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import yfinance as yf

PORT = int(os.environ.get('PORT', 8888))

def get_stock_data(code, months):
    # 嘗試所有可能的代號格式
    candidates = [
        f"{code}.TW",    # 上市
        f"{code}.TWO",   # 上櫃
        f"^{code}",      # 指數
    ]
    # 補零：如果是 4 位數以下，嘗試補零到 4 位
    if len(code) < 4:
        padded = code.zfill(4)
        candidates.insert(0, f"{padded}.TW")
        candidates.insert(1, f"{padded}.TWO")

    end   = datetime.now()
    start = end - timedelta(days=30 * months + 15)

    for ticker_code in candidates:
        try:
            print(f"嘗試查詢：{ticker_code}")
            ticker = yf.Ticker(ticker_code)
            hist = ticker.history(
                start=start.strftime('%Y-%m-%d'),
                end=end.strftime('%Y-%m-%d'),
                auto_adjust=True
            )

            if hist is None or hist.empty:
                print(f"  {ticker_code} 無資料")
                continue

            print(f"  {ticker_code} 取得 {len(hist)} 筆")

            # 取名稱
            name = code
            try:
                info = ticker.fast_info
                name = getattr(info, 'name', None) or code
            except:
                pass
            try:
                full_info = ticker.info
                name = full_info.get('longName') or full_info.get('shortName') or name
                name = name.replace(' Inc.','').replace(' Inc','').strip()
            except:
                pass

            data = []
            for date, row in hist.iterrows():
                try:
                    data.append({
                        'date':  date.strftime('%Y-%m-%d'),
                        'open':  round(float(row['Open']),  2),
                        'high':  round(float(row['High']),  2),
                        'low':   round(float(row['Low']),   2),
                        'close': round(float(row['Close']), 2),
                        'vol':   max(0, round(int(row['Volume']) / 1000))
                    })
                except:
                    continue

            if data:
                return {'code': code, 'name': name, 'data': data}

        except Exception as e:
            print(f"  {ticker_code} 錯誤：{e}")
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
                self.send_json({
                    'error': f'找不到 {code} 的資料。請確認：\n1. 代號是否正確（如 2330、0050）\n2. 是否為上市或上櫃股票'
                }, 404)
                return
            self.send_json(result)
        except Exception as e:
            self.send_json({'error': f'查詢錯誤：{str(e)}'}, 500)

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
