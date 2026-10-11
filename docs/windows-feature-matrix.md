# M31 nicht-U: Windows-Funktionsmatrix und Evidenzlücken

Stand: **11.10.2026**. Arbeitsartefakt zur
[Windows-Copilot-Anleitung](windows-copilot-analysis-guide.md), keine
Hersteller-Paritätsabnahme und keine Freigabe für Geräteaktionen.
Hier wurden ausschließlich vorhandene, attribuierte Projektbelege ausgewertet:
keine neue EXE-Sichtung, Netzwerkanfrage, Gerätekommunikation oder Messung.
Die Matrix beschreibt Funktionen statt eine weitere Registergesamtkarte.

## Evidenzindex und Provenanz

| Kürzel / Klasse | Lokaler Nachweis und genaue Grenze |
|---|---|
| **UI / beobachtet, berichtet** | [README, „Direkt beobachtete Windows-Oberfläche“](../README.md), UI-Automation-Sichtung vom 11.10.2026: Config und IO Status geöffnet, **kein Gerät ausgewählt**; Search, Save, Restore, Reboot, Export und Firmware nicht betätigt. Die Anleitung bestätigt diese eingeschränkte Sichtung. Der Bericht ist vorhanden, Roh-UIA-Protokoll, Screenshots und Control-IDs sind hier nicht veröffentlicht. Keine neue eigene Beobachtung. |
| **VID / Video-Beobachtung, berichtet** | [README, „Ergänzende Video-Beobachtungen“](../README.md) und [PLAN, „Ergänzende Videoquelle“](../PLAN.md): lokal gesichtetes Nutzer-Upgradevideo, Dauer laut PLAN 226,815 s; Modulinfo/Aktionen um **0:55**. Weitere Sequenzen ohne publizierte genaue Zeitmarken. Video/Frames bleiben privat; kein Drahtnachweis. |
| **M / Herstellerangabe, dokumentiert** | [Primärinventar](registers/non-u-en-v1.1.json), Quelle `m31_non_u_en_v1_1`, englisches nicht-U V1.1, 29.01.2026. Definition-IDs und deren `evidence` enthalten Seiten, URL und Hash. **p** bezeichnet gedruckte Seite, **PDF** physische 1-basierte Seite; nicht austauschbar. |
| **N / Herstellerangabe, dokumentiert** | [Hypothesen](registers/hypotheses.json), N1: chinesisches nicht-U V1.1. UI-Save/Restart p47–48 / PDF50–51; Modellbaum/Firmware p49 / PDF52. Diese UI-Angaben belegen keine Register. Quellenidentität im [Quellenvergleich](registers/source-comparison.json). |
| **C / Communitybericht** | [Community-Evidenz](registers/community-evidence.json), `sources[id=community-modbus-cn]`: Artikel vom 16.08.2024, Screenshotlog vom 11.08.2024, Tool v1.1, M31-AAAX4440G, angezeigte Firmware 1.1. Artikel-/Bild-URLs im Datensatz. Serieller Aufbau und DI/DO-Verhalten berichtet; AI ausdrücklich nicht getestet. Repost-/Sponsoring-Unabhängigkeit ungeklärt. Keine neuen PDU-Adressen oder Payloads. |
| **S / synthetische Softwareprüfung** | Unten benannte Projektdateien und Testklassen: Simulator, Mocks, Fake-Zeitgeber und echte Tk-Widgets. Nachweis unserer Implementierung, **nicht** des Herstellerprogramms oder elektrischer Wirkung. Testreferenz bedeutet vorhandener Prüfpfad, nicht hier erneut bestandener Test. |
| **H / unbestätigte Hypothese** | `candidates[id=H1..H6]` in [hypotheses.json](registers/hypotheses.json): null unabhängige Gerätebeobachtungen; `hardware_verified`, `runtime_enabled`, `automatic_probe_allowed`, `automatic_write_allowed` jeweils **false**. |
| **STATIC / statischer Hinweis** | [PLAN, „Explizite Paritätslücken / späterer Ausbau“](../PLAN.md): Geräteprofile, Modbus-Assistent, XLSX/QXlsx und Firmwareauswahl aus statischer Untersuchung angedeutet. Keine belegte vollständige Menü-/Dialogstruktur oder Dateischemata. |

Tool-Provenanz: Die Anleitung nennt den EXE-SHA256 und den bytegleichen
Download id3403; der Dateiname bezeichnet keinen anderen Build. Ausführung
in der vorhandenen VM durch Defender blockiert. Diese Blockade bleibt
bestehen, ohne Ausnahme oder Schutzumgehung. Die separat berichtete
laufende UI-Sichtung ist **nicht** als erfolgreicher Start in dieser VM
auszugeben. Signaturstatus, Windows-Build, Locale/Codepage, DPI, Tk- und
Abhängigkeitsversionen der Hersteller-Sichtung sind im verfügbaren
Sichtungsbericht nicht vollständig belegt; nicht nachträglich ergänzen.

### Abnahmestand strikt trennen

- Anleitung / PLAN berichten für den vorherigen Auto-refresh-Quellstand:
  Linux **236 Tests, 235 bestanden, 1 Hardware-Skip, 38,743 s**;
  nativ Windows **236 Tests, 235 bestanden, 1 Hardware-Skip, 120,555 s**.
  Tests, pip check, Kompilierung, Wheel und GUI-Start/-Ende jeweils Exitcode 0.
- Das Register-README berichtet einen **älteren** Stand 0.5.0 mit 229 Tests;
  dieser Wert ersetzt nicht den jüngeren 236er-Bericht.
- **Aktuelle Merge-/Runtime-Integration nativ unter Windows geprüft:**
  240 Tests in 102,461 s, 239 bestanden und ein Hardware-Skip.
  Kompilierung, `pip check`, Wheel-Build und isolierter Tk-Start/-Ende
  jeweils Exitcode 0. Python 3.12.10, Tk 8.6, Windows 11 Build 26100,
  native Codepage cp1252 ohne UTF-8-Moduswechsel. Keine neue Linux-Abnahme.
- Hersteller-EXE-Parität, modellbezogene Registerverfügbarkeit und
  Hardware-/Elektrikabnahme bleiben davon getrennt. Frühere Hardwareberichte
  in PLAN sind keine Prüfung des aktuellen, nur berichteten Erweiterungsaufbaus
  und kein Nachweis der hier offenen Herstellerbefehle.

## Funktionsmatrix

Für **alle Windows-Zeilen**: keine neue Bedienung, keine hier gemessenen
Livewerte. Ohne besonderen Beleg sind Default, Validierung,
deaktivierter Zustand, Bestätigung, Fehlermeldung, Tastaturzugang und genaue
Control-/Menühierarchie **unbekannt**. Ein sichtbarer Wert ist kein Gerätewert.
„Nicht beobachtet“ bedeutet nicht „fehlt“. Pfade mit `→` bezeichnen nur die
berichteten Ansichten/Controls, nicht erfundene UIA-IDs.

Linux-Referenzen verwenden bestehende stabile Symbole; S ist stets
synthetisch. Unbekannte Herstellerfunktion und vorhandener generischer
Rohregisterzugriff sind keine Funktionsgleichheit.

| ID / Funktion und Windows-Pfad | Vorbedingungen, belegtes Verhalten / Bedienfolge | Wirkung / Sicherheit | Provenanz / Klasse | Linux-Vergleich und Prüfpfad | Explizite Restlücke |
|---|---|---|---|---|---|
| **W01 Transportwahl** · Gerätebereich → Serial Port / Ethernet | UI ohne Zielauswahl; Auswahlmöglichkeiten sichtbar. C zeigt SerialPort mit 9600, 8 Datenbits, 1 Stopbit, NONE, Suchadresse 1: **Screenshotzustand**, kein universeller UI-Default. | Auswahl lokal; Verbinden/Suchen kann I/O auslösen. | UI; C `reported_observation`, `identity_and_discovery`; M `unmapped_or_absent` Daten-/Stopbits | **Implementiert als Standard-Modbus**, `m31tool/core.py:ModbusSession.open_tcp/open_rtu`; `tests/test_core.py`, `tests/test_discovery.py:DiscoveryTests.test_rtu_configuration_and_sequential_close` | Gleichheit der Hersteller-Verbindungsabläufe, Validierung/Timeouts unbekannt; lokale Clientparameter ändern keine Geräteserialparameter. |
| **W02 Suche** · Gerätebereich → Search / Ergebnisliste | UI: Modell/IP oder Slave-Adresse/Typ sichtbar; Search nicht betätigt. C: fertige Suche mit einem Gerät, SerialPort gewählt. | Mögliche aktive Discovery; Herstellerverkehr unbekannt, hier verboten. | UI; C `identity_and_discovery`; H6 | **Teilweise**, explizite begrenzte Modbus-Ziele statt Vendor-Discovery: `m31tool/discovery.py:discover_tcp/discover_rtu`; `tests/test_multi_device_gui.py:DeviceListCallbacks.test_search_requires_explicit_hosts_and_never_uses_current_host_implicitly`; `tests/test_discovery.py:DiscoveryTests` | Keine UDP-Payload/Ports/opcodes belegt. Keine Suche starten, um diese zu erraten. |
| **W03 IO Status → DI / DO** | UI: Bereiche vorhanden, keine Zielauswahl. C berichtet DI-Änderung/DO-Bedienung für sein Modell, ohne Registerframes. M Tabellen-Default 0, kein bestätigter Startzustand. | DI/DO-Status lesen; DO-Bedienung kann Lasten schalten. Hersteller-Bestätigungen unbekannt. | UI; C `access`; M `di_status`, `do_status`, p45–46 / PDF49–50 | **Teilweise**, Rohlesen FC02/01, explizites Schreiben FC05/0F: `ModbusSession`, `m31tool/app.py:M31App._read/_write`; `tests/test_gui_safety.py:GUISafetyTests`, `tests/test_parity_gui.py:ParitySafetyTests.test_multiple_coils_and_cancellation` | Keine vollständige modulare I/O-Ansicht oder geprüfte Zuordnung für die berichtete Erweiterung. Rücklesen ist keine elektrische Bestätigung. |
| **W04 IO Status → AI / AO** | UI: Bereiche vorhanden. M: Integer-/Float-/Prozessfamilien, Default 0; Float zwei Worte/Wert. C hat keine eigene AI-Messung. | AI lesen; AO-Schreiben verändert analoge Ausgänge. | UI; M `ai_integer/ai_float/ai_process`, p46–47 / PDF50–51; `ao_integer/ao_float/ao_process`, p49–50 / PDF53–54 | **Teilweise**, Rohwerte und explizite Wortreihenfolge: `m31tool/formats.py:decode_float32/parse_float32_write`, `M31App._update_interpretation/_write`; `tests/test_formats.py:Float32Tests/Float32WriteTests`, `tests/test_parity_gui.py:ParitySafetyTests.test_float_write_uses_explicit_order_and_complete_raw_readback` | Hersteller-Einheiten, reale Wortreihenfolge und elektrische Skalierung nicht durch plausible Werte bewiesen; Prozesswertkonflikte erhalten. |
| **W05 IO Status → automatische Aktualisierung** | UI: optional, Intervall 100 ms bis 5 s. Aktivierungsdefault, Verhalten ohne Gerät und Fehlerreaktion nicht belegt. | Wiederholte I/O; Hersteller-Lese-/Schreibverkehr nicht erfasst. | UI; Anleitung „Projektbaseline“ | **Implementiert, nur lesend**, `M31App._schedule_auto_refresh/_cancel_auto_refresh/_read`; `tests/test_gui_safety.py:GUISafetyTests` (Auto-refresh-Tests), `tests/test_gui_desktop.py` | Linux-Funktion ist kein Beleg für Hersteller-Pollingframes. Aktuelle Timer-/Lifecycle-Abnahme nach Merge offen. |
| **W06 Config → Modbus-Softwareadresse** | UI: Feld sichtbar; M §3.5 p35 / PDF39 nennt Software-Offset, Werkdefault 1; kein Register angegeben. | Geräteadressänderung möglich, Verbindung/Zuordnung gefährdet. | UI; M `unmapped_or_absent[name=Modbus software offset/slave address]` | **Nicht als Geräte-Setter implementiert**. Lokale Unit-ID: `ModbusSession.unit_id`, `tests/test_multi_device_gui.py:DeviceListCallbacks.test_select_distinct_units_same_tcp_endpoint_only_prepares_fields` | Lokale Unit-ID ≠ Geräte-Softwareoffset, Slot oder Kanaloffset. Keine Adresse aus Gap ableiten. |
| **W07 Config → Baudrate / Parität** | UI: Felder sichtbar; M Default Code 3 = 9600, Parität 0 = None, p51–52 / PDF55–56. Das sind Manualdefaults. | Parameteränderung kann seriellen Zugang verlieren; Persistenz unbekannt. | UI; M `serial_baud`, `serial_parity` | **Lesen implementiert**, `m31tool/device.py:DEVICE_REGISTER_CATALOG/read_device_info`; `tests/test_device.py:DeviceTests.test_every_documented_enum_and_unknown_code` | Kein vollständiger sicherer Konfigurationsablauf; Hersteller-Save-/Restart-/Fehlersemantik fehlt. RTU-Clientsetup ist kein Gerätewrite. |
| **W08 Config → DI-/AI-Filter** | UI: Felder sichtbar. M globale nicht-U-Felder, Werte 1–16, Default 6; DI p45 / PDF49, AI p48 / PDF52 und p42 / PDF46. | Filterwrite kann Signalverhalten ändern; nicht Teil dieser Analyse. | UI; M `di_filter`, `ai_filter` | **Teilweise**, Katalog/Rohzugriff: `m31tool/core.py`, `M31App._prepare_catalog_item`; `tests/test_register_inventory.py:RegisterInventoryTests.test_model_counts_and_non_u_filter_scope` | Keine kanalweisen U-Filter übernehmen; keine Hersteller-Save-Parität. |
| **W09 Config → Netzwerk / DHCP / Modbus-on-net / Ports / Remoteziel** | UI: Felder sichtbar. M `network_mode` Default 0 (TCP server), `dhcp` 0; keine ausgewählten Gerätewerte. M §5.2 p55 / PDF59 beschreibt Save/Restart nach Änderung. | Lesen dokumentierter Felder; Änderung kann Verbindung/Erreichbarkeit verlieren, Persistenz unklar. | UI; M `network_mode`, `dhcp`, `local_ip/subnet/gateway/dns/local_port/destination/destination_port/network_protocol`, p52 / PDF56; M `safety_and_limits` | **Parameterlesen implementiert**, `read_device_info`, `DEVICE_READ_SPECS`; `tests/test_device.py:DeviceTests.test_bounded_ranges_only_cover_documented_registers/test_multiregister_fields_never_guess_byte_order` | MAC/IP/Strings bleiben raw, Packing ungeklärt. UDP-Betriebsmodus beweist keine UDP-Discovery. Kein vollständiger Netzwerk-Setter. |
| **W10 Config → AI-/AO-Bereiche** | UI: Controls sichtbar; Geräte-/Modellabhängigkeit und deaktivierte Zustände nicht belegt. M AI-Defaults modellabhängig, AO Tabelle/Prosa widersprechen sich. | Bereichsänderung kann elektrische Wirkung ändern. AO-Konflikt blockiert sicheren Bereichssetter. | UI; M `ai_range`, p48 / PDF52; `ao_range_table`, p51 / PDF55; `ao_range_prose`, p42 / PDF46 | **Lesevorbereitung teilweise**, `M31App._prepare_catalog_item`; `tests/test_parity_gui.py:ParityDesktopTests.test_range_catalog_prepares_reads_only_and_keeps_ao_conflict_visible` | AO `0x1194` vs `0x0DAC` nicht durch U-Übereinstimmung gelöst. Kein spezifischer sicherer Bereichssetter; generischer Raw-Write ist kein Gegenbeleg. |
| **W11 Config → Wireless-Parameter** | UI-Bericht nennt modellabhängige Felder, nicht deren konkrete Modellzuordnung/Werte. | Wirkung und Protokoll unbekannt. | UI; Variantenvergleich `registers/cross-model-comparison.csv` / `source-comparison.json` | **Nicht implementiert für nicht-U**; Abgrenzung in `tests/test_register_inventory.py:RegisterInventoryTests.test_candidates_and_community_remain_separate_and_inert` | Sichtbarkeit macht Wireless nicht zum nicht-U-Feature. LoRa/U ausdrücklich getrennt, keine übertragene Konfiguration. |
| **W12 Config → Save** | UI: sichtbar, nicht betätigt. N beschreibt Save dann Restart; kein Register angegeben. | Mögliche Geräte-Persistenz/Write; genaue Wirkung unbekannt. | UI; N PDF50–51 / p47–48; H5 | **Nicht implementiert**, `m31tool/device.py` führt keine Save-Aktion aus; lokale Profile separat W18 | Save ≠ FC06/10-Erfolg, Rücklesen, Auto-Persistenz oder Expansion-Storageflag. Kein erfundener Commit. |
| **W13 Info → Adresse / Schnittstelle / MAC / Firmware / I/O-Ausstattung** | UI: Felder berichtet; VID um 0:55; C zeigt Firmware 1.1 nur für sein Modell. Ohne Geräteauswahl keine Identität bestätigt. | Informationsanzeige; Lesetransport/Frames unbekannt. | UI; VID; C; N PDF52 / p49; H1 | **Teilweise**, dokumentierte Parameter/Status: `read_device_info`; `tests/test_device.py:DeviceTests.test_snapshot_preserves_exact_raw_words_and_schema` | Nicht vollständige Modell-/Firmwareinfo; U-Identitätslayout kein nicht-U-Beleg. Geräteinformationen nicht aus Modellnamen vortäuschen. |
| **W14 Gerätebaum / Erweiterungen / Kanalzuordnung** | N Screenshot zeigt Baum und Host-/Erweiterungsfirmware. Exakte Slot-/Host-I/O-Reihenfolge nicht belegt. | Anzeige möglicherweise aus Discovery/privater Abfrage; unbekannt. | N PDF52 / p49; H2; M `safety_and_limits` | **Nicht vollständig implementiert**. Lokale Ziel-Liste `m31tool/discovery.py:DeviceTarget` ist kein physischer Modulbaum; `tests/test_multi_device_gui.py:NativeDeviceListTests` | 16 Expansionen, 32 Descriptorslots, Bitmapbits und Unit-IDs sind verschiedene Größen; berichtete Counts nicht automatisch übernehmen. |
| **W15 Geräteaktionen → Negotiation** | UI: sichtbar, nicht betätigt; VID um 0:55. M getrennte Schutz-/Trigger-/Statusfelder, kein automatischer Start. | **Write / Adressneuordnung**, nicht read-only Discovery; Kommunikation kann sich ändern. | UI; VID; M `negotiation_protection/start/status`, p53 / PDF57 | **Explizit implementiert**, `m31tool/device.py:negotiate_addresses`, `M31App._negotiate`; Default-Nein, Deadline, keine Write-Retries/Rollback; `tests/test_device.py:NegotiationTests`, `tests/test_parity_gui.py:ParitySafetyTests.test_negotiation_cancelled_or_blocked_sends_nothing` | Herstellerdialog/Abbruchsemantik und reales Modellverhalten nicht verifiziert. Kein Aufruf in diesem Auftrag. |
| **W16 Fehler-/Online-Status / Bitmap** | M §4.6 p43 / PDF47 und §4.8 p53 / PDF57; UI-Zuordnung der konkreten Statuscontrols nicht belegt. | Dokumentierte Reads; Snapshot über mehrere Requests nicht atomar. | M `device_exception`, `expansion_fault_bitmap`; H2 | **Implementiert als Rohstatus**, `read_device_info`; `tests/test_device.py:DeviceTests.test_failure_after_first_range_does_not_return_partial_success/test_snapshot_preserves_exact_raw_words_and_schema` | Bitmap-Wortfolge und Bit-/Slot-/Kanalzuordnung offen; kein vollständiger Gerätezustandsbaum. |
| **W17 Geräteaktionen → Restore / Reboot** | UI sichtbar, nicht betätigt; VID um 0:55, C Buttons sichtbar; N UI-Bedienung beschrieben. Keine bestätigte Wirkung dieser Controls. | Reset/Neustart möglich, potenziell Konfigurations-/Verbindungsverlust. | UI; VID; C `identity_and_discovery`; N PDF50–51 / p47–48; H3 | **Nicht implementiert**. Hypothesen bleiben offline, `tests/test_register_inventory.py:RegisterInventoryTests.test_candidates_and_community_remain_separate_and_inert` | Restore-Wirkung/Umfang, Rebootkommando und Magicwerte für nicht-U nicht etabliert. Niemals per U-Probe auflösen. |
| **W18 Dateien → Geräteprofil / Import / Export / Adresstabellen-Export** | UI Export nicht betätigt; VID um 0:55 Adresstabellen-Export sichtbar. STATIC deutet Profile/XLSX an, kein Schema. Exakte Import-/Menüpfade unbekannt. | Dateiausgabe vermutlich lokal; Import/Anwenden könnte schreiben, unbekannt. | UI; VID; STATIC; Anleitung „Projektbaseline“ | **Eigene lokale Formate implementiert**, `m31tool/formats.py:load_profile/save_profile/load_xlsx/save_xlsx`, `m31tool/app.py:load_csv/save_csv`; `tests/test_formats.py:ProfileTests/XLSXTests`, `tests/test_parity_gui.py:ParityDesktopTests.test_client_profile_roundtrip_local_disconnected_and_invalid_atomic` | Client-JSON/Messwert-CSV/XLSX ≠ Hersteller-Gerätekonfiguration oder Adresstabellenschema. Kein unbekanntes Format anwenden. |
| **W19 Modbus-Assistent / generisches Lesen-Schreiben** | STATIC deutet Assistent an; tatsächlicher Dialog, Validierung, FC-Auswahl und Bestätigungen unbekannt. | Reads/Writes möglich; vollständige Wirkung unbekannt. | STATIC; M Registerdefinitionen | **Standard-Modbus implementiert**, `ModbusSession` FC01/02/03/04/05/06/0F/10; `_confirm_write`/`M31App._write` bestätigen und lesen vollständig zurück; `tests/test_core.py`, `tests/test_parity_gui.py:ParitySafetyTests` | Keine identische Hersteller-Assistentenfunktion behaupten. Rohregisterzugriff berechtigt nicht zu unbekannten Befehlen. |
| **W20 Logs / Trace** | C Screenshot enthält Suchlog; vollständige Logansicht, Export und Tastaturpfad unbekannt. | Hersteller-Logging unbekannt; unsere Hookanzeige lokal, Kopieren kann sensible Metadaten enthalten. | C `identity_and_discovery`; S | **Lokale Transport-Hooks implementiert**, `m31tool/core.py:TransportTraceRecord/ModbusSession.trace_snapshot`, `M31App._refresh_trace/_copy_trace/_clear_trace`; `tests/test_transport_trace.py:TransportTraceTests/LoopbackTransportTraceTests` | TX-Hook ≠ Zustellnachweis, RX-Puffer ≠ unabhängiger Paketmitschnitt; keine automatisch rekonstruierte Herstellersemantik. |
| **W21 Netzwerk-Upgrade-Assistent → Adapter / Datei / Suche / Upgrade / Fortschritt** | VID: diese Reihenfolge berichtet; `.ebin`-Hostfirmware V1.2 gewählt. Genaue Zeitmarken außer Modulinfo nicht veröffentlicht, keine eigene Bedienung. | Firmware-/Discoveryverkehr, dauerhaftes Änderungs-/Ausfallrisiko. | VID; H6; Quelle F1 in `registers/source-comparison.json` | **Nicht implementiert**, statische Grenzen in Anleitung / PLAN | Kein Dateiformat, Prüfsummenverfahren, Transfer-/Versions-/Abbruchprotokoll belegt. Firmware ausdrücklich außerhalb aktiver Tests. |
| **W22 Recovery → Reload / BOOT** | VID zeigt physischen Reload-/BOOT-Fall; kein allgemeiner sicherer Ablauf abgeleitet. | Bootloader/Recovery, hohes Ausfall-/Konfigurationsrisiko. | VID; H6 | **Nicht implementiert**, Anleitung „Sicherheitsvertrag“ | Geräte-/Firmwareabhängige Bootbedingungen, Protokoll und Wiederherstellbarkeit offen; keine Taste oder Kommandos ausprobieren. |
| **W23 Menüs / Kontextmenüs / Dialoge / Tastatur / DPI** | Vollständige Hersteller-Inventarisierung fehlt; Config/IO Status sind keine vollständige UI-Abdeckung. Keine Tastaturkürzel beobachtet dokumentiert. | Layoutarbeit lokal; unbekannte Controls nicht betätigen. | UI (begrenzter Umfang); Anleitung „Methode“ | **Eigene Zugänglichkeit implementiert**, `M31App._bind_action/_build_viewport`; `tests/test_gui_layout.py:NativeLayoutTests.test_ctrl_tab_and_reverse_traverse_notebook/test_enlarged_native_fonts_keep_all_actions_reachable_and_footer_fixed` | Kein Windows-Controlbaum, vollständiger Disabled-State-/Fehler-/DPI-Vergleich vorhanden. |

## Unresolved-Ledger

Risikoklassen: **L** lokale Darstellung/Artefakt; **R** unbekannter Lesetransport
(keine aktive Probe erlaubt); **W** Zustands-/Ausgangsänderung;
**F** Firmware/Recovery. Alle folgenden Einträge:
**`hardware_verified=false` für die jeweilige offene Aussage**.
Kandidaten bleiben inert; dies ist keine operative Probe-/Write-Liste.
„Falsifikation“ benennt die Evidenz, die eine Annahme widerlegen würde,
**keinen** auszuführenden Test.

| ID / Status / Matrix | Frage / Kandidat und Quelle | Gegenbeleg / Alternative | Fehlender Nachweis / Falsifikationskriterium | Risiko / nächster zulässiger Schritt |
|---|---|---|---|---|
| **E01 · candidate · H1 · W13** | Nicht-U-Identitätsregister? H1 U0/U1; N1 PDF52 zeigt Info. | Ein U-Manualstamm, null bestätigte nicht-U-Adressquellen; Discovery/private Info statt HR möglich. Filtermaps unterscheiden sich. | Modell-/Firmware-spezifische Vendorbestätigung oder bereits vorhandene attribuierte Request/Responsebytes, FC/Table/Count/Packing. Abweichende nicht-U-Quelle widerlegt U-Transfer. | R · vorhandene Quellen/Captures offline auswerten, andernfalls Herstellerklärung; keine Kandidaten lesen. |
| **E02 · candidate · H2 · W14/W16** | Descriptoren, Firmwarearrays, Host-I/O-Slot, Reihenfolge? H2 U0/U1; N1 PDF52. | 32 Descriptorslots vs 16 Storage-/Modulgrenzen; Baum kann Discoverydaten sein. | Definition physischer Reihenfolge/Absentmarker/Packing und bestätigte nicht-U-Frames. Andere Slotordnung/Transport falsifiziert Arrayübernahme. | R · Scope-/Slotvertrag aus belastbarer Quelle erarbeiten; keine Arrays sondieren, kein 256-Wort-FC03. |
| **E03 · candidate · H3 · W17** | Nicht-U Reboot/Restore entspricht U-Befehlen? N1 PDF50–51; H3. | Keine nicht-U-Adresse/Magicwerte; privates Toolkommando möglich. | Exakter Umfang, Semantik und modellbezogener Befehlsnachweis. Abweichender nicht-U-Befehl widerlegt Transfer. | W · nur vorhandene Vendor-/Capturebelege; niemals durch Neustart-/Resetversuch klären. |
| **E04 · unbekannt · H4 · W09** | Bedeutung Gap `0x753F..0x7540`? H4 N1/U1/L1; Community-Go `Free`. | Drei Varianten eines Vendors, null semantische Quellen. Blockread/Padding belegt kein Feld. | Explizite Felddefinition/Framezuordnung; reserviert/ungültig oder andere Semantik widerlegt jede geratene Benennung. | R/W · unbenannt lassen, aus Snapshot ausschließen; kein Sweep. |
| **E05 · unbekannt · H5 · W12/W07–W10** | Save-to-flash, Auto-Persistenz, Commit oder Reload? N1 PDF50–51; U1 PDF71. | Null Save-Registerquellen; Expansion-Storageflag ist kein Host-Save. | Modell-/Setting-spezifischer Ablauf samt Persistenz/Fehler-/Neustartregeln. Auto-Persistenz oder anderer Commit widerlegt geratenes Saveregister. | W · dokumentierten Ablauf erfragen; lokale Profile deutlich getrennt halten. Kein Save-/Reboot-Persistenzexperiment. |
| **E06 · unbekannt · H6 · W02/W21/W22** | Discovery, Firmwaretransport/-format, Recovery? UI/VID/F1. | UDP-Modus kein Discoverybeleg; C verwendet SerialPort; Assistent kein Payloadformat. | Genaue freigegebene Spezifikation oder schon vorhandener vollständiger Austausch samt Scope. Nicht-UDP/private/Bootloaderquelle widerlegt geratene Ports/FCs. | R/F · statische Quellen oder bestehende Captures prüfen; Firmware/Recovery außerhalb aktiver Arbeit. |
| **E07 · conflict · W10** | AO-Bereich `0x1194` Tabelle vs `0x0DAC` Prosa, M p51/PDF55 vs p42/PDF46. | U-Übereinstimmung unterstützt Kopierfehlerhypothese, bestätigt keine nicht-U-Hardware. | Modell-/Firmwarebezogene Herstellerkorrektur oder vorhandener sauber zugeordneter Austausch. Bestätigtes anderes Layout falsifiziert Tabellenübernahme. | W · Konflikt sichtbar, spezifischer Setter gesperrt; kein Schreiben zur Entscheidung. |
| **E08 · conflict · W03/W04** | Prozessreferenz, signed16-Konversionen, Spannungseinheiten, DI-Endadresse, Strides? Primärinventar und `analog-process-values.csv`. | AO gedrucktes `3-0501` vs HR/FC03; zwei Dezimal/Hex-Konflikte; neun gedruckte Adressen für acht DI. | Herstellerkorrektur bzw. vorhandene bekannte Messwert-/Framezuordnung; falsche Counts/Units widerlegen automatische Normalisierung. | L/R/W · Original und berechnete Normalisierung getrennt anzeigen; synthetische Vektoren prüfen, nicht Livewerte passend interpretieren. |
| **E09 · reported / unbekannt · W03/W04/W14–W16** | Tatsächliche Host-/Erweiterungsidentität, Counts, Offset, Fehlerbitmap? Aufbau laut Anleitung nur Nutzerbericht. | Modellname, IO-Typ-Fortsetzung, Unit-ID und Bitmapbit sind kein Modulplan; frühere PLAN-Aufbauten nicht übertragen. | Redigierte bestätigte Modell-/HW-/Firmware-/Reihenfolgendaten plus konkrete Mappingquelle. Abweichendes Typenschild/Counts falsifiziert Aufbauannahme. | R/W · vorhandene redigierte Metadaten/Herstellerklärung; kein neuer Gerätezielzugriff. |
| **E10 · unbekannt · W06/W07/W09/W13** | Softwareoffset, Daten-/Stopbits und Multiword-Byte-/Wortpacking? M `unmapped_or_absent`; `DeviceRegisterSpec.decode_note`. | Defaults 8/1 und Softwareadresse 1 definieren keine Register; plausible IP/Floatinterpretation ist kein Beleg. | Je Feld FC/Adresse/Count/Order und Änderungssemantik. Andere dokumentierte Reihenfolge falsifiziert Dekodierannahme. | R/W · raw erhalten; keine Gapnamen oder Geräte-Setter ergänzen. |
| **E11 · unbekannt · W18/W19** | Hersteller-Konfigurations-/Adresstabellenformat und Assistent? UI/VID/STATIC. | QXlsx-Bibliothek/Exportbutton beweisen kein Schema; eigener Client-JSON ist anderes Format. | Redigiertes autorisiertes Dateibeispiel mit Version/Felddefinition und Apply-Semantik; abweichendes Schema widerlegt Interoperabilität. | L/W · vorhandene Beispiele offline untersuchen, andernfalls klar nicht kompatibel kennzeichnen. Kein unbekanntes Import/Apply. |
| **E12 · beobachtet, berichtet / unbekannt · W01–W23** | Vollständige Hersteller-UI-States, Bestätigungen/Fehler, Shortcuts, Build/Signatur/DPI? UI eingeschränkt; Defenderblock in VM. | Kein Gerät ausgewählt; nicht betätigte Buttons liefern keine Abläufe. Separate UI-Sichtung beseitigt Blockade nicht. | Attribuierter redigierter Controlbaum und sichere Offline-Sequenzen mit Version/Zeitmarken. Abweichende Version/States falsifizieren Layoutverallgemeinerung. | L · vorhandene Berichte verdichten; spätere autorisierte UI-Sichtung nur ohne I/O und ohne Schutzumgehung. |
| **E13 · dokumentiert / teilweise geprüft · alle S-Referenzen** | Aktueller integrierter Code nach GitHub-Merge ebenso bestanden? | Konfliktauflösung ist neuer Runtime-Stand; frühere 229er-/236er-Berichte sind keine aktuelle Wiederholung. | Aktuelle native Windows-Suite: 240 Tests, 239 bestanden, ein Hardware-Skip; Compile, Dependencies, Wheel und isolierter GUI-Start/-Ende bestanden. Erneuter Linux-Lauf fehlt; Source-Hashes und Umgebung siehe PLAN. | L · Windows-Abnahme erfolgt; Linux separat prüfen, keine Hersteller-/Hardwareabnahme aus Softwaretests ableiten. |

## Priorisierte sichere Folgepakete

Diese Kandidaten benötigen **keinen neuen Gerätebefehl** und sind keine
in diesem Dokument behauptete Implementierung:

1. **P1 / L / sofort lokal:** Matrix und Ledger in Navigation/README verlinken;
   UI-, Manual-, Community-, Software- und Hypothesenlabel konsistent zeigen.
   Kontrollieren: Katalogauswahl, Import und Start bleiben ohne I/O;
   vorhandene Inventar-/GUI-Safety-Tests wiederverwenden.
2. **P2 / L / nach Parent-Merge:** Auto-refresh und Layout am Simulator/nativ
   abnehmen, einschließlich Cancel, Timeout, Teilantwort, Disconnect,
   Worker/Tk-Lifecycle, großen Fonts und normalem Windows-Textdefault.
   236er-Baseline nicht als neues Ergebnis ausgeben.
3. **P3 / L / Mappingdaten reichen:** Modell-/Variantenscope, Manualdefaults
   versus gelesene Werte und ungelöste AO-/Einheitenkonflikte in einer lokalen
   Read-Vorschau deutlicher machen. Keine neuen Reads, Dekoderannahmen oder
   versteckten Setter; `test_register_inventory` und Katalogtests als Basis.
4. **P4 / L / nur manuelle Metadaten:** Ein optionaler **lokaler, unbestätigter**
   Aufbauentwurf wäre möglich; getrennt von verifiziertem Gerätebaum halten,
   keine Counts/Offsets automatisch daraus ableiten. Implementierung erst
   nach festgelegtem lokalem Datenvertrag, Import ohne Verbindung testen.
5. **Blockiert / R-W-F:** Nicht-U Info/Descriptoren, Save, Restore/Reboot,
   Softwareoffset-Setter, AO-Bereichssetter, Vendor-Dateischema,
   proprietäre Discovery, Firmware/Recovery. Erst vollständiger
   modellbezogener Nachweis, **danach** eigene Umsetzungsgenehmigung;
   Hypothesen oder sichtbare Buttons reichen nicht.

## Dokumentprüfung und Integrationshandoff

Dieses Artefakt verändert keine bestehenden Quellen, Tests oder Laufzeit.
Offline-Dokumentprüfung bestanden: 10 lokale Links auf vorhandene Dateien,
23 eindeutige Feature- und 13 Ledger-IDs, benannte Runtime-/Testsymbole
vorhanden, UTF-8 lesbar, keine IPv4-Literale. Die Symbolprüfung liest Text
und importiert keine konfliktbehaftete Runtime. Nach Konfliktauflösung
Referenzen erneut prüfen; die benannten Tests bleiben der integrierten
Ausführung durch den Hauptagenten vorbehalten. Ein reproduzierbarer grüner
Softwarelauf ändert den Status H1–H6 und E01–E12 **nicht** automatisch.
