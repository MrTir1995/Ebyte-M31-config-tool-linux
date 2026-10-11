# M31 Linux-Anwendung: Umsetzungs-, Prüf- und Build-Plan

## Ziel und belastbarer Umfang

Eine Linux-Desktop-Anwendung als sicherer, nachvollziehbarer M31-Modbus-MVP. Die belegten Modbus-TCP- und Modbus-RTU-Funktionen werden über eine grafische Oberfläche zugänglich: Verbindung, Lesen der M31-I/O-Tabellen, gezieltes Schreiben einzelner Ausgänge/Register mit ausdrücklicher Bestätigung und Rücklesen, sowie CSV-Import/-Export für Messwerte. M31-Registeradressen werden entsprechend dem Handbuch beschriftet. Netzwerk- und Geräteparameter, deren Änderungs-/Neustartverhalten nicht hinreichend spezifiziert ist, werden nicht automatisch verändert.

Das Windows-Programm wurde nur statisch untersucht; Quellcode und proprietäre Protokolldetails liegen nicht vor. Daher werden keine Gleichwertigkeit für undokumentierte Funktionen und kein vollständiger Funktionsumfang behauptet. Insbesondere werden Firmware-Update und proprietäre UDP-Geräteerkennung nicht implementiert. Diese Lücken werden in Anwendung und Anleitung kenntlich gemacht. Reale Geräte sind für diesen Auftrag nicht verfügbar; die Abnahme erfolgt mit deterministischen Simulatoren. Hardware-/Elektriktests bleiben erforderlich.

## Technischer Ansatz

- Python 3, Tkinter/ttk für eine leichte Linux-GUI; keine externe GUI-Laufzeit.
- `pymodbus` für Modbus TCP/RTU und `pyserial` für serielle Schnittstellen; Versionen werden in den Projektmetadaten festgelegt.
- Klare Trennung von Protokoll/Adressmodell und GUI; keine Kommunikation oder Schreibzugriffe beim Programmstart.
- Gerätetyp-/Registerprofile folgen den im Handbuch belegten Adressen. Unbekannte oder modellabhängige Details werden nicht geraten.
- Schreibzugriffe sind standardmäßig deaktiviert, müssen einzeln bestätigt und anschließend zurückgelesen werden. Hinweise zu Relaislasten und Analogbereichen sind sichtbar.

## Arbeitspakete und Abhängigkeiten

1. **Projekt-/Abnahmeplan** (unabhängig): Umfang, Paritätslücken, Kriterien, Prüf- und Build-Ablauf festhalten.
2. **Modbus-Kern und Registermodell** (abhängig von 1): TCP/RTU-Transport, Lesen/Schreiben, Handbuchadressen, Verbindungsfehler klar melden; keine Schreibzugriffe ohne expliziten Aufruf.
3. **Desktop-Oberfläche** (abhängig von 1; Integration mit 2): Verbindungsdialog/-status, Register-/I/O-Ansicht, explizite Schreibbestätigung, CSV-Funktionen und sichtbare Funktionsgrenzen.
4. **Tests und Simulator** (abhängig von 2): deterministische Protokolltests für Adressierung, Lese-/Schreibfunktionen und Fehler; gezielte GUI-/CSV-Prüfungen.
5. **Anleitung, Paketierung und Build** (abhängig von 2–4): Linux-Nutzung, Sicherheits-/Hardwarehinweise, Abhängigkeits- und Startdefinition, Build/Installationsprüfung.
6. **Integration und Abnahme** (abhängig von 2–5): Tests/Build ausführen, Ergebnisse korrigieren und dokumentieren.

## Akzeptanzkriterien

- Eine Linux-GUI lässt sich aus dem Projekt starten und zeigt Verbindung, Registertyp, Adresse und Werte an.
- TCP und RTU sind als Transportarten auswählbar; ungültige Verbindungen/Antworten erzeugen eine sichtbare Fehlermeldung, keinen scheinbaren Erfolg.
- Handbuch-Adressen für DI/DO/AI/AO und die bekannten Filterregister sind nachvollziehbar beschriftet.
- Es gibt keine automatischen Änderungen am Gerät. Jeder angebotene Ausgangs-/Register-Schreibzugriff verlangt eine explizite Bestätigung und Rückleseprüfung; Fehler beim Rücklesen werden angezeigt.
- CSV-Export/Import hat einen definierten, geprüften Inhalt und verändert beim Import nicht unaufgefordert das Gerät.
- Automatisierte Tests benötigen keine reale M31-Hardware. Die Anleitung kennzeichnet nicht implementierte Windows-Funktionen und notwendige Hardwarevalidierung.
- Abhängigkeiten und reproduzierbare Build-/Startschritte sind festgelegt; Tests und Build laufen erfolgreich in der Zielumgebung oder verbleibende externe Beschränkungen sind konkret ausgewiesen.

## Prüf- und Build-Ablauf

1. Unit-Tests gegen deterministische Modbus-TCP-/RTU-Simulatoren ausführen; Lese-/Schreibtelegramme, Fehlerantworten, Zeitüberschreitungen und Rückleseabweichungen prüfen.
2. Registerprofile und Grenzwerte gegen das M31-Handbuch prüfen; insbesondere DI/DO ab 0x0000, AI Input Registers 0x0000/0x03E8/0x0BB8, AO Holding Registers 0x0000/0x03E8/0x01F4 sowie Filter 0x0DA3/0x0DA2 (Werte 1–16).
3. CSV-Import/-Export testen; Import bleibt lokal und löst keine Geräteschreibzugriffe aus.
4. GUI mit `python -m m31tool` starten und grundlegende Bedienung/Fehlerdarstellung prüfen.
5. Abhängigkeiten installieren und Paket-Wheel mit `python -m pip wheel . --no-deps` bauen; Paketinhalt/Startmodul prüfen.
6. Erst nach bestandenen Simulatorprüfungen an realer Hardware verifizieren. Vor Ausgangstests Last-/Verdrahtungsgrenzen beachten; keine Firmware- oder Netzwerkänderung ohne Herstellerprotokoll und gesicherten Wiederherstellungsweg.

## Explizite Paritätslücken / späterer Ausbau

Die statische Untersuchung des Windows-Programms deutet auf zusätzliches Geräteprofilmanagement, Speichern/Laden/Anwenden von Konfigurationen, Modbus-Assistent, XLSX/QXlsx sowie Firmwareauswahl/-update hin. Diese Funktionen werden nur ergänzt, wenn ihr Datenmodell und Verhalten ausreichend dokumentiert sind. Proprietäre UDP-Discovery und Firmwareupdate bleiben ausgeschlossen, solange kein verifiziertes sicheres Protokoll vorliegt. Eine verbindliche Eins-zu-eins-Paritätsaussage ist mangels Windows-Quellcode, vollständigem Parametersatz und Hardware nicht möglich.

## Durchgeführte Integration und Prüfungen

- Die delegierten Beiträge für Modbus-Kern, Tkinter-Oberfläche sowie Simulator-Tests/Paketierung/Anleitung wurden integriert. Der Implementierungsstand umfasst TCP/RTU-Transport, manuelles Lesen, bestätigtes Einzel-Schreiben mit verpflichtendem Rücklesen, lokale CSV-Verarbeitung und sichtbare Sicherheits-/Paritätshinweise.
- `python -m unittest discover -v`: **46 Tests bestanden**; TCP-Simulator, RTU-Konfiguration via Mocks, Registermodell, CSV und GUI-Sicherheitscallbacks.
- `python -m compileall -q m31tool tests`: bestanden.
- `python -m pip check`: keine defekten Abhängigkeiten.
- `python -m pip wheel . --no-deps --wheel-dir dist`: Wheel `m31tool-0.1.0-py3-none-any.whl` erfolgreich gebaut.
- Wheel separat unter `build/wheel-verify` installiert; isolierte Imports von `m31tool.core` und `m31tool.__main__` bestanden.
- `python -m m31tool` wurde ausgeführt. Tkinter fehlt im Prüfhost; die Anwendung meldet dafür die notwendige Betriebssystemabhängigkeit verständlich und startet nicht. Ein echter Fenster-/Desktop-Smoke-Test ist dadurch offen.
- Kein M31-Gerät oder RS485-Testaufbau verfügbar: physische I/O-Wirkung, elektrische Sicherheit und RTU-Drahtkommunikation bleiben vor produktiver Nutzung auf Hardware zu prüfen.

## Hardware- und Desktop-Abnahme vom 11.10.2026

Diese zweite Abnahme aktualisiert den früheren Prüfstand: Tkinter 8.6 ist
jetzt verfügbar. Der USB-Ethernet-Adapter hat 192.168.3.10/24 und die Route
zu 192.168.3.7 führt über diesen Adapter, nicht über WLAN.
Am Foto erkennbare Hardware: Host AXAX8080G, Erweiterungen GAXAX8080,
GAXXX8000 und GXAXX0800. Die Erweiterungsadressen werden nicht aus der
Kanalanzahl abgeleitet.

### Verteilte Aufgaben

1. **Sub-Agent Hardware/Kern:** Erreichbarkeit und dokumentierte Leseoperationen
   am einzelnen Host 192.168.3.7:502 prüfen, begrenzt und ohne Netzwerkscan.
   Wiederholbaren, ausdrücklich aktivierbaren Hardware-Lesetest hinzufügen.
   Gefundene Kernfehler mit Regressionstests beheben; keine echten
   Schreibzugriffe, Netzwerkänderungen, Resets oder Firmwareaktionen.
2. **Sub-Agent Desktop:** Echtes Tk-Fenster mit lokaler Simulationsverbindung
   prüfen: Verbindung, Lesen, Anzeige, CSV, bestätigte/abgebrochene
   Schreiboperationen und Fehlerdarstellung. Gefundene GUI-Fehler beheben
   und automatisierte Tests ergänzen. Kein Zugriff auf reale Ausgänge.
3. **Integration/Paketierung (Hauptagent):** Beiträge und Windows-Paritätsgrenzen
   zusammenführen, Anleitung/Abnahmestatus aktualisieren, gesamte Tests,
   Kompilierung, Abhängigkeiten und frisch gebautes/installiertes Wheel prüfen.

Hardware- und Desktop-Paket sind unabhängig; Integration benötigt beide.
Abnahme bedeutet überprüfte Linux-Funktionen, nicht behauptete vollständige
Windows-Parität: Firmware, proprietäre Discovery, Netzwerkparameter,
XLSX und vollständige Geräteprofile sind weiterhin belegte Lücken.
Reale Ausgangsschreibtests und RS485-Tests bleiben ohne einen ausdrücklich
freigegebenen sicheren Testaufbau ausgeschlossen.

### Ergebnis dieser Abnahme

- Beide Sub-Agent-Beiträge wurden integriert: `tests/test_gui_desktop.py`
  prüft vier echte Tk-/Simulatorabläufe; `tests/test_hardware.py` enthält
  den ausdrücklich aktivierbaren Hardware-Lesetest und Sicherheitsprüfungen.
  `tests/test_core.py` erhielt einen Telegramm-Framing-Regressionstest.
  In diesen Prüfungen wurde kein reproduzierbarer Produktfehler nachgewiesen;
  die Anwendung wurde deshalb nicht spekulativ geändert.
- Finale Standardsuite: **56 Tests ausgeführt, 55 bestanden, 1 Hardware-Test
  erwartungsgemäß übersprungen**. Kompilierung und `pip check` bestanden.
- Echtes Desktop-Fenster und separat installiertes Wheel wurden geprüft:
  getrennte Startverbindung, Registerkatalog, Simulatorlesen, CSV,
  Abbruch von Schreibbestätigungen und Simulator-Schreiben mit Rücklesen.
  Der frühere Tkinter-Blocker ist damit behoben.
- **Hardware-Abnahme nicht bestanden:** `192.168.3.7:502`, Unit-ID 1,
  akzeptiert TCP-Verbindungen, aber liefert bei DI-Lesen (02, Adresse 0,
  Anzahl 8) binnen 2 Sekunden keine Antwort. Der explizite Hardware-Test
  schlägt korrekt fehl. Route läuft über den USB-Adapter; Nachbar erreichbar.
- Zur Abgrenzung hat der Hardware-Sub-Agent unabhängige rohe Modbus-TCP-Lese-
  telegramme für DI, Coils und DI-Filter gesendet. Alle drei empfingen null
  Bytes innerhalb der Zeitgrenze. Das DI-Telegramm des Kerns entspricht exakt
  `000100000006010200000008`; kein Client-Framingfehler wurde nachgewiesen.
- Keine echten Geräte-Schreibzugriffe, Neustarts oder Netzwerkänderungen.
  Gerätemodus, tatsächliche Modbus-Adresse und Portkonfiguration müssen
  geprüft werden; ein TCP-Handshake allein bestätigt keinen Modbus-TCP-Modus.
  Vollständige Windows-Parität bleibt ausdrücklich unbestätigt.

## Erneuter Test nach Werksreset

Der Nutzer hat die zuvor geänderte Hardwareadresse gemeldet und das Gerät
auf Werkseinstellungen zurückgesetzt. Zwei unabhängige Sub-Agent-Aufträge:
Hardware-Lesetest an 192.168.3.7:502/Unit 1 und tatsächlicher GUI-Lesepfad
mit anschließenden Simulator-Regressionsprüfungen. Danach werden Ergebnisse
und gegebenenfalls nachgewiesene Fehlerkorrekturen integriert.
Es werden keine echten Ausgänge geschaltet, solange Lasten und sichere
Testbedingungen ungeklärt sind. Eine optionale Webcam-Verifikation kann
Register-Rücklesen oder die elektrische Sicherheitsprüfung nicht ersetzen.

Der Nutzer hat anschließend ausdrücklich bestätigt, dass keine Lasten
angeschlossen sind. Damit ist ein begrenzter Test des Host-DO1 (Coil 0)
freigegeben: Ausgangszustand lesen, einmal umschalten, rücklesen und auf den
Ausgangszustand zurücksetzen. Voraussetzung sind gültige Leseantworten.
Bei Kommunikationsfehlern wird kein blinder Schaltversuch durchgeführt.
Ohne unabhängige optische/elektrische Beobachtung bestätigt Rücklesen nur
den Modbus-Wert, nicht die physische Ausgangswirkung.

### Ergebnis nach erneuter Bereitschaft des Hosts

Die frühen Versuche direkt nach dem gemeldeten Werksreset liefen noch in
Timeouts. Ein nachfolgender unabhängiger DO-Leseversuch antwortete gültig.
Die genaue Ursache dieses Übergangs ist nicht nachgewiesen.

- Hardware-Sub-Agent: Coil 0 vorher aus, einmal ein geschaltet und ein
  zurückgelesen, auf aus zurückgestellt und aus zurückgelesen. Beide
  Schreibantworten gültig; ursprünglicher Registerzustand bestätigt.
  DI-Filter 3491 lieferte 6. Keine weiteren Schreibzugriffe.
- Integrierter Hardware-Lesetest danach mit optionalen AI-Reads bestanden:
  acht DI und acht DO ab 0 jeweils aus, Filter 3490/3491 jeweils 6,
  AI-Rohwerte Adresse 0: [0], 1000: [0, 0], 3000: [0].
- Endpoint 192.168.3.7:502, Unit 1, null Wiederholungen, USB-Adapterroute.
  Host-Lesen und Einzel-Coil-Schreiben/Rücklesen damit live bestätigt.
  Erweiterungsadressierung, physische Ausgangswirkung, AI-Skalierung,
  RTU und vollständige Windows-Parität bleiben ungeprüft.
- Keine Webcam-Aufnahmen; Rücklesen bestätigt keine elektrische Wirkung.
- Desktop-Sub-Agent: echter Tk-GUI-Lesepfad an derselben Hardware erfolgreich,
  DI 0–7 und Coils 0–7 jeweils acht angezeigte Nullen, keine Dialogfehler;
  Verbindung anschließend getrennt und Fenster geschlossen. Keine
  Programmfehler reproduziert, daher keine spekulativen Codeänderungen.

## Ausbauauftrag: vollständige Windows-Parität

Der Nutzer verlangt einen vollständigen Funktionsvergleich, Internetrecherche
und verteilte Umsetzung. Der vorhandene Hardwaretest bestätigt nur einen
Teil des Modbus-Umfangs; er ist keine Windows-Paritätsabnahme.

1. **Herstellerrecherche (Sub-Agent):** öffentliche Handbücher,
   Softwareanleitungen und Downloads prüfen; Funktionen und Protokolle mit
   Quellen belegen. Lokale Dateien und Hardwaredaten werden nicht hochgeladen.
2. **Lokales Inventar (Sub-Agent):** vorhandene Implementierung und Tests
   den bekannten Funktionen zuordnen; konkrete sichere Umsetzungspakete
   und fehlende Belege identifizieren.
3. **Umsetzung:** belegte, voneinander trennbare Funktionslücken an
   Implementierungs-Sub-Agents verteilen; gemeinsame API und Datei-Zuständigkeit
   festlegen. Undokumentierte Vendor-Telegramme nicht ausprobieren.
4. **Integration:** alle Ergebnisse zusammenführen und Simulator-,
   Desktop-, Paket- und gegebenenfalls ausdrücklich sichere Hardwareprüfungen
   ausführen. Quellen, tatsächlich erreichte Parität und verbleibende
   externe Blocker in der Anleitung festhalten.

Vollständige Parität benötigt eine belastbare Windows-Funktionsbaseline
und hinreichende Protokolldokumentation. Firmwareänderungen, Gerätestarts
und Netzwerk-Konfigurationsänderungen werden nicht allein aus der allgemeinen
Paritätsanforderung auf der angeschlossenen Hardware ausprobiert.

### Konkrete delegierte Umsetzungspakete

- **Modbus-Kern:** standardkonforme Mehrfachschreibfunktionen 0F/10,
  Vorabvalidierung und Antwortprüfung sowie Simulator-Regressionsprüfungen.
- **Datenformate:** IEEE754-Konvertierung mit expliziter Wortreihenfolge,
  lokaler XLSX-Messwertimport/-export und versionierte Linux-Clientprofile.
  Diese Profile werden nicht als Windows-Konfigurationsformat ausgegeben.
- **Desktop:** alle genannten APIs in die GUI integrieren, Mehrfachschreiben
  bestätigen und vollständig rücklesen, Rohwerte erhalten, CSV/XLSX-Import
  ausschließlich lokal, Profile laden ohne Verbindung oder Geräteschreiben.
- **Abnahme:** vollständige Standardsuite, echte Tk-Tests, Build und
  isoliertes Wheel prüfen. Reale Mehrfachausgänge und Gerätparameter werden
  bei diesem Ausbau nicht blind verändert.

Die Recherche hat zusätzliche Geräte-Holdingregister für Netzwerk,
serielle Parameter, Adressverhandlung und Fehlerstatus nachgewiesen.
Ein weiteres Sub-Agent-Paket ergänzt deshalb eine explizite lesende
Geräteparameter-/Statusansicht. Herstellerquellen werden in README.md
verlinkt. UDP-Port und Discovery-Payload, Firmware-Transfer-/Recovery-
Protokoll sowie Windows-XLSX-Konfigurationsschema sind weiterhin
nicht hinreichend belegt; diese Funktionen werden nicht erfunden.

Die vollständige primäre Registertabelle wurde auf Herstellerbelege geprüft:
Save/Restart/Version/Softwareoffset-Telegramme fehlen für das nicht-U-Modell.
Die belegte Adressverhandlung (7584/7585/7586–7589) wurde deshalb separat
implementiert und mit Fake-Zeitgebern und echten Tk-Widgets getestet.
Sie benötigt eine Default-Nein-Bestätigung und verändert niemals automatisch
beim Verbinden, Laden oder Importieren den Host. Keine Live-Verhandlung
oder Gerätekonfigurationsänderung während dieses Ausbaus.

## UI-Neugestaltung vor Veröffentlichung

Die Sub-Agent-Recherche nennt GNOME/KDE HIG und WCAG als Orientierung;
Web-spezifische DOM/ARIA-Regeln gelten nicht unverändert für Tk.
Ein unabhängiges Tk-Inventar bestätigt Verbesserungsbedarf bei
Verbindungsidentität, Tastaturbedienung, Größenanpassung und Fortschritt.

1. **Implementierungs-Sub-Agent:** vorhandenes ttk beibehalten, klare
   Verbindungskopfzeile, geordnete Arbeitsbereiche und konsistente Abstände,
   flexibles Layout, sichtbare Datenherkunft und Fortschrittsanzeige.
   Katalog per Tastatur bedienbar; keine Schreib-Shortcuts.
2. **Prüf-Sub-Agent:** neue unabhängige Tk-Layout-/Tastaturtests für
   850x680 und 1280x800, Busy/Status/Verbindungsidentität, Quellenanzeigen
   und weiterhin sichere Bestätigungen.
3. **Integration:** bestehende Regressionstests und neue Prüfungen ausführen,
   Anleitung aktualisieren und finales Wheel prüfen.

Alle bestehenden Modbus-, CSV/XLSX-, Profil-, Interpretations- und
Gerätefunktionen bleiben erhalten. Keine automatische Verbindung,
Schreibaktion, Adressverhandlung oder Kameraaufnahme.
Veröffentlichungsziel laut Nutzer: Ebyte-M31-config-tool-linux,
Open Source; permissive MIT-Lizenz als begründete Standardwahl.

### Finaler integrierter Release-Stand

Alle delegierten UI-Beiträge integriert; unabhängige Tests fanden und
bestätigten Korrekturen für Footer-Clipping und Timer nach Fensterschließung.
142 Tests ausgeführt: 141 bestanden, ein ausdrücklich aktivierbarer
Hardwaretest standardmäßig übersprungen. Kompilierung und Abhängigkeiten
geprüft. Die tatsächliche Hardware-Leseabnahme und DO1-Rückstellung
aus dem vorherigen Prüfstand bleiben separat dokumentiert.

Eigener Code unter MIT; externe Abhängigkeiten werden nicht im Wheel
gebündelt. Keine nachgewiesene Rechteverletzung im begrenzten Herkunfts-
und Lizenzcheck gefunden, jedoch keine verbindliche Rechtsfreigabe.
Herstellerprogramme, Fotos, lokale Umgebungen, Messwerte und Builds werden
nicht in das öffentliche Git-Repository aufgenommen.
Vollständige Windows-Parität bleibt wegen fehlender Herstellerprotokolle
und Referenzdateiformate unbestätigt.

## Mehrgerätebetrieb im Netzwerk und auf RS485

Der Nutzer verlangt Anzeige und Bearbeitung mehrerer Geräte ohne Bindung
an eine einzige vorbelegte ID. Modbus-Zielidentität bleibt dabei erhalten:
auf RTU wird jede Anfrage an die konkrete Slave-ID adressiert; ID 0
(Broadcast) wird nicht zur Bearbeitung verwendet.

- Sub-Agent Domain: ausdrücklich gestartete, begrenzte TCP-/RTU-Suche
  an vom Nutzer vorgegebenen Hosts/CIDR und IDs, ausschließlich Leseprobes,
  Abbruchmöglichkeit und dokumentierte Fehler; keine Erfolgserkennung nur
  anhand eines TCP-Handshakes.
- Sub-Agent GUI: Geräteliste mit logischen Endpunkten und IDs, Suche,
  Abbruch und Auswahl zum Vorbereiten der vorhandenen Geräteverbindung.
  Keine automatischen Scans, Verbindungen oder Schreibaktionen.
- Integration: Simulator-/GUI-Prüfung, Build und kleine Hardware-Leseprobe
  am ausdrücklich freigegebenen Host; bestätigte Geräteaktionen bleiben
  an das ausgewählte Ziel gebunden.

Die generische Modbus-Suche ist kein Nachbau der proprietären
Hersteller-UDP-Erkennung. Mehrere TCP-IDs können dasselbe physische Gerät
ansprechen; Einträge sind daher logische Ziele, keine gesicherte Hardwarezählung.
Geräte-ID-Änderung selbst bleibt ohne dokumentiertes gerätespezifisches
Verfahren ausgeschlossen. Defekte/offline oder nicht mit Modbus sprechende
Teilnehmer können mit dieser Suche nicht garantiert gefunden werden.

### Mehrgeräte-Abnahme

Beide Sub-Agent-Beiträge integriert; gefundene Transport-Normalisierung
zwischen Domain und GUI sowie Tk-Variablen-/Worker-Lebenszyklusfehler
mit Regressionstests behoben. Finale Suite: 179 ausgeführt, 178 bestanden,
ein expliziter Hardwaretest standardmäßig übersprungen. Kompilierung,
Abhängigkeiten, Wheel 0.3.0 und installierte Tk-Anwendung geprüft.
Die neue Suche fand das freigegebene Ziel 192.168.3.7/Unit 1 mit einer
gültigen Leseantwort; GUI-Auswahl übernahm TCP-Endpunkt und ID korrekt.
Keine breite Netzwerksuche, RS485-Drahtabnahme oder Geräte-Schreibzugriffe.

## Ergänzende Videoquelle

Der Nutzer hat ein 226,815 Sekunden langes M31-Upgradevideo bereitgestellt.
Lokale Sichtung anhand einer zeitlichen Bildübersicht und Detailframes:
Modulinfo/Firmwareversion, eigene Netzwerk-Upgradeoberfläche,
Netzwerkkartenauswahl, Firmwaredatei, Gerätesuche und Upgradefortschritt
sowie ein Reload-/BOOT-Recoveryfall sind sichtbar.
Das Video ergänzt die Funktionsbaseline, enthält in den geprüften
Bildsequenzen jedoch keine verifizierbaren Drahtprotokolle.
Keine Firmwareaktion, kein Hardware-Reset, keine Änderung aus geratenen
Telegrammen. Datei und Frames bleiben außerhalb des öffentlichen Projekts.
README dokumentiert die Beobachtungen und deren Grenzen; keine neue
Funktionsgleichheit oder automatische Tontranskription wird behauptet.

## Native Windows-Fehler und blockierte Herstellerreferenz

Die neue EXE ist laut lokalem Vergleich bytegleich zur bisherigen
`Configuration Tool V1.3.exe` (SHA256 siehe README). Windows Defender
blockiert ihre Ausführung. Schutz, Registrierung und Betriebssystem-
Lizenzbedingungen werden nicht umgangen; ohne lauffähige autorisierte
Referenz bleibt die Laufzeit-Paritätsabnahme blockiert.

Der Testlauf unserer Python-Anwendung in der Windows-VM ist keine
Herstellerreferenzprüfung. Er findet ohne M31-Hardware statt. Die erste
native Prüfung fand einen XLSX-Handlefehler sowie ein Minimumfensterproblem.
Nach deren Korrektur meldete der vollständige Windows-Gegenlauf einen
Font-Overflow-Testfehler und `Tcl_AsyncDelete` mit Prozessabbruch. Ein
Windows-Gesamterfolg wird nicht aus Linux-Tests oder Standalone-Smokes
abgeleitet.

Aktuelles Arbeitspaket:

1. Worker-Exception-Tracebackketten vor der Übergabe an den Tk-Thread lösen,
   damit alte Tk-Interpreter nicht durch spätere Worker-GC finalisiert werden.
   Fehlerklasse, Fehlermeldung und Exception-Verkettung bleiben erhalten.
2. App-eigene Timer und Root-Fokusbindung bei Zerstörung entfernen.
   Testfixtures einschließlich zyklischer Dialog-Mockreferenzen nach allen
   Patch-Cleanups auf dem Tk-Hauptthread freigeben. Keine ausgeblendeten Tests,
   keine Abschaltung der Worker-GC und keine Test-pro-Test-Prozessisolation.
3. Der separate Windows-Traceback zeigt verbleibenden vertikalen Overflow
   nach Anforderung von 1600x1200. Der Test hatte dabei weiterhin 24px-Fonts
   und Skalierung 2.0 aktiv; er prüfte keine Rückkehr zum normalen Layout.
   Jetzt stellt er die tatsächlichen ursprünglichen Fonts, Skalierung und
   Status zurück und prüft scrollfreie Erholung auch bei auf 1280x800
   begrenzter Maximalgeometrie. Die exakten Scroll-/Bounds-Assertions bleiben
   erhalten; native Windows-Geometriemessungen und Gegenlauf stehen aus.
4. Linux-Gesamtsuite, Kompilierung, Abhängigkeiten und Wheel prüfen; danach
   den vollständigen nativen Windows-Lauf erneut ausführen lassen.

Undokumentierte Discovery-/Firmware-/Recovery-Telegramme, Geräteparameter-
Speicherung, Neustart/Reset und Windows-Konfigurationsdateischemata bleiben
offene Inventarlücken. Es werden keine Befehle aus UI-Bildern oder ähnlichen
Geräteserien erfunden.

### Bestätigte native Windows-Abnahme des korrigierten Stands 0.3.0

Am 11.10.2026 meldete der Windows-Prüfagent den vollständigen Lauf:
185 Tests in 90,982 Sekunden, 184 bestanden und ein Hardwaretest
übersprungen. Kein Tcl-Abbruch; Großschriftprüfung erfolgreich. Kompilierung,
Abhängigkeiten, Wheel-Build sowie GUI-Start/-Ende waren ebenfalls erfolgreich.
Eingefrorene Gastquelle: `frozen-source-20261011-080337`,
gemeldeter Quellarchiv-SHA256:
`85aff5f2391d610d292968f6fe7d347e1c8ef91880870a1977015c0bd025c0c3`.
Das Windows-Wheel ist nicht als byteidentisch zum Linux-Wheel ausgewiesen.

Die alte native Font-Messprobe belegte die fehlerhafte Testprämisse:
1600x1200 war angefordert, aber tatsächlich 1284x781 bei 1280x800 Bildschirm
und `maxsize=1284x781`. Canvas: 1245x647; benötigter Inhalt: 1131x890 bei
Skalierung ca.2.0. Verbleibender Overflow bei weiterhin großen Fonts war
damit korrekt, kein Beleg für einen stale Scrollbereich. Der korrigierte
Test stellt Fonts/Skalierung zurück und prüft echte Layout-Erholung.
Diese Abnahme gilt nicht automatisch für spätere Funktionsergänzungen.

## Belegter Funktionsabgleich und Ergänzungen 0.4.0

Nutzerauftrag: Funktionsumfang mit dem offiziellen Tool abgleichen und
belegte Lücken ergänzen. Drei gezielte Sub-Agent-Pakete wurden tatsächlich
ausgeführt: Primärhandbuch/Upgrade-Dokumentation, lokale Float-Schreibkodierung,
echte Transportbeobachtung. Die Implementierungsbeiträge wurden integriert.
Hardware und Hersteller-EXE bleiben getrennte Nachweisgrenzen.

| Oberfläche | Vorhanden / ergänzt | Offene Grenze |
| --- | --- | --- |
| TCP/RTU und Geräteauswahl | Alle acht Standard-FCs, explizite begrenzte Suche und logische Endpunkte | Keine garantierte physische Gerätezählung, keine proprietäre UDP-Erkennung |
| DI/DO | Rohwert-Lesen, bestätigtes Einzel-/Mehrfachschreiben mit Rücklesen | Gerätebaum und aktuelle elektrische Hardwareabnahme fehlen |
| AI/AO | Roh-/IEEE754-Lesen; neue Float-Schreibeingabe mit ausdrücklich gewählter Wortreihenfolge und zwei Registern je Wert | Keine automatische Kanal-/Einheiten-/Modellerkennung |
| Filter / Messbereiche | DI/AI-Filterbounds bereits geprüft; neue AI-/AO-Rohwert-Leseeinträge mit Quellenhinweisen | Kein Messbereich-Setter ohne Modellbeleg; AO-Adresswiderspruch bleibt offen |
| Modell / Erweiterungen | Dokumentierter Fehlerstatus und Rohbitmap, bestätigungspflichtige Adressverhandlung | Kein Modell-/Firmware-/Kanalanzahlregister belegt; keine Bitmap-Kanalzuordnung geraten |
| Netzwerk / seriell | Clientparameter und dokumentierte Geräte-Rohwerte/Enums lesbar | Kein sicherer Hersteller-Speichern-/Neustart-/Resetablauf oder ungeklärte IP-Byteordnung |
| Profile / XLSX / CSV | Eigenes Client-JSON und lokale Rohwertformate | Kein nachgewiesenes Windows-Geräte-Konfigurationsschema |
| Modbus-Assistent | Neue lokale Refresh-/Copy-/Clear-Ansicht echter pymodbus-Transport-Hooks | TX-Versuch/RX-Puffer sind kein PCAP oder physischer Zustellnachweis; keine beliebigen Telegramme |
| Firmware / Recovery | Offizielle Anleitung statisch gelesen | Keine Transfer-/Discovery-/Recovery-Spezifikation; keine Firmwareaktion implementiert |

Float-Akzeptanz: keine implizite Wortreihenfolge, nur Holdingregister,
1–61 endliche Dezimalwerte, vollständige Vorschau der Kodierung, genau
FC10-Schreiben plus FC03-Rücklesen aller Rohworte. Abbruch/ungültige Eingabe
verursachen keine I/O; Abweichung, Timeout oder Fehler sind kein Erfolg und
lösen keine automatische Wiederholung aus.

Trace-Akzeptanz: ausschließlich tatsächliche Bibliotheks-Hookbytes unverändert
zurückgeben, TX-Versuch/RX-Puffer ausdrücklich benennen, 500 Einträge begrenzen
und Verlust zählen; Anzeigen/Kopieren/Löschen bleiben lokal. Simulatorprüfungen
vergleichen beobachtete ADUs mit unabhängig erzeugten erwarteten Modbusbytes.

AI-Messbereichsbasis 0x0DAC ist in §4.4.1/§4.8.3 konsistent; erlaubte
elektrische Modellklassen sind nicht zuverlässig einem beliebigen Modellnamen
zugeordnet. AO-Tabelle §4.8.4 nennt 0x1194, AO-Fließtext §4.5.1 dagegen
0x0DAC. Keine ungeprüfte Auflösung dieses Konflikts und keine automatische
Expansionsoffsetannahme. Die neuen Katalogeinträge bereiten nur Lesen vor.

Das offizielle Upgrade-Notes-Archiv (id=3509) enthält ein DOCX-Tutorial,
eine v1.2-EXE und eine .ebin-Datei. Nur Dokumenttext/Bilder wurden statisch
gelesen: keine Protokollspezifikation, dafür ausdrückliche Warnung vor
Konfigurationsverlust nach Firmwareupgrade. Keine EXE-/Firmwareausführung
oder Veröffentlichung von Herstellerartefakten.

Abnahmefolge: gezielte neue Codec-/Core-/GUI-Tests, Linux-Gesamtsuite,
Tk-GC-/Großschriftregression, Build/Installations-Smoke; danach erneuten
vollständigen nativen Windows-Lauf auf dem neuen eingefrorenen Stand.
Keine produktiven Hardwarezugriffe, bis das aktuelle Modulziel und die
Verbindungs-/Modellparameter ausdrücklich geklärt sind.

### Bestätigte Abnahme der Erweiterungen 0.4.0

Linux: vollständige Suite mit 215 Tests, 214 bestanden, ein expliziter
Hardwaretest übersprungen. Zusätzlich 122 GUI-Prüfungen in einem Prozess
mit paralleler Worker-GC bestanden. Kompilierung, Abhängigkeiten und
Wheel-Build erfolgreich. Das separat installierte Wheel wurde mit acht
Ansichten, exakt kodiertem Float-Schreiben/Rücklesen am Loopback-Simulator,
echtem Trace-Kopieren/-Löschen und sauberem Worker-/Tk-Ende geprüft.

Der vollständige native Windows-Gegenlauf bestand ebenfalls:
215 Tests in 107,764 Sekunden, 214 bestanden und ein Hardwaretest
übersprungen, kein `Tcl_AsyncDelete`. Tests, Abhängigkeitsprüfung,
Kompilierung, Wheel-Build und GUI-Start/-Ende meldeten jeweils Exitcode 0.
Gastquelle: `C:\M31Tests\frozen-source-20261011-082005`,
gemeldeter Quellarchiv-SHA256:
`957a8723b2c375a16f7fc6a9cd88bca01645c463e810e484a9786aa91c5c0ecd`.
Windows-Wheel: 48.798 Bytes, SHA256
`fbdb2489ac0ef0a350567e9dc459ead8a24304ae6bfa824964a95f90bc7790cb`.
Keine Bytegleichheit zum Linux-Wheel behauptet. Nach dieser Abnahme wurden
nur README/PLAN um die Ergebnisse ergänzt, keine Laufzeit-/Testquellen verändert.

Damit sind die belegten 0.4.0-Ergänzungen geprüft, **nicht die vollständige
Hersteller-Parität**. Proprietäre Discovery, Firmware/Recovery, Modell-
Identifikations-/Gerätebaumprotokoll, Windows-Geräteprofilschema, Parameter-
Persistenz/Neustart/Reset, sichere vollständige Messbereich-Konfiguration
und aktuelle reale Hardware-/RS485-Abnahme bleiben offen. Keine Geräte-
Schreibzugriffe oder erneute Hersteller-EXE-Ausführung in dieser Abnahme.

## Detailrecherche und Registerinventar 0.5.0

Nutzerauftrag: alle bekannten M31-Register detailliert recherchieren,
wiederkehrende Muster vergleichen und Hinweise aus GitHub/Foren einbeziehen.
Der Koordinator beauftragte drei unabhängige Recherchepakete
(englisches nicht-U-Vollinventar, chinesische/alternative Modellreihen,
GitHub-/Forenbefunde). Nach deren Abschluss wurde ein gezielter Integrations-
Sub-Agent für maschinenlesbare Artefakte und deren Regressionstests eingesetzt.
Keine Recherche wurde als reale Hardwareprüfung ausgegeben.

Umfang: vollständige 13 Tabellen der englischen nicht-U-Primärquelle,
30 reguläre Definitionen plus eine AO-Konfliktbehauptung; separate
Quellen-/Modellvergleiche und inerte Hypothesengruppen. U-spezifische
Register und Community-Code bleiben getrennt, niemals automatisch
nicht-U-Schreiboptionen. Mehrfach vorkommende Quellentexte und Spiegel
derselben PDF sind keine mehrfach unabhängigen Bestätigungen.

Implementierung: die 17 bereits gelesenen Geräteparameter werden auch im
Lesevorbereitungs-Katalog sichtbar, mit genauen Mehrwortlängen und
Quellenhinweisen. Bestehende drei Geräte-Readspans bleiben unverändert;
Verhandlungsauslöser 0x7585 und undefinierte Lücken 0x753F/0x7540 werden
nicht in die Lesevorbereitung aufgenommen. DHCP-Codes 0/1 sind als
belegtes Enum lesbar. Analog-Katalogtexte benennen dokumentierte Formate,
Strides und Konflikte, ohne Messwerte automatisch neu zu skalieren.
Keine neue Bereichs-/Parameter-Schreibfunktion, keine RawWrite-Umstellung.

Abnahme: Artefakte auf Adresskonventionen, Quellen-/Modellbindung,
vollständige Tabelle-/Definitionenabdeckung, Kanalstrides und sichere
Hypothesentrennung prüfen. GUI-Auswahl aller Gerätefelder muss korrekte
Readadresse/-länge vorbereiten und null I/O erzeugen; aktive Befehle,
U-Identitätskandidaten und Reservierungen bleiben ausgeschlossen.
Danach Linux-Gesamtsuite, Build/Installations-Smoke und vollständiger
nativer Windows-Gegenlauf auf dem neuen eingefrorenen Stand.

### Abnahme des Registerinventars 0.5.0

Linux-Gesamtsuite: 229 Tests, 228 bestanden und ein Hardwaretest übersprungen.
Die 13 Offline-Inventartests prüfen Quellenbindung, Adresskonventionen,
Modell-/Kanalzahlen, Strides, Konflikte, Community-/U-Abgrenzung, inerte
Hypothesen und lokale CRC-/Framebeispiele. Der separat installierte
0.5.0-Wheel-Smoke bestätigte alle 29 Katalogeinträge, die korrekten
Wortanzahlen der 17 Gerätefelder, Auswahl ohne Gerätekommunikation und
sauberes Schließen.

Der erste native Windows-Lauf fand eine Test-Portabilitätslücke: ein
README-Artefakt wurde ohne explizite UTF-8-Kodierung gelesen. Diese eng
begrenzte Stelle wurde korrigiert; andere Artefaktreads waren bereits
explizit UTF-8. Keine globale UTF-8-Modusänderung oder Runtime-Umgehung.
13 Inventartests bestanden auch mit simuliertem Windows-Textdefault.

Der vollständige korrigierte native Windows-Lauf bestand am 11.10.2026:
**229 Tests in 103,377 Sekunden, 228 bestanden, ein Hardwaretest übersprungen**,
mit normalem Windows-ACP ohne UTF-8-Override und ohne Tcl-Abbruch.
Tests, Abhängigkeiten, Kompilierung, Wheel-Build sowie GUI-Start/-Ende
meldeten jeweils Exitcode 0. Gastquelle:
`frozen-source-20261011-090849`, Quellarchiv-SHA256
`2990cab9874fd5420ea175506d74527b16473375cd8c8a4798ea9dfe6185b9ad`.
Alle Registerartefakte waren im Prüfarchiv enthalten.
Windows-Wheel: 50.331 Bytes, SHA256
`d8c96899485e055a16cb9cd5ab383eb448d83e3a5caa069a12227869c4517c14`;
keine Bytegleichheit zum Linux-Wheel behauptet.
Nach dieser Abnahme wurden ausschließlich Ergebnisdokumentationen ergänzt.

Damit ist der beauftragte belegte Registervergleich einschließlich
separater Musterhypothesen abgeschlossen. Verborgene Firmwareadressen,
aktuelle Hardwareverifikation und vollständige Hersteller-Parität
werden nicht behauptet. Keine EXE-Ausführung oder Hardwarezugriffe
waren Teil dieser Recherche und Integration.

## Selektive Feature-Integration aus 0109f9a

Der dokumentarische Main-Commit 36d0a1b enthält keine Programmänderungen.
Ein separater Branch 0109f9a ergänzt read-only Auto-refresh. Arbeitsteilung:
isolierte Branch-Abnahme, separater Main-Test-/Build-Agent und lokale
Integration mit installiertem GUI-Smoke. Bestehende uncommittete Float-,
Trace-, Registerinventar- und Tk-Lifecycle-Arbeit bleibt erhalten; kein
Dateiersatz, Checkout oder History-Merge.

Begrenzte Integration: optionales Auto-refresh samt Intervall, serieller
Worker-Ausführung, Fehlerabschaltung, Timerfreigabe bei Trennen/Schließen/
direktem Destroy und Regression für ungültige Adresse/Anzahl/Intervall.
Der vorhandene XLSX-ExitStack bleibt: die isolierten adversarial Prüfungen
belegten kein zusätzliches OS-Dateideskriptorleck durch fehlenden ZIP-Wrapper.
Hardware-Test-Gate-Erweiterungen sind nicht Teil dieses begrenzten Pakets.
Akzeptanz: fokussierte GUI/Safety/Layout-Tests, vollständige Suite,
Kompilierung, pip check, Wheel-Build und Installations-Smoke. Keine Hardware
oder Hersteller-EXE ausführen. Die frühere Windows-Abnahme 0.5.0 gilt nicht
automatisch für diesen erweiterten Stand.

Linux-Integrationsabnahme: 31 fokussierte Tests in 12,102 Sekunden bestanden;
vollständige Suite mit 236 Tests in 38,743 Sekunden, 235 bestanden und ein
expliziter Hardwaretest übersprungen. Unittest, compileall, pip check,
Wheel-Build und diff check jeweils Exitcode 0. Das separat installierte
Wheel bestand den realen Tk-/Loopback-Smoke mit deaktiviertem Startzustand,
read-only Wiederholung, Invalid-Input-Abschaltung und sauberer Timerfreigabe.
Die Runtime-Dateien im Wheel stimmen mit den geprüften Quellen überein.
Zum Zeitpunkt dieser Linux-Prüfung stand die erneute native Windows-Abnahme
noch aus. Es erfolgte keine Hardwareaktion; die vollständige Dateiliste
einschließlich der älteren lokalen Arbeit wurde vor Veröffentlichung vorgelegt.

Der frische native Windows-Gegenlauf bestand anschließend: 236 Tests in
120,555 Sekunden, 235 bestanden und ein Hardware-Skip; Tests, pip check,
Kompilierung, Wheel und GUI jeweils Exitcode 0. Gastquelle:
`C:\M31Tests\frozen-source-20261011-142708`, Quellbundle-SHA256
`4c0043bbd0a1dc86413ce5406effe7d76e8cacf64e3239df7115c3119bbe7e28`.
app.py entspricht dem oben geprüften Stand, SHA256
`d7fbada157a7c61aff01a33995481a8f2063aaf2d8b7a2b05de3226faaf43469`.
Windows-Wheel: 51.462 Bytes, SHA256
`77491ac777927f97ed55f1bba8f5f26315fa4d7e6725782615afbf400b1e242e`.
Keine Bytegleichheit zum Linux-Wheel und keine Hersteller-/Hardwareparität
behauptet. Zusätzlich bestanden unter Linux 130 wiederholte GUI-Tests mit
paralleler Worker-GC in 65,891 Sekunden.

Auf zusätzlichen Nutzerauftrag wurde die eigenständige deutsche
`docs/windows-copilot-analysis-guide.md` erstellt: Windows-Werkzeuge,
Quellen-/UI-Provenanz, Sicherheitsvertrag, Funktionsmatrix, Registermapping
mit H1–H6/Konflikten, zulässige passive Evidenz und Implementierungsabnahme.
Keine Schutzumgehung, kein automatischer Registerscan und keine
Geräte-/Firmwarefreigabe durch diese Anleitung.
