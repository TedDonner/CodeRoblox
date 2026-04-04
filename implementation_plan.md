# Anforderungsdokument: Codex-gestuetzte Roblox-Entwicklung mit Roblox-Studio-Plugin

## Kurzfassung
Wir planen kein Bildschirm-Autopilot-System, sondern eine belastbare Studio-Integration ueber offizielle Roblox-Plugin-APIs plus einen lokalen Codex-Agent. Das ist der sauberste Weg, um Roblox-Spiele mit KI zu entwickeln, Aenderungen nachvollziehbar zu machen und das Fehlerrisiko niedrig zu halten.

Oeffentlich sichtbares Muster bei aehnlichen Tools:
- Tools wie Catalyst beschreiben eine direkte Verbindung zwischen Web/App und Roblox Studio ueber ein Studio-Plugin mit automatischem Sync.
- Roblox erlaubt Plugins offiziell, Dock-Widgets bereitzustellen, HTTP zu sprechen, Script-Quelltext zu lesen und zu schreiben, Undo/Redo sauber zu integrieren und Places extern zu publishen.
- Fuer echte Zuverlaessigkeit sollte unsere v1 nicht Studio per UI-Hacks "fernsteuern", sondern deklarative Kommandos an ein Plugin senden, das Instanzen, Properties, Scripts und Logs kontrolliert bearbeitet.

## Zielbild
Ziel ist eine Entwicklungsplattform, mit der Codex Roblox-Spiele end-to-end unterstuetzen kann:
- Projektkontext aus Roblox Studio und lokalem Workspace erfassen.
- Luau-Code erzeugen, aendern und sicher zurueck in Studio schreiben.
- Studio-Struktur gezielt manipulieren: Instanzen anlegen, verschieben, loeschen, Properties setzen, Services konfigurieren.
- Logs, Analysefehler und Playtest-Ergebnisse zurueck an Codex geben.
- Aenderungen als Diff, Plan und Operationen ausfuehren, nicht als blindes Autocomplete.
- Spaeter optional Publish- und CI-Workflows anbinden.

### Erfolgskriterien fuer v1
- Ein Nutzer kann per Codex ein kleines Roblox-Spiel mit Scripts, Explorer-Struktur und einfachen 3D-Objekten erstellen oder aendern.
- Jede Aenderung ist nachvollziehbar, rueckgaengig machbar und vor Ausfuehrung pruefbar.
- Kein direkter Bedarf an inoffiziellen Roblox-Internals oder UI-Automation.
- Lokale Entwicklung funktioniert auch ohne permanenten Cloud-Roundtrip.

## Architektur und Hauptkomponenten

### 1. Roblox-Studio-Plugin
Verantwortung:
- DockWidget-UI fuer Verbindung, Status, Diff-Vorschau, Freigaben und Logs.
- Lesen des Studio-Kontexts:
  - Explorer-Hierarchie
  - ausgewaehlte Instanzen
  - relevante Script-Quelltexte
  - offene oder aktive Scripts
  - Diagnostik und Laufzeitlogs
- Schreiben von Aenderungen:
  - `ScriptEditorService:UpdateSourceAsync` fuer Script-Edits
  - Instanz- und Property-Operationen im DataModel
  - Undo/Redo ueber `ChangeHistoryService`
- Verbindung zu lokalem Agent ueber HTTP, WebSocket oder SSE.
- Sichere lokale Plugin-Settings fuer Projektbindung und Session-IDs.

#### Nicht-Ziele fuer v1
- Generische Maus- oder Keyboard-Steuerung von Studio
- Reverse Engineering interner Studio-Protokolle
- Headless-Compile als Primaermechanismus

### 2. Lokaler Codex-Agent
Verantwortung:
- Bruecke zwischen Codex CLI/Desktop und Roblox Studio
- Lokaler Workspace als Source of Truth fuer Spezifikation, Prompts, Snapshots und optional dateibasierte Roblox-Projekte
- Uebersetzung zwischen natuerlicher Sprache und strukturierten Studio-Operationen
- Validierung vor Ausfuehrung:
  - Luau-Lint oder Typecheck soweit lokal verfuegbar
  - Regelpruefungen fuer gefaehrliche Aenderungen
  - Konflikterkennung bei parallel geaenderten Scripts
- Sitzungsverwaltung, Projektkontext, Verlauf und Rollback-Metadaten

#### Empfohlene v1-Topologie
`Codex <-> lokaler Agent <-> Roblox-Studio-Plugin`

Cloud optional nur fuer Modellaufrufe, nicht fuer Studio-Dateizugriff oder Primaersteuerung.

### 3. Strukturierte Operations-API
Zwischen Agent und Plugin brauchen wir kein Freitext-Protokoll, sondern eine feste Befehlssprache:
- `get_project_snapshot`
- `get_selection`
- `read_scripts`
- `apply_script_patch`
- `create_instance`
- `update_properties`
- `reparent_instance`
- `delete_instance`
- `run_playtest`
- `collect_output`
- `create_checkpoint`
- `rollback_checkpoint`

#### Interface-Regeln
- Alle Schreiboperationen sind idempotent oder tragen eine eindeutige Operation-ID.
- Jede Schreiboperation enthaelt Zielpfad, Preconditions und erwartetes Ergebnis.
- Das Plugin liefert strukturierte Resultate zurueck: `success`, `changed_entities`, `diagnostics`, `undo_token`, `conflicts`.

## Fachliche Anforderungen

### A. Kontextgewinnung
- Vollstaendigen Projekt-Snapshot auf Anfrage erzeugen.
- Relevanten Kontext klein halten:
  - nur betroffene Scripts
  - Nachbarschaft im Explorer
  - referenzierte Remotes, Module und Services
- Asset- und Szenenkontext als strukturierte Metadaten statt kompletter Binaerdaten uebertragen.

### B. Code-Entwicklung
- Script neu anlegen, umbenennen, verschieben und patchen.
- Multi-file-Aenderungen in einer Transaktion gruppieren.
- Vor Ausfuehrung Diff anzeigen.
- Bei Konflikten Rebase oder erneutes Patchen statt stumpfem Ueberschreiben.

### C. Studio-Steuerung
- Primitive Objekte und Standard-Instanzen deklarativ erzeugen.
- Properties typisiert setzen.
- Referenzen ueber stabile Pfade oder IDs verwalten.
- Auswahl- und Fokuswechsel als Hilfsfunktion, nicht als Kernmechanik.

### D. Sicherheits- und Qualitaetsbarrieren
- Plan-then-apply: Codex erzeugt erst einen Aenderungsplan, Plugin fuehrt erst nach Freigabe aus.
- Schutzregeln fuer destruktive Aktionen.
- Checkpoints vor groesseren Aenderungen.
- Vollstaendiges Audit-Log pro Session.

### E. Validierung statt Compile
Da Roblox keine klassische vollautomatische lokale Compiler-Pipeline wie bei nativen Apps bietet, definieren wir einen Quality-Gate-Stack:
- Luau-Syntax- und Typpruefungen, soweit lokal oder integriert verfuegbar
- Roblox-Analyzer- oder Editor-Diagnostik einsammeln
- Play Solo oder Test-Session ausloesen
- Output, Errors und Warnings zurueck an Codex
- Optionaler Publish erst nach bestandenem Gate

### F. Projektmodell
Fuer v1 sollte das System sowohl Studio-first als auch dateibasiert funktionieren, aber intern ein kanonisches Modell haben:
- Studio-Snapshot als operative Wahrheit fuer Live-Manipulation
- optional lokales Spiegelmodell fuer Git, Review und Wiederholbarkeit
- perspektivisch Kompatibilitaet zu Rojo-aehnlichen Flows statt Eigenformat-Zwang

## Oeffentliche Schnittstellen und Artefakte
Zu spezifizieren sind:
- Plugin-zu-Agent-Protokoll
  - Auth oder Session-Handshake
  - Snapshot-Schema
  - Operations-Schema
  - Error- und Conflict-Schema
- Lokales Projektmanifest
  - Roblox-Projektbindung
  - Universe- und Place-Metadaten
  - Plugin-Agent-Endpunkt
  - Feature-Flags
- Checkpoint- und Rollback-Modell
- Prompt-Kontextvertrag
  - welche Studio-Daten an Codex gehen duerfen
  - welche Daten nie automatisch gesendet werden

## Implementierungsreihenfolge
1. RFC und Domaenenmodell festziehen.
2. Minimalen lokalen Agenten spezifizieren.
3. Roblox-Plugin mit Connect, Snapshot und Script-Patch bauen.
4. Danach Instanz- und Property-Operationen ergaenzen.
5. Danach Diagnostics, Playtest und Checkpoints.
6. Danach optional Dateisync, Publish und CI anbinden.

## Testplan

### Pflichtszenarien
- Verbindung Plugin und lokaler Agent auf Windows stabil aufbauen.
- Snapshot eines kleinen und mittleren Roblox-Projekts korrekt erzeugen.
- Einzelnes Script patchen, waehrend es in Studio geoeffnet ist.
- Mehrere Scripts atomar aendern.
- Instanzen erzeugen, verschieben und loeschen, mit Undo und Redo.
- Konfliktfall: Nutzer aendert Script manuell, waehrend Codex Patch vorbereitet.
- Playtest starten und Logs oder Fehler zurueckholen.
- Rollback nach fehlgeschlagenem Aenderungsset.
- Netzwerkunterbrechung waehrend einer Operation.
- Session-Neustart mit Wiederaufnahme offener Checkpoints.

### Akzeptanzkriterien
- Kein stilles Ueberschreiben von Nutzerarbeit.
- Jede Schreiboperation ist im Audit-Log sichtbar.
- Fehler sind fuer Nutzer verstaendlich und reproduzierbar.
- Plugin bleibt benutzbar, auch wenn Agent oder Modellaufruf ausfaellt.

## Annahmen und getroffene Entscheidungen
- v1 umfasst volle Studio-Steuerung im Sinn deklarativer DataModel-Operationen, nicht GUI-Autopilot.
- Verbindung erfolgt lokal ueber einen Desktop- oder CLI-Agent.
- Wir stuetzen uns ausschliesslich auf offizielle Roblox-Mechanismen.
- Automatisch kompilieren wird in v1 durch Validierung, Diagnostics und Playtest ersetzt.
- Publish oder Deployment ist nachrangig und darf erst nach stabiler Authoring-Schicht kommen.

## Quellenbasis
- Catalyst-Landingpage/FAQ zur Plugin-basierten Studio-Kopplung: <https://bpcatalyst.net/>
- Roblox `HttpService`: <https://robloxapi.github.io/ref/class/HttpService.html>
- Roblox `Plugin`: <https://robloxapi.github.io/ref/class/Plugin.html>
- Roblox Open Cloud Place Publishing: <https://create.roblox.com/docs/cloud/open-cloud/usage-place-publishing>
- Rojo als Referenz fuer dateibasierten Roblox-Workflow: <https://rojo.space/docs/v7/sync-details/>
