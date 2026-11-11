# flipper-reel-remix

Rendert für die monatliche geplante Aufgabe "Trial-Reel-Remix" pro Reel bis zu 5 Versionen und legt sie als Release-Assets ab. Metricool holt die MP4 über die öffentliche Release-URL.

- V1: Peak 1 (3 s) vorne, dann das komplette Original
- V2: V1 um 1 % schneller
- V3: V1 mit 10 % mehr Sättigung
- V4: Peak 1 vorne, Original mit gekürztem Ende
- V5: Peak 2 vorne, dann das komplette Original

Start: Actions > "Remix rendern" > Run workflow mit dem Job-JSON (Format in `render.py`). Die geplante Aufgabe startet den Workflow per `gh workflow run` und liest danach `manifest.json` aus dem Release.

Releases älter als 75 Tage werden automatisch gelöscht. Das Repo muss öffentlich sein, sonst kann Metricool die Videos nicht abholen.
