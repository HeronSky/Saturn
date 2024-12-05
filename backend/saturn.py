import matplotlib
matplotlib.use('Agg')

from flask import Flask, render_template, request, send_from_directory, url_for, redirect, jsonify
from astropy.coordinates import get_body, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime
from timezonefinder import TimezoneFinder
import pytz

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
tf = TimezoneFinder()

LANGUAGES = {
    'en': 'English',
    'zh': '中文'
}

# 新增支持的天體列表
SUPPORTED_BODIES = [
    'mercury', 'venus', 'mars', 'jupiter', 
    'saturn', 'uranus', 'neptune', 'moon', 'sun'
]

def get_locale():
    return request.args.get('lang', 'en')

@app.route('/change_language/<language>')
def change_language(language):
    if language not in LANGUAGES:
        language = 'en'
    return redirect(url_for('index', lang=language))

def validate_location(latitude, longitude, lang):
    """驗證地理位置座標"""
    try:
        lat = float(latitude)
        lon = float(longitude)
        
        if not (-90 <= lat <= 90):
            raise ValueError("緯度必須介於 -90 至 90 之間。" if lang == 'zh' else "Latitude must be between -90 and 90.")
        
        if not (-180 <= lon <= 180):
            raise ValueError("經度必須介於 -180 至 180 之間。" if lang == 'zh' else "Longitude must be between -180 and 180.")
        
        return lat, lon
    except (ValueError, TypeError) as e:
        return None, str(e)

def generate_altitude_plot(selected_bodies, latitude, longitude, hours, lang):
    """生成高度變化圖表"""
    t = Time.now()
    location = EarthLocation(lat=latitude*u.deg, lon=longitude*u.deg, height=0*u.m)
    times = t + np.linspace(0, hours, 100) * u.hour

    plt.figure(figsize=(12, 7))
    error_occurred = False
    error_message = None

    for body_name in selected_bodies:
        try:
            altazs = get_body(body_name, times, location).transform_to(AltAz(obstime=times, location=location))
            alts = altazs.alt.degree
            utc_datetimes = times.datetime
            plt.plot(utc_datetimes, alts, label=body_name.capitalize())
        except Exception as e:
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

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        image_filename = f'altitude_plot_{timestamp}.png'
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        
        try:
            plt.savefig(save_path)
            plt.close()
            return image_filename, None
        except Exception as e:
            error_message = "保存圖像時出錯。" if lang == 'zh' else "Error saving image."
    else:
        plt.close()

    return None, error_message

@app.route('/', methods=['GET', 'POST'])
def index():
    lang = get_locale()
    image_filename = None
    error_message = None

    if request.method == 'POST':
        # 獲取表單數據
        selected_bodies = request.form.getlist('bodies')
        hours = request.form.get('hours', 8)
        location_method = request.form.get('location_method', 'automatic')

        # 驗證選擇的天體
        if not selected_bodies:
            error_message = "請至少選擇一個天體。" if lang == 'zh' else "Please select at least one celestial body."
            return render_template('index.html', error_message=error_message, lang=lang)

        # 驗證選擇的天體是否在支持列表中
        invalid_bodies = set(selected_bodies) - set(SUPPORTED_BODIES)
        if invalid_bodies:
            error_message = f"不支持的天體：{', '.join(invalid_bodies)}"
            return render_template('index.html', error_message=error_message, lang=lang)

        # 驗證時間範圍
        try:
            hours = float(hours)
            if hours <= 0 or hours > 24:
                raise ValueError("時間範圍必須在 0-24 小時之間。")
        except ValueError:
            error_message = "請輸入有效的時間範圍（1-24小時）。" if lang == 'zh' else "Please enter a valid time range (1-24 hours)."
            return render_template('index.html', error_message=error_message, lang=lang)

        # 處理位置
        if location_method == 'manual':
            latitude = request.form.get('manual_latitude')
            longitude = request.form.get('manual_longitude')
        else:
            latitude = request.form.get('auto_latitude')
            longitude = request.form.get('auto_longitude')

        # 驗證地理位置
        latitude, longitude = validate_location(latitude, longitude, lang)
        if not latitude or not longitude:
            error_message = longitude  # longitude 在這裡實際上是錯誤消息
            return render_template('index.html', error_message=error_message, lang=lang)

        # 嘗試確定時區
        try:
            timezone_str = tf.timezone_at(lng=longitude, lat=latitude)
            if timezone_str is None:
                raise ValueError("無法確定時區。" if lang == 'zh' else "Cannot determine timezone.")
            local_timezone = pytz.timezone(timezone_str)
        except Exception as e:
            error_message = f"時區確定錯誤：{e}" if lang == 'zh' else f"Timezone determination error: {e}"
            return render_template('index.html', error_message=error_message, lang=lang)

        # 生成圖表
        image_filename, plot_error = generate_altitude_plot(
            selected_bodies, 
            latitude, 
            longitude, 
            hours, 
            lang
        )

        if plot_error:
            error_message = plot_error

    return render_template('index.html', 
                           image_url=url_for('static', filename=image_filename) if image_filename else None, 
                           error_message=error_message, 
                           lang=lang)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)