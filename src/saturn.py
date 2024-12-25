from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import io
import base64
import os
import logging

# 在匯入 matplotlib.pyplot 之前設置後端
import matplotlib
matplotlib.use('Agg')  # 使用非互動式的 Agg 後端
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from astropy.coordinates import SkyCoord, get_body, EarthLocation, AltAz
from astroquery.simbad import Simbad
from astropy.time import Time
import astropy.units as u

from timezonefinder import TimezoneFinder
from zoneinfo import ZoneInfo 

app = Flask(__name__)
CORS(app)

plt.rcParams['figure.dpi'] = 1000

# 設定日誌級別
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('saturn')

def get_deep_sky_body(body_name):
    result_table = Simbad.query_object(body_name)
    if result_table is None:
        raise ValueError(f"無法找到天體資料：{body_name}")
    ra = result_table['RA'][0]
    dec = result_table['DEC'][0]
    coord = SkyCoord(ra + ' ' + dec, unit=(u.hourangle, u.deg), frame='icrs')
    return coord

def validate_location(latitude, longitude):
    try:
        lat = float(latitude)
        lon = float(longitude)
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return None, None, '緯度或經度超出範圍。'
        return lat, lon, None
    except ValueError:
        return None, None, '緯度和經度必須是數字。'

def generate_altitude_plot(selected_bodies, latitude, longitude, hours):
    try:
        # 設定觀測位置
        location = EarthLocation(lat=latitude * u.deg, lon=longitude * u.deg)
        logger.info("觀測位置已設定。")

        # 設定觀測時間範圍
        time_now = Time.now()
        delta_hours = np.linspace(0, hours, num=int(hours) * 4)
        times = time_now + delta_hours * u.hour
        logger.info("時間範圍已設定。")

        # 根據經緯度獲取時區
        tf = TimezoneFinder()
        timezone_str = tf.timezone_at(lng=longitude, lat=latitude)

        if timezone_str:
            try:
                tz = ZoneInfo(timezone_str)
                timezone_display = timezone_str
                logger.info(f"獲取到時區：{timezone_str}")
            except Exception as e:
                logger.error(f"無法載入時區 {timezone_str}：{str(e)}")
                tz = ZoneInfo('UTC')  # 使用 UTC 作為備用
                timezone_display = 'UTC'
        else:
            tz = ZoneInfo('UTC')  # 無法找到時區，使用 UTC
            timezone_display = 'UTC'
            logger.warning("無法根據經緯度獲取時區，預設使用 UTC。")

        # 將時間轉換為當地時間並移除 tzinfo
        local_times = times.to_datetime(timezone=tz)
        local_times = [dt.replace(tzinfo=None) for dt in local_times]

        # 設定 AltAz 參考系
        altaz = AltAz(obstime=times, location=location)
        logger.info("AltAz 參考系已設定。")

        # 準備圖表
        plt.figure(figsize=(10, 6))
        logger.info("圖表已建立。")

        for body_name in selected_bodies:
            logger.info(f"處理天體：{body_name}")
            try:
                body_lower = body_name.lower()
                if body_lower in ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']:
                    # 太陽系天體
                    body = get_body(body_name, times, location).transform_to(altaz)
                    altitudes = body.alt.deg
                else:
                    # 深空天體
                    coord = get_deep_sky_body(body_name)
                    altazs = coord.transform_to(altaz)
                    altitudes = altazs.alt.deg

                # 使用原始名稱作為標籤
                label = body_name
                plt.plot(local_times, altitudes, label=label)
            except Exception as e:
                logger.error(f"獲取 {body_name} 資料時出錯：{str(e)}")
                raise ValueError(f"無法獲取 {body_name} 的資料：{str(e)}")

        # 設置圖表標題和標籤（使用英文）
        plt.title('Altitude of Celestial Bodies')
        plt.xlabel('Local Time')
        plt.ylabel('Altitude (degrees)')
        plt.legend()
        plt.grid(True)
        logger.info("圖表已配置。")

        # 設置 X 軸為當地時間格式
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.gcf().autofmt_xdate()  # 自動調整日期標籤角度

        # 在圖表右下角註明時區
        plt.annotate(f"Timezone: {timezone_display}", xy=(1.0, 0.0), xycoords='axes fraction',
                     horizontalalignment='right', verticalalignment='bottom',
                     fontsize=10, bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.5))

        # 保存圖表到緩衝區並編碼為 Base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        logger.info("圖表已保存並編碼。")

        return image_base64
    except Exception as e:
        logger.error(f"生成圖表時出錯：{str(e)}")
        raise ValueError(f"生成圖表時出錯：{str(e)}")

@app.route('/generate_plot', methods=['POST'])
def generate_plot():
    logger.info("收到 /generate_plot 請求。")
    data = request.json
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    bodies = data.get('bodies')
    hours = data.get('hours', 24)

    logger.info(f"請求資料：latitude={latitude}, longitude={longitude}, bodies={bodies}, hours={hours}")

    # 驗證位置
    lat, lon, error = validate_location(latitude, longitude)
    if error:
        logger.error(f"位置驗證錯誤：{error}")
        return jsonify({'message': error}), 400

    # 生成圖片
    try:
        image_base64 = generate_altitude_plot(bodies, lat, lon, int(hours))
        logger.info("圖表生成成功。")
        return jsonify({'image_base64': image_base64}), 200
    except ValueError as e:
        logger.error(f"ValueError：{str(e)}")
        return jsonify({'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Exception：{str(e)}")
        return jsonify({'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9862))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)