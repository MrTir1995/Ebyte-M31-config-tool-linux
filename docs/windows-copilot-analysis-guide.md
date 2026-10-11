# Arbeitsauftrag für Copilot auf Windows: M31-Funktionsanalyse und Registermapping

## Ziel und verbindlicher Umfang

Analysiere das offizielle EBYTE Configuration Tool für **M31 nicht-U** so
genau wie unter den folgenden Sicherheitsgrenzen möglich. Vergleiche die
belegten Funktionen mit diesem Projekt und ergänze fehlende Funktionen nur
auf Grundlage nachvollziehbarer, modellbezogener Protokollnachweise.
Ein sichtbarer Button ist kein Nachweis eines Registerbefehls.
Das Ziel ist geprüfte, evidenzbasierte Funktionsparität, nicht die Behauptung
eines vollständigen Windows-Nachbaus trotz ungeklärter Protokolle.

Diese Anleitung kann als eigenständiger Copilot-Auftrag verwendet werden.
Sie erteilt **keine Freigabe für Gerätekommunikation oder Geräteeingriffe**.
Auch vom Nutzer genannte IP-Adressen sind keine Testanweisung. Plane kleine
Arbeitspakete, delegiere unabhängige Quellen-/UI-/Testaufgaben bei Bedarf,
integriere Ergebnisse und prüfe die gemeinsame Anwendung vor Abschluss.
Sicherheitsgrenzen gelten unverändert für jeden Sub-Agenten.

Projekt: [MrTir1995/Ebyte-M31-config-tool-linux](https://github.com/MrTir1995/Ebyte-M31-config-tool-linux).
Lies zuerst [README](../README.md), [PLAN](../PLAN.md) und das
[Registerinventar](registers/README.md). Bewahre vorhandene lokale Änderungen;
kein Reset, Checkout, Rebase, Commit oder Push ohne entsprechende Freigabe.
Diese Anleitung selbst autorisiert keine spätere Veröffentlichung.

Vom Nutzer berichteter Aufbau: **M31-AXAX8080G** als Host und
**GXAAA0444** als Erweiterung, mit berichteten 8 DI/8 DO am Host und
4 AI/4 DI/4 DO an der Erweiterung. Das ist eine Arbeitsannahme, keine
bestätigte Identifikation oder Registerzuordnung. Erfasse vor jeder
Hardwareauswertung die exakten Typenschilder, Host-/Erweiterungsreihenfolge,
Hardware-Revisionen, Firmwarestände und TCP-/RS485-Verbindung.
Übertrage keine Eigenschaften anderer früher benutzter Erweiterungen.

## Projektbaseline und Abnahmegrenzen

Die Python/Tk-Anwendung unterstützt dokumentiertes Modbus TCP/RTU mit
FC01/02/03/04/05/06/0F/10. Sie startet ohne Geräte-I/O, verwendet explizite
Ziele und bestätigt Ausgabeschreibzugriffe standardmäßig mit Nein sowie
vollständigem Rücklesen. Sie besitzt einen Rohwert-/Registerkatalog,
IEEE754-Anzeige und Float-Eingabe mit expliziter Wortreihenfolge,
CSV/XLSX-Messwertaustausch, versionierte lokale Clientprofile,
Parameter-/Statuslesen, lokale Transport-Hook-Ansicht und optionales
read-only Auto-refresh. Dokumentierte Adressverhandlung ist eine separate,
bestätigungspflichtige Aktion, keine automatische Erkennung.

Nicht als fertig behandeln: proprietäre Suche/UDP-Discovery, Firmware-
Upgrade/Recovery, Geräte-Save/Persistenz, Reset/Reboot, vollständige
Modell-/Firmwareinfo, modularer Gerätebaum, sichere vollständige AI-/AO-
Bereichskonfiguration und Windows-Geräte-Konfigurationsdateischemata.
Clientprofile sind keine Gerätekonfiguration. Ein TX-Hook vor dem Senden
ist kein Zustellnachweis; ein RX-Puffer ist kein unabhängiger Paketmitschnitt.

Stand 11.10.2026: Linux-Integrationssuite **236 Tests, 235 bestanden,
ein expliziter Hardware-Skip**, 38,743 Sekunden. Der anschließend gemeldete
native Windows-Gegenlauf desselben Auto-refresh-Quellstands bestand ebenfalls:
**236 Tests, 235 bestanden, ein Hardware-Skip**, 120,555 Sekunden.
Tests, pip check, Kompilierung, Wheel und GUI-Start/-Ende jeweils Exitcode 0.
Dies prüft **unsere Anwendung**, nicht das Herstellerprotokoll oder reale I/O.
Die frühere Meldung „Windows-Abnahme ausstehend“ ist für diesen Quellstand
damit überholt; für jede spätere Runtime-Änderung ist neu zu prüfen.

Die Hersteller-EXE wurde in der vorhandenen VM durch Defender blockiert.
Eine separat berichtete laufende Windows-UI-Sichtung von Config/IO Status
hatte kein ausgewähltes Gerät; Suche, Save, Restore, Reboot, Export und
Firmware wurden nicht betätigt. Kein erfolgreicher Geräteaustausch ist daraus
belegt. Video-/UI-Beobachtung und unsere nativen Softwaretests bleiben
getrennte Evidenzklassen.

## Windows-Werkzeuge und Einrichtung

Verwende unterstütztes **Python 3.12 mit Tk**, Git und PowerShell.
Erforderliche Python-Abhängigkeiten und Build-Backend stehen in
`pyproject.toml`; keine zusätzlichen Projektpakete auf Verdacht installieren.
Arbeite in einem eigenen Checkout oder einer zuvor vereinbarten Arbeitskopie.
In PowerShell vom Repository-Verzeichnis:

```powershell
git status --short
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q m31tool tests
.\.venv\Scripts\python.exe -m pip wheel --no-deps . --wheel-dir dist
.\.venv\Scripts\python.exe -m m31tool
```

Keine Shell-Aktivierung erforderlich. Prüfe `$LASTEXITCODE` nach jedem
nativen Befehl und brich bei Fehlern ab; eine spätere erfolgreiche Zeile
ersetzt nicht den vorherigen Fehler. Hardware-Testvariablen dürfen bei der
normalen Suite nicht gesetzt sein. Lies UTF-8-Projektartefakte explizit als
UTF-8; ändere nicht global den Textmodus, um Portabilitätsfehler zu verdecken.

| Werkzeug | Zweck und Grenze |
|---|---|
| VM mit Snapshot/isolierter Testumgebung | Reproduzierbarer OS-/Softwarezustand. Kein Schutz vor Schäden an angeschlossenen Ausgängen; keine direkte Hardwareweitergabe ohne Freigabe. |
| PowerShell `Get-FileHash -Algorithm SHA256`, `Get-AuthenticodeSignature`, Dateiversionen | Identität, Herkunft und Signaturstatus protokollieren. Dateiname/Signatur allein beweist weder Sicherheit noch kompatibles Protokoll. |
| Herstellerhandbücher und Downloadpakete | Register-/Modell-/Versionsbelege. Kurz zitieren und Seiten/Hashes festhalten, keine vollständigen PDFs/EXEs/Firmware ins Repository kopieren. |
| Windows UI Automation, Screenshots, manuelle Protokollierung | Tabs, Controls, Zustände, Fehlermeldungen und exakte Bedienfolge erfassen. Sichtbarkeit bedeutet keine Gerätewirkung. |
| Wireshark mit Npcap | Nur genehmigte passive Aufzeichnung auf einem isolierten, nutzerkontrollierten LAN. Kein Discovery-Senden, keine fremden Netzwerke, keine Entschlüsselungs-/Schutzumgehung. |
| Microsoft Sysinternals Procmon | Prozess-, Datei- und Registry-Zugriffe beobachten. Keine Daten verändern; Dateizugriffe erklären noch kein Geräteprotokoll. |
| Microsoft Sysinternals TCPView, optional | Lokale Endpunkte/Verbindungen zuordnen. Portbeobachtung allein beweist weder Payload noch Befehlssemantik. |
| Deterministischer Loopback-Simulator und Projekttests | Decoder/Encoder, Safety, Fehler und UI ohne echte Hardware reproduzieren. Keine elektrische Abnahme. |

Observationstools nur aus offiziellen Quellen und mit Zustimmung installieren.
Keine unbekannten RS485-/Sniffer-Treiber. Npcap beobachtet Ethernet, nicht
automatisch RS485. Für RTU zunächst Dokumentation und Simulator verwenden;
ein physischer passiver Mitschnitt benötigt separat genehmigte geeignete
Hardware, Verkabelung und einen qualifizierten Aufbau.
Keine privaten Quellen, Dumps oder Captures an Drittanbieter/Cloud-LLMs senden.

Bekannte Herstellerquellen:

- [M31-AXAX8080G Downloads](https://www.cdebyte.com/products/M31-AXAX8080G/4#Downloads)
- [Nicht-U-Handbuch V1.1](https://www.cdebyte.com/pdf-down.aspx?id=3402)
- [Configuration Tool, Download id3403](https://www.cdebyte.com/pdf-down.aspx?id=3403)
- [Upgrade Notes id3509](https://www.cdebyte.com/pdf-down.aspx?id=3509), nur statisch lesen
- Weitere chinesische/U-/LoRa-Quellen mit Hashes und Scope im
  [Quellenvergleich](registers/source-comparison.json)

Bekannte EXE-SHA256:
`c4473c9521020043f568d4ba7a2630b4cacb7a731a3635d6d4e8d594a387baee`.
Die erneut geladene id3403-Datei war bytegleich, nicht ein neuer Build.
Bei Defenderblockade **stoppen und dokumentieren**: Defender nicht
deaktivieren, keine Ausschlüsse, kein Unblock-/MOTW-Bypass, keine Binary-Patches
und kein Adminstart zur Umgehung. Static-/Handbuchinventar fortsetzen.
Ausführung nur in einer sauberen autorisierten Windows-Umgebung unter
normaler Sicherheitsrichtlinie bzw. mit einem vom Hersteller freigegebenen,
geeigneten signierten Build, nicht durch Umgehen einer Warnung.

## Sicherheitsvertrag und Stop-Bedingungen

1. Zuerst Offline-/UI-Analyse ohne verbundenes Gerät und ohne Zielauswahl.
   Auch dieses Stadium darf keine Suche oder Netzwerkaktion auslösen.
2. Keine aktiven Netzwerkscans, geratenen UDP-Broadcasts, Register-Sweeps,
   reservierten Bereichsproben oder Versuche an Hypothesenadressen.
3. Keine Live-Writes, Save, Restore, Reboot, Factory Reset, Firmwareupdate,
   Reload-/BOOT-Recovery oder Erweiterungsverhandlung in diesem Analyseauftrag.
4. Passive Captures nur während einer **separat ausdrücklich genehmigten,
   normalen read-only Bedienaktion** auf isolierter Hardware. Dokumentiere
   Ziel, Modell, Firmware, Schnittstelle, ausgewählten Lesebereich und
   Zeitfenster vorher. Ist unklar, ob ein Hersteller-Control schreibt, nicht
   betätigen. Zuerst klären, niemals durch Ausprobieren entscheiden.
5. Spätere absichtliche Schreibtests benötigen eine neue explizite Freigabe:
   ein namentlich genanntes Setting/Register, entbehrliches Testgerät,
   bestätigte ungefährliche Lastsituation, Backup-/Recoveryplan,
   Vorher-/Nachher-Rücklesen und dokumentierten Rücksetzplan. Das ist keine
   Garantie, dass Rollback möglich ist. Unbekannte Persistenz und Nebenwirkungen
   verhindern eine Freigabe, nicht deren Ersatz durch einen geratenen Reset.
6. Firmware/Recovery bleibt außerhalb dieses Auftrags, auch wenn deren
   Oberflächen oder vorhandene Firmwaredateien statisch inventarisiert werden.

Hypothesen sind niemals Schreibberechtigung. Bei unerwartetem Verkehr,
unklarem Ziel, Schutzwarnung, widersprüchlicher Modellidentität oder
undokumentierten Seiteneffekten stoppen und einen klaren Blocker melden.
Nicht alle offenen Registerfragen müssen durch Tests auflösbar sein.

## Methode: vollständiges UI- und Funktionsinventar

Erstelle eine eigene Funktionsmatrix, keine bloße Liste sichtbarer Buttons.
Erfasse alle Tabs, Menüs, Kontextmenüs und gefahrlos zugänglichen Dialoge:
Search/Discovery, TCP/seriell, Config, IO Status, Info/Identität/Firmware,
Lesen/Schreiben, Save/Persistenz, Restore/Reset/Reboot, Negotiation,
Export/Import, Upgrade/Recovery und Logs.
Unsichere Controls bleiben **sichtbar, nicht betätigt**.

Jede Zeile benötigt:

| Feld | Erwarteter Inhalt |
|---|---|
| ID, Feature und UI-Pfad | Eindeutige Funktion, Tab/Dialog/Control, Text und Tastaturzugang |
| Vorbedingungen | OS/Toolversion, Geräteauswahl, Transport, Modell/Firmware, erforderliche Verbindung |
| Verhalten | Default, gültige Eingaben, deaktivierte Zustände, Bestätigungen, Fehler und angezeigte Ergebnisse |
| Bedienfolge/Evidenz | Einzelne Aktionen in Reihenfolge, Screenshots/Video-Zeitstempel, Quelle/Seite/Commit |
| Wirkung/Sicherheit | Nur lokale UI, mögliche I/O, Lesen, Schreiben, Persistenz, Reset oder Firmware; unbekannt ausdrücklich markieren |
| Linux-Vergleich | Implementiert, teilweise, fehlend, ungeklärt; betroffene Projektpfade und Tests |
| Nachweisgrenze | Nur UI beobachtet, Herstellerangabe, passiver Drahtnachweis, Communitybericht oder Hypothese |

Protokolliere Windows-Build, Locale/Codepage, Display-/DPI-Skalierung,
Python/Tk/Abhängigkeitsversionen, Tool-Dateihash und Signaturstatus.
Fehlersituationen dürfen nur offline oder am Simulator erzeugt werden,
solange keine sichere Live-Freigabe vorliegt. Sichtbare Defaultwerte sind
keine aus einem Gerät gelesenen Werte. „Nicht beobachtet“ ist nicht „fehlt“.

Priorisiere anschließend belegte Lücken nach Nutzen, Evidenz und Risiko.
UI-Layout kann unabhängig vom Geräteprotokoll verbessert werden; gerätespezifische
Funktionen bleiben gesperrt, bis ihr vollständiger Ablauf geklärt ist.

## Registermapping: Ausgangsbasis und Datenvertrag

Vorhandene Artefakte zuerst lesen und erweitern, nicht durch eine neue
ungeprüfte Gesamtkarte ersetzen:

- [Primärinventar](registers/non-u-en-v1.1.json): 13 nicht-U-Registertabellen,
  30 reguläre Definitionen plus AO-Konfliktbehauptung.
- [Hostbereiche](registers/known-host-ranges.csv) und
  [Handbuch-Prozesswerte](registers/analog-process-values.csv).
- [Modellvergleich](registers/cross-model-comparison.csv) und
  [U-only Register](registers/u-only-registers.csv).
- [Hypothesen H1–H6](registers/hypotheses.json) und
  [GitHub-/Forenevidenz](registers/community-evidence.json).

Für jedes Feld/Familie erfassen: stabiler Schlüssel, Modbus-Tabelle und FC,
nullbasierte PDU-Adresse in Hex/Dezimal, gedruckte Vendor-Referenz,
Wort-/Bitanzahl, Kanalstride und Grenzen, Datentyp, Zugriff, Default,
Einheit/Skalierung, Bit-/Byte-/Wortreihenfolge, Stringpacking, Modell,
Host/Erweiterung, Firmware-/HW-Scope, genaue Quelle mit URL/Hash/Seite bzw.
Commit/Zeilen, Konflikte, Extraktionsvertrauen und Hardware-Nachweis.
Unsichere Endianness nicht aus einem plausiblen Messwert erraten.

PDU-Adressen sind **nullbasiert**. Numerische Referenzspalten verwenden
häufig Adresse +1; Vendor-Präfixe 0/1/3/4 bezeichnen verschiedene Tabellen.
FC01-Coil0, FC02-DI0, FC03-Holding0 und FC04-Input0 sind nicht dasselbe Feld.
Erhalte falsche gedruckte Referenzen unverändert als Quelle und dokumentiere
die Normalisierung getrennt. Ein Blockread definiert nicht jedes gelesene
Wort semantisch; eine Ausnahme beweist nicht universelle Nichtverfügbarkeit.

Nicht-U, U, U-Erweiterung, LoRa und andere Generationen strikt trennen.
DI-/AI-Filter zeigen reale Gegenbeispiele für blinde Serienübertragung.
Mehrfach kopierte Manuals, Übersetzungen, unser Repository oder
Community-Code mit denselben Manualwerten sind keine unabhängige
Hardwarebestätigung. Community-Code bleibt code-derived/reported, bis
attributierbare Modell-/Firmware-Captures oder Herstellerbelege vorliegen.

Bekannte sichere Grenzen des operativen Katalogs:
17 Geräte-Lesefelder, exakte Readspans `(0x7530,15)`, `(0x7541,68)`,
`(0x7586,4)`; undefinierte `0x753F`/`0x7540` nicht auffüllen.
Verhandlungsauslöser `0x7585` bleibt außerhalb der Lesevorbereitung.
Float-Familien haben zwei Worte je Wert/Stride2; übrige Kanalfolgen
häufig Stride1. Fortsetzung je I/O-Typ ist nicht ein universeller
Block pro Erweiterung, Slot oder Slave-ID.

### Offene Fragen, die ausdrücklich aufzulösen oder offen zu lassen sind

| Gruppe | Frage und erforderlicher Nachweis |
|---|---|
| H1 | Nicht-U Modell-/Firmware-/Identitätsregister: U-Adressen sind kein Beleg für Nicht-U. Herstellerbestätigung oder autorisierte passive Info-Lesesequenz nötig. |
| H2 | Erweiterungsdescriptoren, Firmwarefelder, Slotarrays und Reihenfolge: Host/Erweiterung/Slot/Unit-ID nicht gleichsetzen; 16 Module und 32 Beschreibungs-/Bitmapplätze können verschiedene Grenzen sein. |
| H3 | Reboot-/Resetbefehle: U-Kandidaten nicht übertragen, keine Live-Probe. Nur bereits vorliegende belastbare Hersteller-/Capturebelege auswerten. |
| H4 | `0x753F..0x7540`: Gap/Reserved/Legacy/anderes Feld bleibt unbekannt. Kein Sweep; ein Community-89-Wort-Read ist keine Semantik. |
| H5 | Save-to-flash/Persistenz: bisher keine gerechtfertigte Nicht-U-Adresse. Auto-Persistenz, Commit und Reload unterscheiden, niemals Speicherregister erfinden. |
| H6 | UDP-Discovery/Firmware-Wireprotokoll: sichtbare Assistenten und UDP-Modus sind keine Payloadspezifikation. Firmware bleibt außerhalb der aktiven Tests. |
| AO-Konflikt | Nicht-U-Tabelle nennt `0x1194`, Prosa `0x0DAC`: U-Übereinstimmung löst Nicht-U-Hardware nicht auf. Kein Bereichssetter vor modellbezogenem Nachweis. |
| Formate/Beispiele | AO-Prozesswertreferenz, signed16-Dezimal/Hex, Spannungs-Einheiten, DI-Beispielendadresse, Kanalzahlen und Float-Strides getrennt prüfen. Eine berechnete Korrektur ist keine Herstellerkorrektur. |
| Expansionen | GXAAA0444-Typenschild/Counts, tatsächlich angehängte I/O-Familien, Offset-/Kanalzuordnung, Fehlerbitmap und Verhandlungssemantik konkret belegen; keine Zuordnung aus Modellnamen oder Bitmap raten. |

Führe ein Unresolved-Ledger mit Frage, Kandidaten, Quelle, Gegenbeleg,
fehlender Evidenz, Falsifikationskriterium, Risikoklasse und nächstem
zulässigen Schritt. Status: dokumentiert, beobachtet, reported,
candidate, conflict oder unbekannt; getrennte Hardwareverified-Angabe.
Neue Musterkandidaten bleiben inert, mit Runtime-/Autoprobe-/Autowrite-Flags
false, auch wenn mehrere Dokumente dasselbe Muster wiederholen.

## Passive Evidenz und Auswertung

Nur nach konkreter read-only Freigabe: das genaue UI-Control und einen
benannten Lesebereich bedienen, sonst nichts. Isoliertes Interface,
Capture-Zeitfenster, Prozess, Ziel und erlaubte Aktion vorab festhalten.
Originalcapture lokal zugriffsgeschützt erhalten und hashen.
Kein Mitschnitt fremder Geräte oder Zugangsdaten.

Jeder ausgewertete Austausch benötigt UTC-Zeitstempel, Geräte-/Firmware-
Scope, Bedienaktions-ID, vollständige Request-/Responsebytes und
Frame-/Streamreferenz. Modbus TCP: MBAP Transaction-ID, Protocol-ID,
Length, Unit-ID, FC, Startadresse/Count und Antwort/Exception zuordnen;
TCP-Segmente rekonstruieren, nicht mit einzelnen Nachrichten gleichsetzen.
RTU nur bei genehmigtem passivem Aufbau: Serialparameter, Adresse/FC,
Framegrenzen und CRC prüfen. Nicht-Modbus-Payloads ausdrücklich als
unbekannt markieren, nicht in erfundene Register umdeuten.

Nur eine passende Antwort, nachvollziehbare Datentypinterpretation und
konkreter Scope tragen eine Mappingaussage. UI-Werte, Netzwerkantworten
und elektrische Signale sind getrennte Nachweise. MAC/IP/Seriennummern,
Hostnamen und personenbezogene Daten vor jeder Weitergabe redigieren;
identische pseudonyme IDs behalten, Redaktionen und ihre Grenze nennen.
Originale nicht öffentlich committen. Im Projekt nur kurze eigene
Beschreibungen, zitierbare Quellen und synthetische Regression-Vektoren.

## Umsetzung, Prüfung und Lieferung

1. Sichere statische Quellen-/UI-Baseline und vollständige Funktionsmatrix
   erstellen; Blockaden und nicht betätigte Controls dokumentieren.
2. Lücken, Quellenkonflikte und die zugelassene nächste Evidenzarbeit festlegen.
   Noch unbekannte Befehle bleiben nicht implementierte Grenzen.
3. Falls genehmigt, normale read-only Aktionen passiv erfassen; bestehende
   Captures offline auswerten. Keine Discovery-, Write- oder Firmwaretests.
4. Mapping mit Scope/Zitaten/Konflikten erweitern; Artefaktschema,
   Adresskonvention, Counts/Strides und Hypothesentrennung testen.
   `tests/test_register_inventory.py` und bestehende Helpers wiederverwenden.
5. Belegte Funktionen zuerst lokal am deterministischen Simulator
   implementieren. Vorschau, Default-Nein, exakte Ziele und Rücklesen für
   zulässige spätere Writes beibehalten; keine automatischen Writes/Retries.
6. Tests für Erfolg, Exception, Timeout, Teilantwort, Cancel, Invalid-Input,
   no-I/O beim Start/Import/Katalog, Worker/Tk-Lifecycle, Dateihandles,
   große Fonts/DPI und native Windows-Textdefaults ergänzen.
7. Fokussierte und volle Linux-/native Windows-Suiten, compileall, pip check,
   Wheel und separat installierten GUI-Start/-Ende prüfen. Keine Hardware
   während der Standardabnahme; Hardware nur mit neuer expliziter Freigabe.
8. Gemeinsamen Diff, Testzahlen/Skips/Exitcodes, Logs und Source-/Wheel-SHA256
   liefern; verbleibende Paritäts-/Hardwarefragen sichtbar lassen.
   Unterschiedliche Windows-/Linux-Wheelhashes sind kein automatischer Fehler.

Lieferartefakte: Funktionsmatrix, Quellen-/Tool-Provenanz, redigierter
Evidenzindex, aktualisiertes Mapping und Unresolved-Ledger, kleine
Implementierungsänderungen samt Regressionstests, Nutzungs-/Safety-Doku
und exakte Abnahmeergebnisse. Keine vollständigen Herstellerdateien,
Firmware, geheimen Daten oder fremden Implementierungen übernehmen.

Vor jeder später ausdrücklich freigegebenen Veröffentlichung: `git status`,
beabsichtigte Dateien und cached Diff prüfen, Remote-HEAD vergleichen,
nur Fast-forward und niemals Force-Push. Die vier dokumentierenden CSV
unter `docs/registers/` werden vom allgemeinen `*.csv`-Ignore erfasst;
nur diese geprüften Forschungsartefakte gezielt aufnehmen, nicht beliebige
Messwertexporte oder Build-/Capturedateien. Bei Divergenz oder unbekannten
Änderungen stoppen. Ohne weitere Quellen kann der Auftrag mit einem
präzisen Ledger abgeschlossen werden, aber niemals mit erfundener
vollständiger Hersteller-Parität.
