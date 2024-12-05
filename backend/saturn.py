import matplotlib
matplotlib.use('Agg')
from flask import Flask, request, send_from_directory, jsonify
from flask_cors import CORS
from astropy.coordinates import get_body, get_sun, get_moon, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def cleanup_old_files(max_age_hours=24):
    current_time = datetime.now()
    for filename in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(filepath):
            file_time = datetime.fromtimestamp(os.path.getctime(filepath))
            if (current_time - file_time) > timedelta(hours=max_age_hours):
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"清理檔案失敗 {filepath}: {e}")

@app.route('/', methods=['POST'])
def generate_chart():
    try:
        data = request.get_json()
        selected_bodies = data.get('bodies', [])
        latitude = float(data.get('latitude'))
        longitude = float(data.get('longitude'))
        hours = float(data.get('hours'))
        lang = data.get('lang', 'zh')

        # 驗證輸入
        if not selected_bodies:
            raise ValueError("請至少選擇一個天體" if lang == 'zh' else "Please select at least one celestial body")
        if not -90 <= latitude <= 90:
            raise ValueError("緯度必須在 -90 到 90 度之間" if lang == 'zh' else "Latitude must be between -90 and 90 degrees")
        if not -180 <= longitude <= 180:
            raise ValueError("經度必須在 -180 到 180 度之間" if lang == 'zh' else "Longitude must be between -180 and 180 degrees")
        if hours <= 0 or hours > 24:
            raise ValueError("時間範圍必須在 0-24 小時之間" if lang == 'zh' else "Time range must be between 0-24 hours")

        # 清理舊檔案
        cleanup_old_files()

        # 設定觀測位置
        location = EarthLocation(lat=latitude*u.deg, lon=longitude*u.deg)
        now = Time.now()
        times = Time([now + timedelta(hours=h) for h in np.linspace(0, float(hours), 100)])
        frame = AltAz(obstime=times, location=location)

        # 繪製圖表
        plt.figure(figsize=(12, 8))
        for body in selected_bodies:
            if body == 'sun':
                altaz = get_sun(times).transform_to(frame)
                label = '太陽' if lang == 'zh' else 'Sun'
            elif body == 'moon':
                altaz = get_moon(times).transform_to(frame)
                label = '月亮' if lang == 'zh' else 'Moon'
            else:
                altaz = get_body(body, times).transform_to(frame)
                label = body.capitalize()
            plt.plot(times.datetime, altaz.alt.degree, label=label)

        # 設定圖表樣式
        plt.grid(True)
        plt.legend()
        plt.xlabel('時間' if lang == 'zh' else 'Time')
        plt.ylabel('高度 (度)' if lang == 'zh' else 'Altitude (degrees)')
        plt.title('天體高度變化圖' if lang == 'zh' else 'Celestial Bodies Altitude Chart')
        plt.xticks(rotation=45)

        # 儲存圖片
        filename = f'altitude_plot_{uuid.uuid4()}.png'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        plt.savefig(filepath, bbox_inches='tight')
        plt.close()

        return jsonify({
            'image_url': f"/static/{filename}",
            'success': True
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/static/<filename>')
def serve_file(filename):
    if not filename.endswith('.png'):
        return "不允許的檔案類型", 400
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))