# Ebyte-M31-config-tool-linux

Linux-MVP für **dokumentierte Modbus-Funktionen** der Ebyte-M31-Module:
TCP/RTU verbinden, digitale und analoge Werte lesen, einzelne oder mehrere
Coils/Register gezielt schreiben und zurücklesen sowie Messwerte als CSV/XLSX
austauschen. IEEE754-Anzeige, lokale Clientprofile und Geräteparameterstatus
ergänzen den Modbus-Explorer.
Die Tkinter-Oberfläche startet ohne Gerätekommunikation oder Schreibzugriffe.
Der Umsetzungs- und Abnahmeplan steht in [PLAN.md](PLAN.md).

Dies ist **kein vollständiger Nachbau** der Windows-Anwendung. Der belegte
Funktionsumfang, nicht eine uneingeschränkte Eins-zu-eins-Parität, ist das Ziel.
Das Projekt ist unabhängig und inoffiziell; es ist weder mit Ebyte verbunden
noch vom Hersteller empfohlen oder freigegeben. Produktnamen werden nur
zur Beschreibung der Gerätekompatibilität verwendet.

## Vergleich mit dem Windows-Programm

Der Vergleich basiert auf der bisherigen statischen EXE-Untersuchung und
dem M31-Handbuch, nicht auf einem parallelen Windows-Testlauf.

### Öffentlich recherchierte Herstellerquellen

- [M31-AXAX8080G Downloads](https://www.cdebyte.com/products/M31-AXAX8080G/4#Downloads)
- [M31-Handbuch V1.1, 63 Seiten](https://www.cdebyte.com/pdf-down.aspx?id=3402):
  Modbus-Registertabellen in Abschnitt 4.8, Windows-Bedienablauf in Kapitel 5.
- [Offizielles Windows-Tool-Paket](https://www.cdebyte.com/pdf-down.aspx?id=3403):
  `Configuration Tool V1.3.exe`; nur statisch untersucht, nicht ausgeführt.

Die Internetrecherche bestätigt Netzwerk-/Seriellsuche, Parameterverwaltung,
Neustartablauf und Erweiterungsadressverhandlung. Statische Symbole bestätigen
UDP-Broadcast und QXlsx, liefern aber weder ein vollständiges Discovery-
Telegramm noch das Windows-XLSX-Konfigurationsschema. Ein Broadcast auf einen
geratenen Port ist deshalb keine implementierte Hersteller-Discovery.
Das Handbuch nennt außerdem Einschränkungen älterer Host-Firmware beim
Zusammenspiel mit einigen Erweiterungen einschließlich GXAXX0800 (V2.0);
Firmwarekompatibilität muss für die tatsächlichen Geräte bestätigt werden.

### Ergänzende Video-Beobachtungen

Das vom Nutzer bereitgestellte, etwa 3:47 Minuten lange M31-Video zeigt
einen **Firmware-Upgrade-Lehrgang**, keinen vollständigen Funktionsvergleich.
Die lokal geprüften Bildsequenzen und eingeblendeten Texte ergänzen das
Inventar:

- Um 0:55 zeigt die Modulinfo Firmwareversion, Modbus-Adresse,
  Schnittstellentyp und I/O-Ausstattung. Außerdem sind Neustart, Werksreset,
  automatische Adressverhandlung und Adresstabellen-Export sichtbar.
- Der Upgrade-Ablauf verwendet einen eigenen Netzwerk-Upgrade-Assistenten:
  passende Netzwerkkarte auswählen, Firmwaredatei auswählen, Gerät suchen,
  Upgrade auslösen und Fortschritt beobachten. Im Beispiel wird eine
  `.ebin`-Datei für Host-Firmware V1.2 ausgewählt.
- Später wird ein Wiederherstellungsfall mit der physischen Reload-Taste
  und einem im Assistenten als `BOOT` angezeigten Gerät dargestellt.
  Das ist keine Freigabe oder vollständige Wiederherstellungsanleitung
  für beliebige Hardware-/Firmwareversionen.

Die Beobachtungen bestätigen zusätzliche Windows-Bedienoberflächen, liefern
aber weder Discovery-/Firmware-Telegramme noch Firmwaredateiformat,
Prüfsummen, Versionskompatibilität oder eine sichere Recovery-Spezifikation.
Deshalb wird kein Firmwareupdate aus Bildbeobachtungen heraus implementiert
oder am Gerät ausprobiert. Die Videodatei und Einzelbilder werden nicht
im Repository veröffentlicht. Ton wurde nicht automatisch transkribiert;
die Auswertung beruht auf sichtbaren Bildern und Einblendungen.

| Funktion | Linux-Implementierung / Nachweisgrenze |
| --- | --- |
| Modbus TCP, Lesen von DI/DO/Registern | Implementiert; Simulatorprüfungen, Hardware-Lesetest separat |
| Modbus RTU | Implementiert; Mock-Konfiguration geprüft, kein RS485-Aufbau |
| Mehrgerätebetrieb | Explizite generische Modbus-Suche und Auswahl logischer Endpunkte; keine proprietäre UDP-Erkennung |
| Einzelne Coils/Register schreiben (05/06) | Implementiert; Host-Coil 0 live mit Rückstellung geprüft, übrige Schreibtests am Simulator |
| Mehrfachschreiben (0F/10) | Implementiert mit vollständiger Bestätigung und Rücklesen; am Simulator geprüft |
| I/O-Ansicht | Rohregister-Explorer, Adresskatalog und IEEE754-Anzeige mit expliziter Wortreihenfolge; kein vollständiger modularer Gerätebaum |
| Messwerte speichern/laden | Lokaler CSV-/XLSX-Austausch; kein Geräte-Konfigurationsimport |
| XLSX/QXlsx | Eigenes geprüftes Messwertschema; Windows-Konfigurationskompatibilität nicht bestätigt |
| Clientprofile speichern/laden | Versioniertes JSON für Linux-Verbindungseinstellungen; kein Geräte-Konfigurationsformat |
| Vollständiger Modbus-Assistent | Generischer Explorer bietet alle acht Standardfunktionscodes; vollständiges Windows-Verhalten nicht bestätigt |
| Geräteparameter-/Fehlerstatus | Dokumentierte Holdingregister explizit lesbar, unsichere Byteinterpretationen bleiben roh |
| Erweiterungsadressverhandlung | Dokumentierter Ablauf implementiert, separat bestätigt; am Fake-Gerät geprüft, nicht live ausgelöst |
| Netzwerk-/Seriellparameter im Gerät speichern, Neustart | Nicht implementiert; Verbindungseinstellungen verändern nur den Linux-Client |
| Proprietäre UDP-Erkennung, Firmware-Update | Aus Sicherheitsgründen ohne dokumentiertes Protokoll nicht implementiert |

Damit ist eine geprüfte Linux-Anwendung für den genannten Modbus-Umfang
möglich, aber keine bestätigte vollständige Funktionsgleichheit zum
Windows-Zwilling.

## Voraussetzungen und Installation

- Linux, Python **3.10 oder neuer**, `pip` und `venv`.
- **Tkinter ist eine Betriebssystem-Abhängigkeit**, kein pip-Paket. Bei
  Debian/Ubuntu wird es mit `python3-tk` installiert; andere Distributionen
  verwenden beispielsweise `python3-tkinter` oder `python-tkinter`.
  Das Paket muss zur verwendeten Python-Version passen. In der untersuchten
  Umgebung war Python 3.12.3 vorhanden, aber zunächst kein `tkinter`.
- Für die grafische Anwendung ist eine laufende X11-/Wayland-Sitzung nötig.
  Tests und Wheel-Build benötigen keinen Bildschirm.
- Für RTU: ein geeigneter USB-/RS485-Adapter und Zugriffsrechte auf dessen
  serielles Gerät. Keine Anwendung als root starten.

Auf Debian/Ubuntu, **einmalig auf Betriebssystemebene**:

```sh
sudo apt-get update
sudo apt-get install python3 python3-venv python3-pip python3-tk
```

Danach im Projektverzeichnis:

```sh
cd /pfad/zum/Ebyte-Modbus
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -c "import tkinter; print('Tk', tkinter.TkVersion)"
python -m m31tool
```

Das veröffentlichte Repository heißt `Ebyte-M31-config-tool-linux`;
nach dem Klonen entsprechend in diesen Ordner wechseln.

Alternativ startet der installierte Konsolenbefehl `m31tool` dieselbe GUI.
`pymodbus>=3.10,<4`, `pyserial>=3.5,<4` und `openpyxl>=3.1,<4` werden durch die
Projektmetadaten installiert. Bei „No module named tkinter“ die
Betriebssysteminstallation korrigieren, nicht `pip install tkinter` versuchen.
Ein erfolgreicher Tkinter-Import allein bestätigt noch keine grafische Sitzung.

## Verbindung und Bedienung

### Mehrere Geräte auswählen

Eine Modbus-ID ist nicht nur ein Suchmerkmal: insbesondere auf RS485 trägt
**jede Anfrage die Slave-ID ihres Zielgeräts**. Unterschiedliche IDs auf
demselben Bus können unabhängig ausgewählt werden. Broadcast-ID 0 wird
nicht für Geräteschreibzugriffe verwendet.

Die Geräteliste bietet eine ausdrücklich gestartete generische Lese-Suche.
Für TCP werden bekannte Hosts oder ein begrenztes IPv4-Netz sowie der
gewünschte ID-Bereich angegeben; RTU durchsucht die IDs auf dem konfigurierten
seriellen Port mit passenden Busparametern. Keine automatische Netzwerksuche
beim Start. Die Suche kann abgebrochen werden und verändert keine Ausgänge
oder Geräteadressen.

Ein gefundenes Ziel wird ausgewählt und in die Verbindungseinstellungen
übernommen. Zum Wechseln zunächst trennen, dann das andere Ziel verbinden.
Die vorhandenen Lese-/Schreibfunktionen arbeiten anschließend mit dessen
Endpunkt und ID; Bestätigungen nennen weiterhin das konkrete Ziel.

Ein TCP-Gerät kann mehrere IDs beantworten oder ignorieren. Die Liste
zeigt deshalb **logische Modbus-Ziele**, nicht zwingend verschiedene
physische Geräte. Modbus-Leseprobes garantieren keine Erkennung aller
offline, inkompatiblen oder nur über Herstellerprotokolle erreichbaren
Geräte. Geräte-IDs werden nicht automatisch verändert oder neu zugeteilt.
ID-Konflikte auf RS485 müssen vor sicherer Gerätebearbeitung behoben werden.

Die neue Oberfläche trennt Lesen, **Device writes** und **Local files** in
eigene Arbeitsbereiche. Verbindungszustand und Ziel bleiben auch bei
Fehlermeldungen sichtbar; eine Fortschrittsanzeige kennzeichnet laufende
Kommunikation. Tabellen und Status passen sich der Fenstergröße an.
`Ctrl+Tab` wechselt Arbeitsbereiche, Enter in Host-Feldern verbindet,
Enter in Adresse/Anzahl liest und Enter im Katalog bereitet eine Auswahl vor.
Es gibt keine Tastenkombination, die Ausgänge schreibt oder Adressen verhandelt.
Dateiimporte bleiben lokal; bestätigungspflichtige Geräteaktionen bleiben
ausdrücklich getrennt.

Das Redesign orientiert sich an
[GNOME HIG](https://developer.gnome.org/hig/principles.html),
[KDE HIG](https://develop.kde.org/hig/simple_by_default/) und
[WCAG-Fokusanforderungen](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html).
Diese Orientierung ist keine formelle Barrierefreiheitszertifizierung.

1. Modulvariante, Handbuch, Anschlussbelegung und Geräteparameter prüfen.
2. TCP mit der **bekannten Geräte-IP**, dem Modbus-Port (typisch **502**) und
   der passenden Unit-ID verbinden. Keine IP-Adresse des Geräts wird geraten.
   Die Sitzungs-Vorgaben sind Unit-ID **1**, Timeout **2 Sekunden**.
3. Für RTU den richtigen Gerätepfad (z. B. `/dev/ttyUSB0`), Baudrate, Parität,
   Stoppbits und Slave-ID gemäß der tatsächlichen Gerätekonfiguration
   einstellen. RTU verwendet 8 Datenbits; die GUI-Vorgaben sind 9600 Baud,
   Parität N und ein Stoppbit (8N1). Diese sowie die TCP-Vorgaben sind keine
   garantierten M31-Werkseinstellungen.
4. Registertyp, **nullbasierte** Adresse und Anzahl auswählen, dann lesen.
   Modbus-Funktionscodes: Coils **01**, Discrete Inputs **02**,
   Holding Registers **03**, Input Registers **04**.
5. Nur wenn nötig Schreibzugriffe ausdrücklich freigeben, einen Einzelwert
   auswählen und die Bestätigung lesen. Coils verwenden **05**, Holding
   Registers **06**. Mehrere kommagetrennte Werte verwenden **0F** bzw.
   **10**; die Bestätigung zeigt den gesamten Bereich und alle Werte.
   Die Oberfläche liest anschließend sämtliche geschriebenen Werte zurück.
6. CSV-/XLSX-Dateien dienen dem lokalen Austausch von Messwerten; ein Import ist
   **kein** Befehl, diese Werte auf das Gerät zu übertragen.

Im Interpretationstab kann IEEE754-float32 mit `big` (höherwertiges Wort
zuerst) oder `little` (Wörter vertauscht) ausdrücklich ausgewählt werden.
Nur aufeinanderfolgende Registerpaare werden interpretiert; die Rohdaten
und Exporte bleiben unverändert. Das Programm unterstellt keine
modellbezogene Wortreihenfolge oder Skalierung.

Die Clientprofile speichern Transport, Host/Port, serielle Einstellungen,
Unit-ID/Timeout und Leseauswahl in einem eigenen versionierten JSON-Format.
Laden ist nur getrennt vom Gerät möglich und verbindet nicht automatisch.
Profile enthalten keine Ausgangswerte und werden nicht auf das M31 angewendet.

XLSX verwendet genau eine Tabelle mit demselben Header wie CSV und
numerischen Adressen/Werten. Formeln, fehlerhafte Zellen und unpassende
Spalten werden abgewiesen. Dies ist kein Importformat für Windows-
Gerätekonfigurationen. Auch XLSX-Import verändert ausschließlich die lokale
Anzeige.

Das CSV-Format ist UTF-8 mit Komma als Trennzeichen und dem exakten Header
`object_type,address,value`. Zulässige Typen sind `Coils`, `Discrete inputs`,
`Holding registers` und `Input registers`. Adressen liegen in 0–65535,
Bitwerte in 0–1, Registerwerte in 0–65535. Beim Import werden auch
`0x`-Hexzahlen akzeptiert; maximal 100.000 Datenzeilen werden lokal geladen.

```csv
object_type,address,value
Discrete inputs,0,1
Input registers,1000,2500
```

Bei fehlenden seriellen Rechten ist auf vielen Distributionen Mitgliedschaft
in der Gruppe `dialout` nötig (nach einer Änderung erneut anmelden).
Gerätepfad und Distribution prüfen, keine pauschalen `chmod 777`-Rechte setzen.

## Registerkarte und Interpretation

Die folgenden Adressen sind Modbus-PDU-Adressen, **keine** 1-basierten
„40001“-Referenzen. Eine Adresse `0x0000` wird unverändert als `0` gesendet.

| Bereich | Modbus-Tabelle | Adresse hex / dezimal |
| --- | --- | --- |
| Digitale Eingänge DI | Discrete Inputs | `0x0000` / 0 |
| Digitale Ausgänge DO | Coils | `0x0000` / 0 |
| Analoge Eingänge AI, belegte Bereiche | Input Registers | `0x0000` / 0, `0x03E8` / 1000, `0x0BB8` / 3000 |
| Analoge Ausgänge AO, belegte Bereiche | Holding Registers | `0x0000` / 0, `0x03E8` / 1000, `0x01F4` / 500 |
| DI-Filter | Holding Registers | `0x0DA3` / 3491 |
| AI-Filter | Holding Registers | `0x0DA2` / 3490 |

Filterwerte liegen im dokumentierten Bereich **1–16**. Kanalzahl,
Mehrwortlayout, Skalierung, Spannungs-/Strombereich und verfügbare Tabellen
hängen von der Modulvariante ab. Rohregister sind 16-Bit-Werte; unbekannte
Interpretationen werden nicht automatisch als physikalische Messwerte geraten.
Nicht jede Adresse ist auf jedem Modul vorhanden. Die Registerkarte ist kein
Auftrag, alle Bereiche blind zu lesen oder Filter automatisch zu verändern.

## Geräteparameter und fehlende Herstellerprotokolle

Der Geräteparameter-/Status-Tab liest ausdrücklich ausgewählte dokumentierte
Holdingregister: Baudcode, Parität, Netzwerkmodus, DHCP, MAC/IP/Netzmaske/
Gateway/DNS, lokale und Zielports, Zieladresse, Netzwerk-Protokoll,
Adressverhandlungs- und Fehlerstatus. Die Anzeige bewahrt die Rohworte.
Nicht belegte Byte-/Wortreihenfolgen für Netzwerkadressen und Zielstrings
werden nicht stillschweigend geraten. Mehrere Leseanfragen sind kein atomarer
Snapshot; bei Fehlern wird eine ältere Anzeige als veraltet gekennzeichnet.

Die separate Adressverhandlung erfordert eine ausdrückliche Bestätigung:
einmal `1` an `0x7584`, einmal `1` an `0x7585`, danach Statuslesen an
`0x7586` und Fehlerregister `0x7587`/`0x7588`. Sie kann Geräteadressen und
Topologie verändern und wird niemals automatisch ausgelöst.
Die 30-Sekunden-Grenze ist eine Client-Prüfgrenze, keine Herstellerzusage;
ein laufender Austausch unterliegt zusätzlich dem Verbindungstimeout.
Fehler bedeuten möglicherweise veränderten Gerätezustand, nicht Rückstellung.
Nach Abschluss ist die Parameteransicht ausdrücklich neu zu lesen.
Diese Funktion wurde nicht auf dem angeschlossenen Gerät ausgeführt.

**Offene Schritte zur vollständigen Windows-Parität:** Für das konkrete
nicht-U-Modell fehlen veröffentlichte Telegramme zum Parameter-Speichern,
Neustarten, Werksreset und Firmwaretransfer. Das Herstellerhandbuch beschreibt
die Windows-Schaltflächen, aber nicht deren Drahtprotokoll. Ähnlich benannte
Register aus dem anderen M31-U-Handbuch werden nicht übernommen.
Ebenso fehlen Discovery-Port/Payload und ein Windows-XLSX-Exportbeispiel.
Für diesen Restumfang werden Herstellerprotokolle oder nachvollziehbare
Windows-Referenzmitschnitte und Beispieldateien benötigt; ohne sie kann
keine vollständige Funktionsgleichheit bestätigt oder sicher implementiert
werden. Ein Windows-Gegenlauf und reale RS485-Abnahme stehen ebenfalls aus.

## Sicherheit und Hardware-Abnahme

**Keine automatischen Schreibzugriffe:** Start, Verbindung, Lesen und
CSV-Import verändern keine Ausgänge. Jede GUI-Schreiboperation benötigt eine
explizite Freigabe und Einzelbestätigung. Die Core-API schreibt nur bei einem
expliziten Methodenaufruf; deren Protokollbestätigung ersetzt kein Rücklesen.

- Relais können reale Lasten schalten. Vor Tests Lasten sicher trennen;
  Spannungs-/Strom-, Isolation- und Verdrahtungsgrenzen des Herstellers beachten.
- Analogausgänge nur im dokumentierten Bereich und mit geeignetem Messgerät
  prüfen. Rohwerte nicht ohne bestätigte Skalierung verwenden.
- Erfolgreiches Rücklesen beweist den Registerwert, nicht den physischen
  Zustand der Last. Ein Kommunikationsfehler nach dem Schreiben bedeutet
  einen **unbekannten Ausgangszustand**, nicht „es wurde nichts geändert“.
- Fehler nicht durch unkontrolliertes erneutes Schreiben beheben. Der Kern
  vermeidet automatische Telegramm-Wiederholungen.
- Modbus TCP bietet keine Verschlüsselung/Authentifizierung: nur in einem
  vertrauenswürdigen, isolierten Netzwerk verwenden.

Automatisierte Tests verwenden ausschließlich einen lokalen TCP-Simulator.
Die normale Testsuite kontaktiert kein reales Gerät. Ein ausdrücklich
aktivierter Hardware-Lesetest ist davon getrennt. RS485-Elektrik, RTU-Timing
und Lastverhalten sind damit **nicht abgenommen**. Vor produktiver Verwendung
ist eine separate Hardwareprüfung mit sicherem Aufbau nötig.

## Angeschlossener Aufbau

Auf dem bereitgestellten Foto sind Host **AXAX8080G** und die Erweiterungen
**GAXAX8080**, **GAXXX8000** und **GXAXX0800** erkennbar. Zusammen besitzen sie
24 digitale Eingänge, 16 digitale Ausgänge und 8 analoge Eingänge.
Dies beschreibt die Kanalzahl, **nicht deren Modbus-Adressen**; insbesondere
werden Erweiterungsadressen nicht blind aus Kanalzahlen berechnet.

Für die Direktverbindung wurde am 11.10.2026 die Linux-Route zur
dokumentierten Standardadresse `192.168.3.7` über den USB-Ethernet-Adapter
mit Clientadresse `192.168.3.10/24` bestätigt. Die Adresse des jeweiligen
Geräts kann von der Werkseinstellung abweichen. Das Programm ändert weder
den Linux-Netzwerkadapter noch die IP-Adresse des M31.

**Aktualisierter Prüfstand vom 11.10.2026 nach Werksreset:** Der Host
antwortet an `192.168.3.7:502`, Unit-ID 1. DI und DO ab Adresse 0
(je acht Werte) wurden erfolgreich gelesen, alle Werte waren aus.
AI- und DI-Filter lieferten jeweils 6; die exemplarischen AI-Rohregister
bei 0, 1000 (zwei Worte) und 3000 lieferten Null.
Nach ausdrücklicher Bestätigung des Nutzers, dass keine Lasten angeschlossen
sind, wurde ausschließlich Host-DO1 (Coil 0) von aus auf ein geschaltet,
zurückgelesen, auf aus zurückgestellt und erneut zurückgelesen.
Der ursprüngliche Registerzustand ist bestätigt wiederhergestellt.
Die vorherigen Timeouts wurden beim erneuten Test nicht reproduziert;
eine genaue Ursache ist nicht nachgewiesen.
Die Erweiterungszuordnung und physische/elektrische I/O-Wirkung sind noch
nicht verifiziert. Kameraaufnahmen wurden nicht benötigt oder angefertigt.

## Prüf- und Wheel-Build-Befehle

Die folgenden Befehle sind vom Projektverzeichnis aus reproduzierbar
ausführbar. Eine aktivierte `.venv` aus der Installation wird vorausgesetzt.
Es wird **kein pytest** benötigt.

```sh
python -m unittest discover -s tests -v
python -m compileall -q m31tool tests
python -m pip check
python -m pip wheel . --no-deps --wheel-dir dist
```

Tests öffnen nur `127.0.0.1` mit einem vom Betriebssystem zugewiesenen freien
Port. Sie prüfen Lese-Funktionscodes, Nulladressierung, Bit-Padding,
Einzelschreiben und explizites Rücklesen, ignorierte Schreibzugriffe,
Modbus-Exceptions, verkürzte Antworten, Zeitüberschreitungen,
Verbindungsabbrüche und ungültige Argumente. CSV-Tests prüfen Roundtrip,
Header, Grenzen, fehlerhafte Zeilen und den Importumfang.
GUI-Callback-Tests prüfen ohne Tk-Fenster die Schreibbestätigung,
Abbruch, zwingendes Rücklesen und ausschließlich lokalen CSV-Import.
RTU-Konfiguration und Fehler werden mit Mock-Clients geprüft; diese Tests
prüfen keine elektrischen RS485- oder seriellen Drahttelegramme.
Kein Gerät muss erreichbar sein.

`tests/test_gui_desktop.py` prüft zusätzlich echte Tk-Fenster und asynchrone
Kommunikation mit dem lokalen Simulator. Ohne verfügbare grafische Sitzung
werden diese Desktop-Tests ausdrücklich übersprungen.

Der getrennte Hardware-Lesetest ist standardmäßig deaktiviert. Er wird nur
für den hier angeschlossenen Host an `192.168.3.7:502`, Unit-ID 1, aktiviert:

```sh
M31_HARDWARE_READ_TEST=192.168.3.7 python -m unittest tests.test_hardware -v
```

Optional untersucht `M31_HARDWARE_AI=1` zusätzlich dokumentierte AI-Adressen.
Das bestätigt noch keine Adresszuordnung der Erweiterungen.
Der Test schreibt keine Gerätewerte, wiederholt fehlgeschlagene
Kommunikation nicht automatisch und bricht bei Transportfehlern ab.
Erfolgreicher TCP-Verbindungsaufbau allein ist keine bestandene
Modbus-Abnahme: dafür muss eine gültige Modbus-Antwort empfangen werden.

Das gebaute Wheel in einer **separaten Umgebung** prüfen:

```sh
python3 -m venv .wheel-venv
.wheel-venv/bin/python -m pip install dist/m31tool-0.3.0-py3-none-any.whl
.wheel-venv/bin/python -m pip check
(cd .wheel-venv && bin/python -c "import m31tool.core; import m31tool.__main__; print('Wheel-Import OK')")
```

Grafischer Smoke-Test in einer Desktop-Sitzung:

```sh
.wheel-venv/bin/python -m m31tool
```

Das Wheel enthält die Anwendung, nicht Python/Tk selbst. Der Build benötigt
das in `pyproject.toml` deklarierte Setuptools-Backend. Versionsbereiche
garantieren keine bitidentischen Builds über unterschiedliche Zeitpunkte;
für eine eingefrorene Auslieferung Python-, OS- und aufgelöste Paketversionen
zusätzlich dokumentieren (`python --version`, `python -m pip freeze`).

## Bekannte Grenzen

- **Firmware-Update ist nicht implementiert.** Ohne verifiziertes
  Herstellerprotokoll und Wiederherstellungsweg werden keine Firmwaredaten
  an das Modul gesendet.
- **Proprietäre UDP-Geräteerkennung ist nicht implementiert.** TCP benötigt
  eine bekannte Geräteadresse.
- Keine ungesicherten automatischen Änderungen von Netzwerkparametern,
  Geräteidentität oder Neustartverhalten.
- Kein vollständiges Windows-Geräteprofilmanagement oder
  Geräte-Konfigurations-Speichern/Laden/Anwenden. Linux-Clientprofile
  und CSV/XLSX sind lokale Einstellungen bzw. Messwertaustausch, kein Ersatz
  für ein Hersteller-Konfigurationsformat.
- Der generische Modbus-Explorer bietet die acht belegten Standardfunktionscodes,
  ersetzt aber keinen nachgewiesenen vollständigen Windows-Assistenten.
- Das Windows-Programm wurde nur statisch untersucht. Ohne dessen Quellcode,
  vollständige Protokolldokumentation und reale Hardware wird keine
  vollständige Funktionsgleichheit behauptet.

## Herkunft, Lizenzen und Veröffentlichung

Der Quellbaum enthält keine Herstellerprogramme, Firmware, Handbuchkopien,
Logos oder Gerätefotos. Implementierte Schnittstellenparameter werden mit
Herstellerquellen dokumentiert. Die eigenen CSV/XLSX-/Profilformate sind
keine Kopien eines nachgewiesenen Windows-Dateiformats.

Der eigene Projektcode wird unter der [MIT-Lizenz](LICENSE) veröffentlicht:
freie Nutzung, Änderung und Weitergabe mit Erhalt des Lizenzhinweises.
Diese permissive Lizenz wurde entsprechend dem Wunsch nach Open Source
gewählt. Sie erteilt keine Rechte an Marken, Herstellerprogrammen oder
anderem fremdem Material und ist keine rechtliche Freigabe.

Die aktuelle Anwendung importiert diese externen Laufzeitabhängigkeiten;
das Wheel bündelt deren Quellcode nicht:

| Abhängigkeit | Geprüfte Version | Lizenznachweis |
| --- | --- | --- |
| pymodbus | 3.15.0 | BSD-3-Clause |
| pyserial | 3.5 | BSD-3-Clause; vollständigen Release-Lizenztext bei Bündelung mitliefern |
| openpyxl | 3.1.5 | MIT |
| et_xmlfile (indirekt) | 2.0.0 | MIT sowie Python-/PSF-Hinweise für übernommenen Python-Code |

Bei künftiger Bündelung von Abhängigkeiten müssen die zugehörigen Copyright-,
Lizenz- und Haftungshinweise vollständig erhalten bleiben; für et_xmlfile
gehören dazu auch `LICENCE.python` und `AUTHORS.txt`. Keine Autorennamen
als Empfehlung verwenden. Python/Tk und Buildwerkzeuge werden nicht
mitgeliefert. Die rechtliche Prüfung ist keine anwaltliche Beratung und
kann unbekannte Rechte, Verträge oder tatsächliche Übernahmen nicht ausschließen.

`.gitignore` schließt lokale Umgebungen, Builds, `.env` und Messwert-/Profil-
dateien von normalem Git-Tracking aus. Ein explizites `git add -f` umgeht
diesen Schutz. Hardware-Prüfberichte nennen die Hersteller-Werksadresse,
keine Zugangsdaten; individuelle Messwerte und Fotos nicht veröffentlichen.

Relevante Primärquellen für eine fachliche Prüfung:
[UrhG § 69a](https://www.gesetze-im-internet.de/urhg/__69a.html)
(Ausdrucksformen gegenüber Schnittstellenideen),
[§ 69d](https://www.gesetze-im-internet.de/urhg/__69d.html) und
[§ 69e](https://www.gesetze-im-internet.de/urhg/__69e.html)
(Berechtigung und begrenzte Interoperabilitätsausnahmen),
[§ 69g](https://www.gesetze-im-internet.de/urhg/__69g.html),
[GeschGehG § 3](https://www.gesetze-im-internet.de/geschgehg/__3.html)
und [MarkenG § 23](https://www.gesetze-im-internet.de/markeng/__23.html).
Diese Vorschriften sind keine pauschale Erlaubnis für beliebige Übernahmen
oder Analysen. Rechtmäßiger Erwerb, konkrete Analysehandlungen und etwaige
Vertragsbedingungen müssen fallbezogen beurteilt werden. Eine lokale
Codeprüfung kann insbesondere keine allgemeine Freiheit von Patenten,
Marken-, Urheber- oder Geschäftsgeheimnisrechten garantieren.
