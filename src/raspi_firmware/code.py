# code.py

# ===================================================================
# Haupt-Anwendung für das yourmuesli.at IoT Environmental Monitoring
#
# Autor: Degiampietro Martin, Kern Tobias
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
import adafruit_dht as dht
import board
import digitalio
import toml
import wifi
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import adafruit_connection_manager
import json
import socketpool
import board
import wifi
import adafruit_ntp
import rtc

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
    
    def set_ntp_time(self):
        """
        Synchronisiert die Systemzeit mit einem NTP-Server.

        :param timezone_offset: Offset in Stunden zur UTC-Zeit.
        """
        try:
            ntp = adafruit_ntp.NTP(
                socketpool.SocketPool(wifi.radio),
                server="pool.ntp.org"
            )
            clock = rtc.RTC()
            clock.datetime = ntp.datetime
            current_time = time.localtime()
            print(f"Aktuelle NTP-Zeit: {current_time}")
            print("Systemzeit mit NTP synchronisiert.")
        except Exception as e:
            print(f"Fehler bei NTP-Synchronisation: {e}")

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
        try:
            temperature = self.sensor.temperature
            humidity = self.sensor.humidity
            if temperature is None or humidity is None:
                return None
        except Exception as e:
            print(f"Fehler beim Auslesen des Sensors: {e}")
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
        print("Verbinde mit MQTT-Broker...")
        tm = time.localtime()
        timestamp = "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z".format(
            tm[0], tm[1], tm[2], tm[3], tm[4], tm[5]
        )
        offline_payload = {
            "timestamp": timestamp,
            "device_id": self.config["device_id"],
            "status": "offline"
        }
        offline_json = json.dumps(offline_payload)
        self.mqtt_client.will_set(self.config["status_topic"], offline_json, retain=True)
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

        temp_payload = {
            "timestamp": timestamp,
            "device_id": self.config["device_id"],
            "value": data.get("temperature"),
            "unit": "°C"
        }

        humidity_payload = {
            "timestamp": timestamp,
            "device_id": self.config["device_id"],
            "value": data.get("humidity"),
            "unit": "%"
        }

        status_payload = {
            "timestamp": timestamp,
            "device_id": self.config["device_id"],
            "status": "online"
        }

        temperature_json = json.dumps(temp_payload)
        humidity_json = json.dumps(humidity_payload)
        status_json = json.dumps(status_payload)

        self.mqtt_client.publish(self.config["telemetry_topic"]+"/temperature", temperature_json)
        self.mqtt_client.publish(self.config["telemetry_topic"]+"/humidity", humidity_json)
        self.mqtt_client.publish(self.config["status_topic"], status_json)

    def publish_status(self, status: str):
        """
        Sendet eine einfache Statusnachricht (z.B. "online", "rebooting")
        an das definierte Status-Topic.

        :param status: Die zu sendende Statusnachricht.
        """
        print(f"Sende Status: {status}")
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
        print("Starte Webserver...")
        # Falls bereits ein Socket existiert (z.B. nach soft-reload), schließen.
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

        self.server_socket = self.pool.socket()
        for _ in range(3):
            try:
                self.server_socket.bind(("0.0.0.0", self.port))
                print(f"Socket gebunden auf Port {self.port}")
                break
            except OSError as e:
                # EADDRINUSE = 112 on CircuitPython
                if e.errno != 112:
                    raise
                print(f"Port {self.port} belegt, versuche nächsten")
                self.port += 1
        self.server_socket.listen(1)
        self.server_socket.settimeout(0.5)

        print(f"Webserver läuft auf http://{wifi.radio.ipv4_address}:{self.port}")

    def poll(self, config: dict):
        """
        Verarbeitet eine einzelne anstehende HTTP-Anfrage. Muss in der
        Hauptschleife des Programms aufgerufen werden.
        """

        new_config = None

        try:
            client, addr = self.server_socket.accept()
        except Exception:
            # Kein Client wartet, poll kehrt sofort zurück
            return False, new_config

        print("Neue Verbindung von", addr)

        try:
            buffer = bytearray(1024)
            size = client.recv_into(buffer)

            if size <= 0:
                return False, None

            request = buffer[:size].decode("utf-8")
            print("Anfrage:\n", request)
            request_line, body = self._split_request(request)
            method, path = self._parse_request_line(request_line)

            response, new_config = self._route_request(
                method, path, body, config
            )
            print(f"Response:\n{response}")

            client.send(response.encode("utf-8"))

        except Exception as e:
            body = json.dumps({"error": str(e)})
            client.send(self._response(500, body))

        finally:
            client.close()

        return True, new_config

    def _route_request(self, method, path, body, config):
        if method == "GET" and path in ["/config", "/status"]:
            return self._handle_get_request(path), None

        if method == "POST" and path == "/config":
            return self._handle_post_request(body, config)

        return self._response(404, json.dumps({"error": "not found"})), None

    def _handle_get_request(self, path):
        """
        Interne Methode: Bearbeitet GET-Anfragen und liefert das
        HTML-Konfigurationsformular aus.
        """
        if path == "/config":
            settings = self.config_manager.load_settings()
            return self._response(200, json.dumps(settings))
        
        if path == "/status":
            status = {"status": "online"}
            return self._response(200, json.dumps(status))

        return self._response(404, json.dumps({"error": "not found"}))
        
    def _handle_post_request(self, body, config):
        """
        Interne Methode: Bearbeitet POST-Anfragen vom Formular,
        speichert die neuen Einstellungen und löst einen Neustart aus.
        """
        print("POST-Body:", body)
        new_settings = json.loads(body)
        for key, value in new_settings.items():
            config[key] = value
        return self._response(200, json.dumps(config)), config

    def _response(self, code, body):
        return (
            f"HTTP/1.1 {code} OK\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
            f"{body}"
        )

    def _split_request(self, request):
        parts = request.split("\r\n\r\n", 1)
        return parts[0], parts[1] if len(parts) > 1 else ""

    def _parse_request_line(self, request_line):
        line = request_line.split("\r\n", 1)[0]
        parts = line.split()
        method = parts[0]
        path = parts[1]
        return method, path


# ===================================================================
# HAUPTPROGRAMM (Main Logic)
# ===================================================================
print("Starte IoT Environmental Monitoring...")

# 1. INITIALISIERUNG
#    - Status-LED initialisieren.
print("Init: LED")
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

#    - ConfigManager erstellen und Konfiguration aus "settings.toml" laden.
print("Init: ConfigManager")
configManager = ConfigManager(filepath="settings.toml")
config = configManager.load_settings()

#    - NetworkManager erstellen und mit den geladenen WLAN-Daten verbinden.
#      -> Währenddessen Status-LED blinken lassen.
print("Init: NetworkManager")
networkManager = NetworkManager(ssid=config["wifi_ssid"], password=config["wifi_password"])
if not networkManager.is_connected():
    led.value = not led.value
    networkManager.connect()
if not networkManager.is_connected():
    exit(1)
print("IP-Adresse:", networkManager.get_ip())
networkManager.set_ntp_time()

#    - Sensor, MqttClient und WebServer mit den Konfigurationsdaten instanziieren.
print("Init: Sensor, MqttClient, WebServer")
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

def connection_issues_check():
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

while True:
    connection_issues_check()
    mqttClient.loop()
    # check every reading_interval_seconds for sending data
    if (time.time() - t) >= config["reading_interval_seconds"]:
        t = time.time()
        data = sensor.read_data()
        if data:
            mqttClient.publish_telemetry(data)
            print("Daten gesendet:", data)
        else:
            print("Fehler beim Auslesen der Sensordaten.")
    reconnect, new_config = webServer.poll(config)
    if reconnect:
        connection_issues_check()
    if new_config:
        config = new_config
        configManager.save_settings(config)
        print("neue Einstellungen gespeichert")
