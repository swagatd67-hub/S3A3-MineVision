import json
import websocket

WS_URL = "ws://127.0.0.1:8000/ws/telemetry"

ws = websocket.create_connection(WS_URL)

print("Connected to PipeVision telemetry stream")

while True:
    message = json.loads(ws.recv())
    message_type = message.get("type")

    if message_type == "telemetry":
        data = message["data"]

        print(
            f"[TELEMETRY] "
            f"mission={data.get('mission_id')} | "
            f"distance={data.get('distance_m')} m | "
            f"battery={data.get('battery_percent')}%"
        )

    elif message_type == "analytics_update":
        mission_id = message.get("mission_id")
        distance = message.get("distance_m")
        points = message.get("latest_points", {})
        events = message.get("recent_events", [])
        new_event = message.get("new_event")

        print(
            f"[ANALYTICS] "
            f"mission={mission_id} | "
            f"distance={distance} m | "
            f"metrics={len(points)} | "
            f"events={len(events)}"
        )

        if new_event:
            print(
                f"  >>> EVENT: {new_event['event_type']} | "
                f"{new_event['severity']} | "
                f"{new_event['distance_start_m']}–"
                f"{new_event['distance_end_m']} m"
            )