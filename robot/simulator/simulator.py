import math
import time
from datetime import datetime, timezone
import requests

API = 'http://127.0.0.1:8000'
ROBOT_ID = 'PV-SIM-001'

def main():
    requests.post(f'{API}/api/v1/robots/register', json={
        'robot_id': ROBOT_ID, 'name': 'PipeVision Simulator', 'firmware_version': 'sim-0.1',
        'capabilities': ['camera','imu','water_quality','pressure','cleaning','adaptive_morphology']
    }, timeout=5).raise_for_status()
    t = 0.0
    while True:
        body = 105 + 15 * math.sin(t/5)
        payload = {
            'robot_id': ROBOT_ID, 'timestamp': datetime.now(timezone.utc).isoformat(),
            'battery_percent': max(0, 100 - 0.15*t), 'distance_m': max(0, 0.15*t),
            'body_diameter_mm': body, 'state': 'INSPECTING',
            'imu': {'ax':0.03*math.sin(t),'ay':0.02*math.cos(t),'az':9.81,'gx':0.02,'gy':0.01,'gz':0.10*math.sin(t/2)},
            'pressure': {'body_kpa':95+4*math.sin(t/4),'front_anchor_kpa':175,'rear_anchor_kpa':170},
            'water': {'temperature_c':25+0.5*math.sin(t/7),'ph':6.9+0.08*math.sin(t/9),'conductivity_ms_cm':1.6+0.15*math.sin(t/6),'turbidity_ntu':30+5*math.sin(t/3)}
        }
        requests.post(f'{API}/api/v1/telemetry', json=payload, timeout=5).raise_for_status()
        print(f'{ROBOT_ID} | {payload["distance_m"]:.2f} m | diameter {body:.1f} mm | battery {payload["battery_percent"]:.1f}%')
        t += 0.5
        time.sleep(0.5)

if __name__ == '__main__':
    main()
