import matplotlib
matplotlib.use('Agg')  # 使用非互動後端

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from astropy.coordinates import get_body, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u  # 確保導入 astropy.units
from datetime import datetime, timedelta
from timezonefinder import TimezoneFinder
from apscheduler.schedulers.background import BackgroundScheduler
import os

app = Flask(__name__, template_folder='../frontend', static_folder='static')
CORS(app)

# 設定圖像上傳目錄的絕對路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 初始化 TimezoneFinder
tf = TimezoneFinder()

# 設定支持的語言
LANGUAGES = {
    'en': 'English',
    'zh': '中文'
}

def delete_old_files():
    now = datetime.now()
    cutoff = now - timedelta(hours=1)
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(file_path):
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            if file_mtime < cutoff:
                os.remove(file_path)
                print(f"Deleted {file_path}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=delete_old_files, trigger="interval", minutes=60)
scheduler.start()

@app.route('/')
def index():
    return render_template('index.html')

# 新增 API 端點
@app.route('/api/calculate', methods=['POST'])
def calculate():
    data = request.json
    body_name = data.get('body')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    time_str = data.get('time')
    
    # 解析時間
    time = Time(time_str)
    
    # 設定觀測位置
    location = EarthLocation(lat=latitude*u.deg, lon=longitude*u.deg)
    
    # 計算天體高度
    altaz = AltAz(obstime=time, location=location)
    body = get_body(body_name, time)
    body_altaz = body.transform_to(altaz)
    
    # 返回結果
    result = {
        'body': body_name,
        'altitude': body_altaz.alt.deg
    }
    return jsonify(result)

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=True)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()