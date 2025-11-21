# code.py

# ===================================================================
# Haupt-Anwendung für das yourmuesli.at IoT Environmental Monitoring
#
# Autor: Ihr Team
# Datum: 02.09.2025
#
# Hardware: Raspberry Pi Pico W
# Sensor: DHT22 (Temperatur & Luftfeuchtigkeit)
# Software: CircuitPython
# ===================================================================

# ----------- Bibliotheken importieren -----------
# Hier werden später alle benötigten CircuitPython-Bibliotheken importiert
# z.B. import board, time, wifi, adafruit_dht, etc.
import time
from adafruit_datetime import datetime, timezone
import adafruit_dht as dht
import board
import digitalio
import toml
import wifi
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import adafruit_connection_manager
import json
import socketpool
# ===================================================================
# KLASSE: ConfigManager
# ===================================================================
class ConfigManager:
    """
    Verwaltet das Laden und Speichern der Konfiguration aus der 'settings.toml'.
    """

    def __init__(self, filepath: str):
        """
        Initialisiert den ConfigManager.

        :param filepath: Der Pfad zur Konfigurationsdatei (z.B. "settings.toml").
        """
        self.filepath = filepath

    def load_settings(self) -> dict:
        """
        Lädt die Einstellungen aus der TOML-Datei.

        :return: Ein Dictionary mit allen geladenen Einstellungen.
        """
        try:
            with open(self.filepath, "r") as f:
                settings = toml.load(f)
            return settings
        except Exception as e:
            print(f"Fehler beim Laden der Konfiguration: {e}")
            return {}

    def save_settings(self, settings: dict):
        """
        Speichert Änderungen zurück in die TOML-Datei und startet den
        Mikrocontroller neu, um die neuen Einstellungen zu übernehmen.

        :param settings: Das Dictionary mit den zu speichernden Einstellungen.
        """
        with open(self.filepath, "w") as f:
            toml.dump(settings, f)

# ===================================================================
# KLASSE: NetworkManager
# ===================================================================
class NetworkManager:
    """
    Kümmert sich um die Verbindung zum WLAN-Netzwerk.
    """

    def __init__(self, ssid: str, password: str):
        """
        Initialisiert den NetworkManager mit den WLAN-Zugangsdaten.

        :param ssid: Der Name des WLAN-Netzwerks (SSID).
        :param password: Das Passwort für das WLAN-Netzwerk.
        """
        self.ssid = ssid
        self.password = password

    def connect(self) -> bool:
        """
        Stellt die Verbindung zum WLAN her. Versucht es bei einem Fehler
        mehrfach, bevor aufgegeben wird.

        :return: True bei erfolgreicher Verbindung, ansonsten False.
        """
        for attempt in range(5):
            try:
                wifi.radio.connect(self.ssid, self.password)
                print(f"Mit WLAN '{self.ssid}' verbunden.")
                return True
            except Exception as e:
                print(f"Verbindungsversuch {attempt + 1} fehlgeschlagen: {e}")
                time.sleep(3)
        return False

    def is_connected(self) -> bool:
        """
        Prüft den aktuellen Verbindungsstatus.

        :return: True, wenn eine WLAN-Verbindung besteht, ansonsten False.
        """
        return wifi.radio.connected

    def get_ip(self) -> str:
        """
        Gibt die aktuell zugewiesene IP-Adresse des Geräts zurück.

        :return: Die IP-Adresse als String (z.B. "192.168.1.100").
        """
        return str(wifi.radio.ipv4_address)


# ===================================================================
# KLASSE: Sensor
# ===================================================================
class Sensor:
    """
    Kapselt die Logik zum Auslesen des DHT22-Sensors.
    """

    def __init__(self, pin_number: int):
        """
        Initialisiert den Sensor am angegebenen GPIO-Pin.

        :param pin_number: Die Nummer des GPIO-Pins (z.B. 15 für GP15).
        """
        self.sensor = dht.DHT11(getattr(board, f"GP{pin_number}"))

    def read_data(self) -> dict | None:
        """
        Liest Temperatur und Luftfeuchtigkeit vom Sensor.

        :return: Ein Dictionary wie {'temperature': 22.5, 'humidity': 45.8}
                 oder None, falls das Auslesen fehlschlägt.
        """
        temperature = self.sensor.temperature
        humidity = self.sensor.humidity
        if temperature is None or humidity is None:
            return None
        return {'temperature': temperature, 'humidity': humidity} 


# ===================================================================
# KLASSE: MqttClient
# ===================================================================
class MqttClient:
    """
    Verwaltet die Kommunikation mit dem zentralen MQTT-Broker.
    """

    def __init__(self, config: dict):
        """
        Initialisiert den MQTT-Client mit den Broker-Details aus der Konfiguration.

        :param config: Ein Dictionary mit den MQTT-Einstellungen.
        """
        self.config = config

        pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
        ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
        
        self.mqtt_client = MQTT.MQTT(
            broker=self.config["broker_address"],
            port=self.config["broker_port"],
            username=self.config["mqtt_username"],
            password=self.config["mqtt_password"],
            socket_pool=pool,
            ssl_context=ssl_context
        )

    def connect(self):
        """
        Verbindet sich mit dem MQTT-Broker und setzt eine "Last Will and Testament"
        Nachricht, die gesendet wird, falls das Gerät unerwartet die Verbindung verliert.
        """
        self.mqtt_client.will_set(self.config["status_topic"], "offline", retain=True)
        self.mqtt_client.connect()

    def publish_telemetry(self, data: dict):
        """
        Formatiert die Sensordaten in ein JSON-Payload und sendet sie
        an das definierte Telemetrie-Topic.

        :param data: Das Dictionary mit den Sensordaten.
        """
        tm = time.localtime()
        timestamp = "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z".format(
            tm[0], tm[1], tm[2], tm[3], tm[4], tm[5]
        )
        status = "ok" if data else "error"

        temp_payload = {
            "timestamp": timestamp,
            "sensor_id": self.config["device_id"],
            "value": data.get("temperature"),
            "unit": "°C",
            "status": status
        }

        humidity_payload = {
            "timestamp": timestamp,
            "sensor_id": self.config["device_id"],
            "value": data.get("humidity"),
            "unit": "%",
            "status": status
        }

        temperature_json = json.dumps(temp_payload)
        humidity_json = json.dumps(humidity_payload)

        self.mqtt_client.publish(self.config["telemetry_topic"]+"/temperature", temperature_json)
        self.mqtt_client.publish(self.config["telemetry_topic"]+"/humidity", humidity_json)

    def publish_status(self, status: str):
        """
        Sendet eine einfache Statusnachricht (z.B. "online", "rebooting")
        an das definierte Status-Topic.

        :param status: Die zu sendende Statusnachricht.
        """
        self.mqtt_client.publish(self.config["status_topic"], status)

    def loop(self):
        """
        Hält die MQTT-Verbindung aktiv. Muss regelmäßig in der Hauptschleife
        aufgerufen werden.
        """
        self.mqtt_client.loop(timeout=1)


# ===================================================================
# KLASSE: WebServer
# ===================================================================
class WebServer:
    """
    Stellt eine einfache HTTP-Schnittstelle zur Fernkonfiguration bereit.
    """

    def __init__(self, config_manager: ConfigManager):
        """
        Initialisiert den Webserver.

        :param config_manager: Eine Instanz des ConfigManagers, um Einstellungen
                               zu lesen und zu speichern.
        """
        self.config_manager = config_manager
        self.pool = socketpool.SocketPool(wifi.radio)
        self.server_socket = None
        self.port = 8080

    def start(self):
        """
        Startet den Webserver, sodass er auf Anfragen lauscht.
        """
        self.server_socket = self.pool.socket()
        self.server_socket.bind(("0.0.0.0", self.port))
        self.server_socket.listen(1)

        print(f"Webserver läuft auf http://{wifi.radio.ipv4_address}:{self.port}")

    def poll(self):
        """
        Verarbeitet eine einzelne anstehende HTTP-Anfrage. Muss in der
        Hauptschleife des Programms aufgerufen werden.
        """

        client, addr = self.server_socket.accept()
        print("Neue Verbindung von", addr)

        buffer = bytearray(1024)       # Puffer anlegen
        size = client.recv_into(buffer) # liest bis zu 1024 Bytes in buffer

        if size > 0:
            request = buffer[:size].decode("utf-8")
        if request:      
            if "GET / " in request:
                response = self._handle_get_request(request)
            elif "POST / " in request:  # request_line.startswith("POST"):
                response = self._handle_post_request(request)
            else:
                body = "<h1>400 - Bad Request</h1>"
                response = (
                    "HTTP/1.1 400 Bad Request\r\n"
                    "Content-Type: text/html\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                    f"{body}"
                )

        client.send(response.encode("utf-8"))
        client.close()


    def _handle_get_request(self, request):
        """
        Interne Methode: Bearbeitet GET-Anfragen und liefert das
        HTML-Konfigurationsformular aus.
        """

        body = """
        <html>
        <body>
            <h1>Pico W Konfiguration</h1>
            <form method="POST">
                Name: <input name="name"><br><br>
                Wert: <input name="value"><br><br>
                <button type="submit">Speichern</button>
            </form>
        </body>
        </html>
        """

        return (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
            f"{body}"
        )


    def _handle_post_request(self, request):
        """
        Interne Methode: Bearbeitet POST-Anfragen vom Formular,
        speichert die neuen Einstellungen und löst einen Neustart aus.
        """

        # Header und Body trennen
        parts = request.split("\r\n\r\n", 1)
        body = parts[1] if len(parts) > 1 else ""

        # POST-Formulardaten parsen (key=value&key2=value2)
        data = {}
        if "=" in body:
            for pair in body.split("&"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    data[key] = value

        # Beispiel: Weiterverwendung oder Speicherung
        # Du kannst hier auch Datei schreiben usw.
        # print("POST-Daten:", data)

        confirmation = f"""
        <html>
        <body>
            <h1>Gespeichert!</h1>
            <p>Name: {data.get("name")}</p>
            <p>Wert: {data.get("value")}</p>
            <p>Der Pico startet gleich neu...</p>
        </body>
        </html>
        """

        # Neustart — wenn du möchtest
        # microcontroller.reset()

        return (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html\r\n"
            f"Content-Length: {len(confirmation)}\r\n"
            "Connection: close\r\n\r\n"
            f"{confirmation}"
        )



# ===================================================================
# HAUPTPROGRAMM (Main Logic)
# ===================================================================

# 1. INITIALISIERUNG
#    - Status-LED initialisieren.
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

#    - ConfigManager erstellen und Konfiguration aus "settings.toml" laden.
configManager = ConfigManager(filepath="settings.toml")
config = configManager.load_settings()

#    - NetworkManager erstellen und mit den geladenen WLAN-Daten verbinden.
#      -> Währenddessen Status-LED blinken lassen.
networkManager = NetworkManager(ssid=config["wifi_ssid"], password=config["wifi_password"])
if not networkManager.is_connected():
    led.value = not led.value
    networkManager.connect()
if not networkManager.is_connected():
    exit(1)
print("IP-Adresse:", networkManager.get_ip())

#    - Sensor, MqttClient und WebServer mit den Konfigurationsdaten instanziieren.
sensor = Sensor(pin_number=config["sensor_pin"])
mqttClient = MqttClient(config=config)
webServer = WebServer(config_manager=configManager)

#    - WebServer starten.
webServer.start()


# 2. VERBINDUNGSAUFBAU
#    - Mit dem MqttClient zum Broker verbinden.
mqttClient.connect()

#    - Eine "online"-Statusnachricht senden.
mqttClient.publish_status("online")

#    - Status-LED auf "dauerhaft an" setzen, um Betriebsbereitschaft zu signalisieren.
led.value = True


# 3. HAUPTSCHLEIFE (Endlosschleife)
#    - while True:
#        - MqttClient.loop() aufrufen, um die Verbindung zu halten.
#        - WebServer.poll() aufrufen, um Konfigurationsanfragen zu prüfen.
#
#        - Prüfen, ob das Sende-Intervall (reading_interval_seconds) abgelaufen ist.
#        - WENN ja:
#            a. Daten vom Sensor lesen (Sensor.read_data()).
#            b. WENN Daten gültig sind:
#               - Telemetrie über den MqttClient veröffentlichen.
#            c. WENN Daten ungültig sind:
#               - Fehler loggen oder anzeigen (z.B. durch Blinken der LED).
#
#        - Fehlerbehandlung für getrennte WLAN- oder MQTT-Verbindungen implementieren
#          und versuchen, die Verbindung wiederherzustellen.
t = time.time()
while True:
    mqttClient.loop()
    webServer.poll()
    if (time.time() - t) >= config["reading_interval_seconds"]:
        t = time.time()
        data = sensor.read_data()
        if data:
            mqttClient.publish_telemetry(data)
            print("Daten gesendet:", data)
        else:
            print("Fehler beim Auslesen der Sensordaten.")

    # check every second for connection issues
    if (time.time() - t) >= 1:
        if not networkManager.is_connected():
            print("WLAN-Verbindung verloren. Versuche, erneut zu verbinden...")
            if networkManager.connect():
                print("WLAN-Verbindung wiederhergestellt.")
            else:
                print("Erneuter Verbindungsversuch fehlgeschlagen.")

        if not mqttClient.mqtt_client.is_connected():
            print("MQTT-Verbindung verloren. Versuche, erneut zu verbinden...")
            try:
                mqttClient.connect()
                print("MQTT-Verbindung wiederhergestellt.")
            except Exception as e:
                print(f"Erneuter Verbindungsversuch fehlgeschlagen: {e}")
