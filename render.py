"""Trial-Reel-Remix v2: rendert pro Reel bis zu 12 Varianten mit ffmpeg.

Aufruf: python render.py job.json out/
job.json:
{"run": "2026-11-13a",
 "saturation": 1.10,
 "reels": [{"id": "<shortcode>", "mp4": "<MP4-URL>",
            "peak1": [s, e],                 Pflicht, stärkster Moment (ca. 3 s)
            "peak2": [s, e] | null,          zweitstärkster Moment
            "end_cut": x | null,             Original nur bis x (unnötiges Ende weg)
            "result": [s, e] | null,         Ergebnis/Nachher-Moment (1,5 bis 2 s)
            "short": [s, e] | null,          Kernaussage für den 15-s-Cut (max. 12 s)
            "loop_end": x | null,            Schnittpunkt, der nahtlos in den Anfang läuft
            "hooks": ["Zahl", "Meinung", "Fehler"],   Text-Hooks für V6 bis V8
            "only": ["V1", ...] | null}]}    optional: nur diese Varianten rendern

Varianten:
  V1  Peak 1 + komplettes Original
  V3  V1 mit Sättigung x saturation
  V4  Peak 1 + Original bis end_cut
  V5  Peak 2 + komplettes Original
  V6  V1 + Text-Hook 1 (Zahl) in den ersten 2,5 s
  V7  V1 + Text-Hook 2 (Meinung)
  V8  V1 + Text-Hook 3 (Fehler)
  V9  Ergebnis zuerst, dann Original mit Einblendung "So sah es vorher aus"
  V10 Peak 1 + Kernaussage, max. 15 s
  V11 Peak 1 + Original bis loop_end (Loop-Ende)
  V12 V1, erste Sekunde auf 110 % gezoomt
  V13 V1 mit eingebrannten Untertiteln (faster-whisper)
Ausgabe: out/<id>_V<n>.mp4 und out/manifest.json
"""
import json, os, subprocess, sys, textwrap, urllib.request

W, H, FPS = 1080, 1920, 30
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "Montserrat-ExtraBold.ttf")
FONTDIR = os.path.join(HERE, "fonts")
NORM = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p"
ZOOM = f"scale={int(W*1.1)}:{int(H*1.1)},crop={W}:{H}"
AUD = "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo"
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
       "-movflags", "+faststart"]
BOX = "0x3e7b80@0.92"  # Flippɘr dunkles Türkis


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(" ".join(cmd[:6]) + " ...\n" + r.stderr[-1500:])
    return r.stdout


def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
               "-of", "json", path])
    d = json.loads(out)
    streams = d.get("streams", [])
    v = next((s for s in streams if s["codec_type"] == "video"), None)
    a = next((s for s in streams if s["codec_type"] == "audio"), None)
    return {"duration": round(float(d["format"]["duration"]), 2), "width": v and v.get("width"),
            "height": v and v.get("height"), "audio": a is not None}


def text_file(out_dir, name, text, width=18):
    lines = []
    for para in text.split("\n"):
        lines += textwrap.wrap(para, width=width) or [""]
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def drawtext(path, start, end, size=74, y="h*0.20"):
    p = path.replace("\\", "/").replace(":", "\\:")
    f = FONT.replace("\\", "/").replace(":", "\\:")
    return (f"drawtext=fontfile='{f}':textfile='{p}':expansion=none:fontsize={size}:fontcolor=white:"
            f"line_spacing=14:box=1:boxcolor={BOX}:boxborderw=28:x=(w-text_w)/2:y={y}:"
            f"enable='between(t,{start},{end})'")


def build(src, segments, dst, post_v="", post_a=""):
    """segments: Liste von (start, ende, zusatzfilter_video). Werden normalisiert und aneinandergehängt."""
    parts, labels = [], ""
    for i, (s, e, extra) in enumerate(segments):
        vf = NORM + ("," + extra if extra else "")
        parts.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS,{vf}[v{i}]")
        parts.append(f"[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS,{AUD}[a{i}]")
        labels += f"[v{i}][a{i}]"
    n = len(segments)
    parts.append(f"{labels}concat=n={n}:v=1:a=1[vc][ac]")
    parts.append(f"[vc]{post_v or 'null'}[vo]")
    parts.append(f"[ac]{post_a or 'anull'}[ao]")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-filter_complex", ";".join(parts),
         "-map", "[vo]", "-map", "[ao]", *ENC, dst])
    return sum(e - s for s, e, _ in segments)


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def make_srt(media, srt_path):
    from faster_whisper import WhisperModel  # nur im Runner installiert
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(media, language="de", word_timestamps=True, vad_filter=True)
    cues, buf = [], []
    for seg in segs:
        for w in seg.words or []:
            buf.append(w)
            if len(buf) >= 4 or w.word.strip().endswith((".", "?", "!", ",")):
                cues.append(buf)
                buf = []
    if buf:
        cues.append(buf)
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, c in enumerate(cues, 1):
            txt = "".join(w.word for w in c).strip()
            f.write(f"{i}\n{srt_time(c[0].start)} --> {srt_time(c[-1].end)}\n{txt}\n\n")
    return len(cues)


def valid(seg, dur, min_len=0.8):
    return bool(seg) and 0 <= float(seg[0]) < float(seg[1]) <= dur + 0.05 and float(seg[1]) - float(seg[0]) >= min_len


def main(job_path, out_dir):
    job = json.load(open(job_path))
    sat = float(job.get("saturation", 1.10))
    os.makedirs(out_dir, exist_ok=True)
    manifest = {"run": job.get("run"), "saturation": sat, "reels": []}
    for r in job["reels"]:
        rid = r["id"]
        entry = {"id": rid, "versions": {}, "errors": []}
        try:
            src = os.path.join(out_dir, f"{rid}_src.mp4")
            if r["mp4"].startswith("http"):
                urllib.request.urlretrieve(r["mp4"], src)
            else:
                src = r["mp4"]
            info = probe(src)
            if not info["audio"]:
                raise RuntimeError("Original hat keine Tonspur")
            dur = info["duration"]
            entry["original_duration"] = dur
            p1 = [float(x) for x in r["peak1"]]
            if not valid(p1, dur):
                raise RuntimeError(f"peak1 ungültig: {p1} bei {dur}s")
            P1 = (p1[0], p1[1], "")
            full = (0, dur, "")
            hooks = [h for h in (r.get("hooks") or []) if h and h.strip()]
            plans = {
                "V1": dict(segs=[P1, full]),
                "V3": dict(segs=[P1, full], v=f"eq=saturation={sat}"),
            }
            if r.get("end_cut") and 5 < float(r["end_cut"]) < dur - 0.3:
                plans["V4"] = dict(segs=[P1, (0, float(r["end_cut"]), "")])
            if valid(r.get("peak2"), dur):
                p2 = [float(x) for x in r["peak2"]]
                plans["V5"] = dict(segs=[(p2[0], p2[1], ""), full])
            for i, name in enumerate(["V6", "V7", "V8"]):
                if i < len(hooks):
                    tf = text_file(out_dir, f"{rid}_{name}.txt", hooks[i])
                    plans[name] = dict(segs=[P1, full], v=drawtext(tf, 0, 2.5))
            if valid(r.get("result"), dur):
                rs = [float(x) for x in r["result"]]
                rlen = rs[1] - rs[0]
                tf = text_file(out_dir, f"{rid}_V9.txt", "So sah es vorher aus", width=22)
                plans["V9"] = dict(segs=[(rs[0], rs[1], ""), full], v=drawtext(tf, rlen, rlen + 2.2, size=66))
            if valid(r.get("short"), dur, 3):
                sh = [float(x) for x in r["short"]]
                sh[1] = min(sh[1], sh[0] + 15 - (p1[1] - p1[0]))
                plans["V10"] = dict(segs=[P1, (sh[0], sh[1], "")])
            if r.get("loop_end") and 5 < float(r["loop_end"]) < dur - 0.3:
                plans["V11"] = dict(segs=[P1, (0, float(r["loop_end"]), "")])
            z_end = min(p1[0] + 1.0, p1[1])
            plans["V12"] = dict(segs=[(p1[0], z_end, ZOOM)] + ([(z_end, p1[1], "")] if p1[1] - z_end > 0.1 else []) + [full])
            plans["V13"] = dict(segs=[P1, full], subs=True)
            only = r.get("only")
            if only:
                plans = {k: v for k, v in plans.items() if k in only}
            for v, pl in plans.items():
                dst = os.path.join(out_dir, f"{rid}_{v}.mp4")
                try:
                    post_v = pl.get("v", "")
                    if pl.get("subs"):
                        base = os.path.join(out_dir, f"{rid}_V13_base.mp4")
                        expect = build(src, pl["segs"], base)
                        srt = os.path.join(out_dir, f"{rid}_V13.srt")
                        if make_srt(base, srt) == 0:
                            raise RuntimeError("Keine Sprache erkannt, V13 entfällt")
                        style = ("FontName=Montserrat ExtraBold,FontSize=16,PrimaryColour=&H00FFFFFF,"
                                 "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=110")
                        s_esc = srt.replace(":", "\\:")
                        run(["ffmpeg", "-y", "-v", "error", "-i", base, "-vf",
                             f"subtitles='{s_esc}':fontsdir='{FONTDIR}':force_style='{style}'",
                             "-c:a", "copy", *ENC[:6], "-movflags", "+faststart", dst])
                        os.remove(base)
                    else:
                        expect = build(src, pl["segs"], dst, post_v)
                    got = probe(dst)
                    ok = abs(got["duration"] - expect) <= 0.6 and got["width"] == W and got["height"] == H and got["audio"]
                    if not ok:
                        raise RuntimeError(f"Prüfung fehlgeschlagen: {got}, erwartet {expect:.2f}s")
                    entry["versions"][v] = {"file": os.path.basename(dst), "duration": got["duration"],
                                            "size": os.path.getsize(dst)}
                except Exception as ex:  # eine kaputte Variante stoppt die anderen nicht
                    entry["errors"].append(f"{v}: {str(ex)[:600]}")
            if src.endswith("_src.mp4"):
                os.remove(src)
        except Exception as ex:  # ein kaputtes Reel stoppt die anderen nicht
            entry["errors"].append(str(ex)[:800])
        manifest["reels"].append(entry)
    json.dump(manifest, open(os.path.join(out_dir, "manifest.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    if not any(e["versions"] for e in manifest["reels"]):
        sys.exit("Keine einzige Variante gerendert")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
