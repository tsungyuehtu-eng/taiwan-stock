"""
台股查詢工具 - 雲端版伺服器（適用 Render）
"""

import http.server
import json
import urllib.request
import urllib.error
import urllib.parse
import os
import time
from datetime import datetime, timedelta

# Render 會自動設定 PORT 環境變數
PORT = int(os.environ.get('PORT', 8888))

class StockHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]}")

    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == '/':
            self.serve_file('index.html', 'text/html')
        elif parsed.path == '/api/stock':
            code   = params.get('code',   [''])[0].strip()
            months = int(params.get('months', ['1'])[0])
            self.handle_stock(code, months)
        elif parsed.path == '/api/realtime':
            code = params.get('code', [''])[0].strip()
            self.handle_realtime(code)
        elif parsed.path == '/health':
            self.send_json({'status': 'ok'})
        else:
            self.send_response(404)
            self.end_headers()

    def serve_file(self, filename, content_type):
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def handle_stock(self, code, months):
        if not code:
            self.send_json({'error': '請輸入股票代號'}, 400)
            return

        all_data = []
        name = code
        now = datetime.now()

        for i in range(months - 1, -1, -1):
            target   = datetime(now.year, now.month, 1) - timedelta(days=30 * i)
            yyyymmdd = target.strftime('%Y%m01')
            url = f'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={yyyymmdd}&stockNo={code}'

            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/json'
                })
                with urllib.request.urlopen(req, timeout=10) as res:
                    raw = json.loads(res.read().decode('utf-8'))

                if raw.get('stat') != 'OK' or not raw.get('data'):
                    continue

                title = raw.get('title', '')
                if ' ' in title:
                    name = title.split(' ')[1]

                for row in raw['data']:
                    try:
                        parts   = row[0].split('/')
                        date_str = f"{int(parts[0])+1911}-{parts[1]}-{parts[2]}"
                        vol     = round(int(row[1].replace(',', '')) / 1000)
                        open_p  = float(row[3].replace(',', ''))
                        high_p  = float(row[4].replace(',', ''))
                        low_p   = float(row[5].replace(',', ''))
                        close_p = float(row[6].replace(',', ''))
                        all_data.append({
                            'date':  date_str,
                            'open':  open_p,
                            'high':  high_p,
                            'low':   low_p,
                            'close': close_p,
                            'vol':   vol
                        })
                    except (ValueError, IndexError):
                        continue

                time.sleep(0.3)

            except Exception as e:
                print(f"警告：{e}")

        if not all_data:
            self.send_json({'error': f'找不到 {code} 的資料，請確認是上市股票代號'}, 404)
            return

        all_data.sort(key=lambda x: x['date'])
        self.send_json({'code': code, 'name': name, 'data': all_data})

    def handle_realtime(self, code):
        url = f'https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{code}.tw&json=1&delay=0'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as res:
                raw = json.loads(res.read().decode('utf-8'))

            arr = raw.get('msgArray', [])
            if not arr:
                self.send_json({'error': '無即時資料'}, 404)
                return

            d = arr[0]
            def sf(v):
                try: return float(v)
                except: return None

            self.send_json({
                'name':  d.get('n', code),
                'price': sf(d.get('z')) or sf(d.get('y')),
                'prev':  sf(d.get('y')),
                'open':  sf(d.get('o')),
                'high':  sf(d.get('h')),
                'low':   sf(d.get('l')),
                'vol':   round(int(d.get('v', 0)) / 1000) if d.get('v') else None
            })
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    print(f'✅ 台股伺服器啟動，PORT={PORT}')
    server = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), StockHandler)
    server.serve_forever()
