---
title: "Industrial Internet of Things Projekt mit Raspberry Pico W"
author: "Martin Degiampietro, Tobias Kern"
format: html
---

## Zusammenfassung der Aufgabenstellung und Ziele

Ziel ist es, eine Lösung zu entwerfen und zu implementieren, die Sensordaten erfasst, diese sicher überträgt und in Echtzeit analysiert, um Anomalien zu erkennen.
Folgende Punkte wurden implementiert:

- Echtzeit-Erfassung von Temperatur und Luftfeuchtigkeit.
- Fernkonfiguration des Geräts über REST-API.
- MQTT-Kommunikation für Telemetriedaten und Statusmeldungen.

## Anleitung für User

### Konfiguration und Start des Mikrocontrollers

#### 1. Vorbereitung

- Raspberry Pi Pico W mit CircuitPython bespielen.
- Notwendige Bibliotheken installieren:
  - `adafruit_minimqtt`
  - `adafruit_connection_manager.mpy`
  - `adafruit_dht`
  - `adafruit_ntp`
  - `adafruit_ticks`
- Sensor an den gewünschten GPIO-Pin anschließen.

#### 2. Konfigurationsdatei anlegen

In der Konfigurationsdatei `settings.toml` die gewünschten Parameter festlegen und überschreiben.
Dafür steht als Vorlage die Dateie `settingsl_template.toml` zur Verfügung.

``` toml
wifi_ssid = "YOUR-WLAN-SSID"
wifi_password = "YOUR-WLAN-PASSWORT"
broker_address = "YOUR-BROKER-ADDRESS"
mqtt_username = "YOUR-USERNAME"
mqtt_password = "YOUR-PASSWORD"
device_id = "YOUR-DEVICE-ID"
sensor_pin = YOUR-SENSOR-PIN
```

#### 3. Raspberry starten

Das Raspberry anstecken und folgende Dateien rüberkopieren:

- `settings.toml`
- `boot.py`
- `code.py`
- die installierten Bibliotheken

Die Status-LED zeigt den Verbindungsstatus:

- Blinkt während WLAN-Verbindung
- Dauerhaft an, wenn betriebsbereit

Über die Serielle Schnittstelle ist es möglich, die Outputs/logs zu lesen.

#### 4. MQTT

Die Sensordaten werden im Intervall `reading_interval_seconds` (der in `settings.toml` festgelegt ist) an den Broker gesendet. Statusmeldungen (`"online", "offline"`) werden über das Status-Topic veröffentlicht.

#### 5. Webserver verwenden

Als Standardport für den Webserver wird port `8080` verwendet. Als fallback wird `8081` genutzt, wenn `8080` nicht verfügbar ist.
Folgende Webserver-Endpunkte stehen zur Verfügung:

- `GET /config` → gesamte Konfiguration als JSON
- `GET /config/KEY` → einzelnen Wert abfragen
- `GET /status` → Status abfragen
- `POST /config` → JSON mit neuen Werten senden, z. B. `{"reading_interval_seconds": 10}`

#### 6. Cloud

Die Passwörter und Einstellungen müssen in `CHANGE-ENV-FILE` geändert werden und die Datei in `.env` umbenannt werden. Danach hat man eine `.env` Datei, mit alle Konfigurationen.
Danach kann der container mit `docker-compose up -d` gestartet werden. Wenn der container neu gestartet wird, müssen die Ordner `influx/data` and `influx/config` gelöscht werden.

### Empfehlungen für die IT-Abteilung

- Webserver ist unverschlüsselt (HTTP). Im produktiven Umfeld VPN oder HTTPS erwägen.
- Keine sensiblen Daten im Klartext speichern, z. B. WLAN-Passwort.
- Bei der Firewall-Konfiguration beachten, dass die benötigten Ports (8080 für den Webserver) freigegebens sind.

## Anleitung für Developer

- Das repository ist als `pdm`-Projekt strukturiert. Nutzen Sie `pdm install`, um die Abhängigkeiten zu installieren.
- Für Dokumentation wurde [Quarto](https://quarto.org/) verwendet, die `quarto-cli`-Befehle sind ebenfalls in der `pdm`-Umgebung verfügbar.
  - Führen Sie `quarto preview` im `docs`-Verzeichnis aus, um die Dokumentation lokal zu starten.
  - Zudem existiert eine github-action zur automatischen Erstellung der Dokumentation, die diese auch automatisch als Website bereitstellt, wenn Sie in den Main-Branch pushen. Wenn sie diese entfernen wollen, müssen sie die Datei `.github/workflows/publish.yml` anpassen.

### Struktur des Projekts

- `docs/`: Quarto Dokumentation
- `docs/iot-specs`: Spezifikationen für IoT-Geräte
- `docs/images`: Bilder für die Dokumentation
- `src/esp32_firmware`: Quellcode mit Ansätzen für die Firmware-Entwicklung
- `src/raspi_firmware`: Quellcode mit Ansätzen für die Firmware-Entwicklung
- `src/cloud`: Quellcode mit Ansätzen für die Cloud-Entwicklung
- `tests/`: Tests für den Quellcode
