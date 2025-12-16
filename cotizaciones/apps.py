from django.apps import AppConfig
import socket
import requests

class CotizacionesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cotizaciones'

    def ready(self):
        import cotizaciones.signals


def test_internet():
    try:
        socket.create_connection(("www.google.com", 80), timeout=5)
        print("✅ SOCKET: Internet OK")
    except Exception as e:
        print("❌ SOCKET: Sin internet:", e)

    try:
        r = requests.get("https://www.google.com", timeout=5)
        print("✅ HTTP: Internet OK", r.status_code)
    except Exception as e:
        print("❌ HTTP: Sin internet:", e)

test_internet()