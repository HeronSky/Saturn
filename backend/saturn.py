import os
import io
import base64
import numpy as np
import matplotlib
matplotlib.use('Agg')

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from astropy.coordinates import get_body, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u
import matplotlib.pyplot as plt
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

SUPPORTED_BODIES = [
    'mercury', 'venus', 'mars', 'jupiter',
    'saturn', 'uranus', 'neptune', 'moon', 'sun'
]

def validate_location(latitude, longitude):
    try:
        lat = float(latitude)
        lon = float(longitude)

        if not (-90 <= lat <= 90):
            raise ValueError("緯度必須介於 -90 至 90 之間")

        if not (-180 <= lon <= 180):
            raise ValueError("經度必須介於 -180 至 180 之間")

        return lat, lon, None
    except (ValueError, TypeError) as e:
        return None, None, str(e)

def generate_altitude_plot(selected_bodies, latitude, longitude, hours):
    try:
        t = Time.now()
        location = EarthLocation(lat=latitude * u.deg, lon=longitude * u.deg, height=0 * u.m)
        timezone = pytz.timezone('UTC')
        times = t + np.linspace(0, hours, 100) * u.hour

        plt.figure(figsize=(12, 7))
        plt.clf()

        results = {}
        for body_name in selected_bodies:
            try:
                altazs = get_body(body_name, times, location).transform_to(
                    AltAz(obstime=times, location=location)
                )
                alts = altazs.alt.degree
                local_times = [t.datetime.replace(tzinfo=pytz.utc).astimezone(timezone) for t in times]
                plt.plot(local_times, alts, label=body_name.capitalize())
                results[body_name] = 'success'
            except Exception as e:
                results[body_name] = f"Error: {str(e)}"

        plt.axhline(0, color='black', linewidth=2)
        plt.xlabel('Local Time')
        plt.ylabel('Altitude (degrees)')
        plt.title(f'Altitude Changes of Celestial Bodies Over the Next {hours} Hours (Local Time)')
        plt.legend()
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png')
        plt.close()
        img_buffer.seek(0)

        img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')

        return img_base64, results, None

    except Exception as e:
        plt.close()
        return None, None, f"Error generating chart: {str(e)}"

@app.route('/')
def index():
    return render_template_string("<h1>Welcome to the Celestial Chart API</h1>")

@app.route('/celestial-chart', methods=['POST'])
def generate_chart():
    try:
        data = request.get_json()

        selected_bodies = data.get('bodies', [])
        hours = float(data.get('hours', 8))
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if not selected_bodies:
            return jsonify({
                'status': 'error',
                'message': '請至少選擇一個天體'
            }), 400

        invalid_bodies = set(selected_bodies) - set(SUPPORTED_BODIES)
        if invalid_bodies:
            return jsonify({
                'status': 'error',
                'message': f"不支援的天體：{', '.join(invalid_bodies)}"
            }), 400

        lat, lon, loc_error = validate_location(latitude, longitude)
        if loc_error:
            return jsonify({
                'status': 'error',
                'message': loc_error
            }), 400

        image_base64, body_results, error = generate_altitude_plot(
            selected_bodies,
            lat,
            lon,
            hours
        )

        if error:
            return jsonify({
                'status': 'error',
                'message': error,
                'body_results': body_results
            }), 500

        return jsonify({
            'status': 'success',
            'image_base64': image_base64,
            'body_results': body_results
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)