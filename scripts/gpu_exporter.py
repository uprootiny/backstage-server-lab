"""GPU metrics exporter for Prometheus — scrapes nvidia-smi every 5s."""
import subprocess
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 9101

def get_gpu_metrics():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,fan.speed",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
        parts = [p.strip() for p in r.stdout.strip().split(",")]
        def clean(s):
            s = s.strip().replace("[N/A]", "0").replace("N/A", "0")
            try: return str(float(s))
            except: return "0"
        util = clean(parts[0]) if len(parts) > 0 else "0"
        mem_used = clean(parts[1]) if len(parts) > 1 else "0"
        mem_total = clean(parts[2]) if len(parts) > 2 else "32768"
        temp = clean(parts[3]) if len(parts) > 3 else "0"
        power = clean(parts[4]) if len(parts) > 4 else "0"
        fan = clean(parts[5]) if len(parts) > 5 else "0"
        return f"""# HELP gpu_utilization_percent GPU utilization percentage
# TYPE gpu_utilization_percent gauge
gpu_utilization_percent {{gpu="0"}} {util}
# HELP gpu_memory_used_mb GPU memory used in MB
# TYPE gpu_memory_used_mb gauge
gpu_memory_used_mb {{gpu="0"}} {mem_used}
# HELP gpu_memory_total_mb GPU memory total in MB
# TYPE gpu_memory_total_mb gauge
gpu_memory_total_mb {{gpu="0"}} {mem_total}
# HELP gpu_temperature_celsius GPU temperature
# TYPE gpu_temperature_celsius gauge
gpu_temperature_celsius {{gpu="0"}} {temp}
# HELP gpu_power_draw_watts GPU power draw
# TYPE gpu_power_draw_watts gauge
gpu_power_draw_watts {{gpu="0"}} {power}
# HELP gpu_fan_speed_percent GPU fan speed
# TYPE gpu_fan_speed_percent gauge
gpu_fan_speed_percent {{gpu="0"}} {fan}
"""
    except Exception as e:
        return f"# error: {e}\n"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(get_gpu_metrics().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    print(f"GPU exporter on :{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
