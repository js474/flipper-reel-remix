# Trial-Reels Tagesplanung (Betriebsanleitung)

Wird von der geplanten Aufgabe "Trial-Reels Planung" gelesen (alle 3 Tage, am 1., 4., 7. ... des Monats um 20:41, plant MORGEN bis MORGEN+2). Dort steht der Ablauf, hier die festen Regeln.

## Raster (Metricool Best Time Instagram, Stand 13.11.2026)
- 12:00 Feed-Trial (Aufgabe "Feed-Reel als Trial Reel", weitere Quellen 14:00 und 16:00)
- Remix: 11, 15, 17, 18, 19, 20, 21 Uhr (7 Slots), steht in state.json unter slots.remix
- Zusammen höchstens 8 Trial Reels pro Tag (slots.max_trials) inklusive Feed-Trial, 7 Tage die Woche. Ist der Feed-Trial noch nicht eingeplant, hält plan.py einen Platz frei. Alte Posts in posted zählen mit.
- Ab 14.11.2026 (Entscheidung Johannes 13.11.): 8 statt 10 Trials, damit der Stoff länger reicht. 13 und 22 Uhr entfallen (außerhalb der Best Times).

## Lanes
- Höchstens 7 Lanes (slots.max_lanes) = 7 verschiedene Inhalte gleichzeitig. Jede Lane bekommt pro Tag höchstens einen Slot. Reichen die Slots nicht, kommt zuerst die Lane dran, die am längsten nicht lief.
- Am 13.11. liefen noch 9 Lanes. Neue Lanes kommen erst dazu, wenn weniger als 7 aktiv sind.
- Ein Inhalt läuft nie zweimal am selben Tag. Gesperrt (block) sind Tage, an denen derselbe Inhalt als Feed-Reel, Feed-Trial oder Repost läuft, plus der Tag davor und danach.
- Die Uhrzeit rotiert täglich (plan.py), damit jede Variante in verschiedenen Slots läuft.

## Varianten (render.py)
V1 Peak vorne + Original | V3 +10 % Sättigung | V4 unnötiges Ende weg | V5 zweiter Peak als Hook
V6 Text-Hook Zahl | V7 Text-Hook Meinung | V8 Text-Hook Fehler | V9 Ergebnis zuerst + "So sah es vorher aus"
V10 15-s-Cut | V11 Loop-Ende | V12 Zoom erste Sekunde | V13 eingebrannte Untertitel (nur wenn das Original noch keine hat, Job-Feld "subs": true)
V2 (1 % schneller) entfällt ab 13.11.2026.
Reihenfolge in der Warteschlange: V1, V6, V3, V9, V7, V10, V4, V8, V12, V5, V13, V11 (fehlende überspringen).

## Captions
- Erste Zeile: Hook-Frage (hook_line). Bei V6 bis V8 ersetzt der eingeblendete Text-Hook die erste Zeile.
- Darunter die Original-Caption. Keine Links und Domains (plan.py entfernt sie).
- Hooks: Deutsch, Du-Form, max. 10 Wörter, keine Gedankenstriche, keine Floskeln, nie "Coaching", nach Doppelpunkt groß.
  Hook 1 Zahl/Preis, Hook 2 Meinung/Frage, Hook 3 Fehler/Warnung. Nur Aussagen, die im Reel vorkommen.

## Auswertung und Repost
- 3 Tage nach dem letzten Trial einer Lane: Metricool-Analytics (IGRE) je Trial, Sieger = meiste Shares + Saves, dann niedrigere Skip-Rate, dann Views.
- Sieger-Variante läuft als normales Reel um 15:00 auf Instagram, Facebook, YouTube, TikTok, Threads und X (kein Pinterest).
- variant_wins in state.json zählt, welcher Variantentyp wie oft gewinnt.

## Neue Reels
- Kandidaten: Instagram-Reels der letzten 12 Monate, Score Shares + Saves (IGRE21 + IGRE12), mindestens 1000 Views (IGRE23).
- Nicht: Inhalte, die gerade in einer Lane laufen oder in den letzten 60 Tagen liefen; reine Musik-Reels; Reels ohne MP4 in Metricool (direkt in Instagram gepostet).
- Gleiches Video mit umformulierter Caption gibt es oft mehrfach: Gleiches Thema in der ersten Captionzeile = gleicher Inhalt, nur einmal nehmen.
- vidIQ-Prompt: siehe Aufgabe. Peaks bei 0,0 s sind wertlos (dann den zweiten Peak als Peak 1 nehmen).
