import matplotlib
matplotlib.use('Agg')  # 使用非互動後端

from flask import Flask, render_template, request, send_from_directory, url_for, redirect
from astropy.coordinates import get_body, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime, timedelta
from timezonefinder import TimezoneFinder
import pytz
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__, template_folder='../frontend', static_folder='static')

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

def get_locale():
    return request.args.get('lang', 'en')

@app.route('/change_language/<language>')
def change_language(language):
    if language not in LANGUAGES.keys():
        language = 'en'
    return redirect(url_for('index', lang=language))

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

@app.route('/', methods=['GET', 'POST'])
def index():
    lang = get_locale()
    image_url = None
    error_message = None
    if request.method == 'POST':
        # 獲取用戶輸入
        selected_bodies = request.form.getlist('bodies')
        hours = request.form.get('hours', 8)
        location_method = request.form.get('location_method', 'automatic')

        if location_method == 'manual':
            latitude = request.form.get('manual_latitude')
            longitude = request.form.get('manual_longitude')
            try:
                latitude = float(latitude)
                longitude = float(longitude)
                print(f"Manual Location - Latitude: {latitude}, Longitude: {longitude}")
            except (ValueError, TypeError):
                error_message = "請輸入有效的經度和緯度。" if lang == 'zh' else "Please enter valid latitude and longitude."
                return render_template('index.html', error_message=error_message, lang=lang)
        else:
            latitude = request.form.get('auto_latitude')
            longitude = request.form.get('auto_longitude')
            try:
                latitude = float(latitude)
                longitude = float(longitude)
                print(f"Automatic Location - Latitude: {latitude}, Longitude: {longitude}")
            except (ValueError, TypeError):
                error_message = "自動位置檢測失敗。請嘗試手動輸入。" if lang == 'zh' else "Automatic location detection failed. Please try manual input."
                return render_template('index.html', error_message=error_message, lang=lang)

        # 打印接收到的表單數據
        print("Form Data Received:")
        print(f"Selected Bodies: {selected_bodies}")
        print(f"Hours: {hours}")
        print(f"Location Method: {location_method}")
        print(f"Latitude: {latitude}")
        print(f"Longitude: {longitude}")

        # 驗證天體選擇
        if not selected_bodies:
            error_message = "請至少選擇一個天體。" if lang == 'zh' else "Please select at least one celestial body."
            return render_template('index.html', error_message=error_message, lang=lang)

        # 驗證時間輸入
        try:
            hours = float(hours)
            if hours <= 0:
                raise ValueError
        except ValueError:
            error_message = "請輸入有效的時間範圍（正數）。" if lang == 'zh' else "Please enter a valid time range (positive number)."
            return render_template('index.html', error_message=error_message, lang=lang)

        # 驗證經緯度範圍
        if not (-90 <= latitude <= 90):
            error_message = "緯度必須介於 -90 至 90 之間。" if lang == 'zh' else "Latitude must be between -90 and 90."
            return render_template('index.html', error_message=error_message, lang=lang)

        if not (-180 <= longitude <= 180):
            error_message = "經度必須介於 -180 至 180 之間。" if lang == 'zh' else "Longitude must be between -180 and 180."
            return render_template('index.html', error_message=error_message, lang=lang)

        # 根據經緯度確定時區
        try:
            timezone_str = tf.timezone_at(lng=longitude, lat=latitude)
            print(f"Detected Timezone: {timezone_str}")
            if timezone_str is None:
                raise ValueError("無法確定時區。" if lang == 'zh' else "Cannot determine timezone.")
            local_timezone = pytz.timezone(timezone_str)
            print(f"Local Timezone: {local_timezone}")
        except Exception as e:
            error_message = f"時區確定錯誤：{e}" if lang == 'zh' else f"Timezone determination error: {e}"
            print(error_message)
            return render_template('index.html', error_message=error_message, lang=lang)

        # 當前 UTC 時間
        t = Time.now()

        # 定義觀測位置
        location = EarthLocation(lat=latitude*u.deg, lon=longitude*u.deg, height=0*u.m)

        # 計算天體的高度變化
        times = t + np.linspace(0, hours, 100) * u.hour

        plt.figure(figsize=(10, 6))
        error_occurred = False

        for body_name in selected_bodies:
            try:
                altazs = get_body(body_name, times, location).transform_to(AltAz(obstime=times, location=location))
                alts = altazs.alt.degree
                # 將時間轉換為 UTC 的 datetime 對象
                utc_datetimes = times.datetime
                plt.plot(utc_datetimes, alts, label=body_name.capitalize())
                print(f"Plotted {body_name.capitalize()} successfully.")
            except Exception as e:
                print(f"處理天體 {body_name} 時出錯：{e}")
                error_message = f"處理天體 {body_name} 時出錯。" if lang == 'zh' else f"Error processing celestial body {body_name}."
                error_occurred = True

        if not error_occurred:
            plt.xlabel('UTC 時間' if lang == 'zh' else 'UTC Time')
            plt.ylabel('高度（度）' if lang == 'zh' else 'Altitude (degrees)')
            plt.title(f'接下來 {hours} 小時內天體高度變化（UTC 時間）' if lang == 'zh' else f'Celestial Altitude Changes Over the Next {hours} Hours (UTC Time)')
            plt.legend()
            plt.grid(True)
            plt.xticks(rotation=45)
            plt.tight_layout()

            # 保存圖表
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            image_filename = f'altitude_plot_{timestamp}.png'
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            try:
                plt.savefig(save_path)
                plt.close()
                image_url = url_for('static', filename=image_filename)
                print(f"圖像已保存至 {save_path}")
            except Exception as e:
                print(f"保存圖像時出錯：{e}")
                error_message = "保存圖像時出錯。" if lang == 'zh' else "Error saving image."
        else:
            plt.close()

        return render_template('index.html', image_url=image_url, error_message=error_message, lang=lang)

    # 處理 GET 請求
    return render_template('index.html', lang=lang)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    try:
        app.run(debug=True)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()