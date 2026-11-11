"""Trial-Reel-Remix: rendert pro Reel bis zu 5 Versionen mit ffmpeg.

Aufruf: python render.py job.json out/
job.json:
{"run": "2026-12",
 "speed": 1.01,
 "saturation": 1.10,
 "reels": [{"id": "<shortcode>", "mp4": "<Metricool-MP4-URL>",
            "peak1": [start, ende], "peak2": [start, ende] oder null,
            "end_cut": <Sekunde, bis zu der V4 das Original zeigt> oder null}]}

Versionen:
  V1  Peak 1 (3 s) + komplettes Original
  V2  V1, um "speed" schneller (Bild und Ton)
  V3  V1 mit Sättigung x "saturation"
  V4  Peak 1 + Original bis end_cut (nur wenn end_cut gesetzt)
  V5  Peak 2 + komplettes Original (nur wenn peak2 gesetzt)
Ausgabe: out/<id>_V<n>.mp4 und out/manifest.json
"""
import json, os, subprocess, sys, urllib.request

W, H, FPS = 1080, 1920, 30
NORM = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p"
AUD = "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo"
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
       "-movflags", "+faststart"]


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


def hook_plus(src, hook, tail_end, dst, extra_v="", extra_a=""):
    """Segment hook=[s,e] vor das Original (0 bis tail_end) setzen."""
    s, e = hook
    fc = (f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS,{NORM}[v0];"
          f"[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS,{AUD}[a0];"
          f"[0:v]trim=0:{tail_end},setpts=PTS-STARTPTS,{NORM}[v1];"
          f"[0:a]atrim=0:{tail_end},asetpts=PTS-STARTPTS,{AUD}[a1];"
          f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[vc][ac];"
          f"[vc]{extra_v or 'null'}[vo];[ac]{extra_a or 'anull'}[ao]")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-filter_complex", fc, "-map", "[vo]", "-map", "[ao]",
         *ENC, dst])


def main(job_path, out_dir):
    job = json.load(open(job_path))
    speed = float(job.get("speed", 1.01))
    sat = float(job.get("saturation", 1.10))
    os.makedirs(out_dir, exist_ok=True)
    manifest = {"run": job.get("run"), "speed": speed, "saturation": sat, "reels": []}
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
            p1 = r["peak1"]
            plans = {
                "V1": (p1, dur, "", ""),
                "V2": (p1, dur, f"setpts=PTS/{speed}", f"atempo={speed}"),
                "V3": (p1, dur, f"eq=saturation={sat}", ""),
            }
            if r.get("end_cut") and 5 < float(r["end_cut"]) < dur - 0.3:
                plans["V4"] = (p1, float(r["end_cut"]), "", "")
            if r.get("peak2"):
                plans["V5"] = (r["peak2"], dur, "", "")
            for v, (hook, tail, ev, ea) in plans.items():
                dst = os.path.join(out_dir, f"{rid}_{v}.mp4")
                hook_plus(src, hook, tail, dst, ev, ea)
                got = probe(dst)
                expect = (hook[1] - hook[0]) + tail
                if v == "V2":
                    expect = expect / speed
                ok = abs(got["duration"] - expect) <= 0.6 and got["width"] == W and got["height"] == H and got["audio"]
                if not ok:
                    raise RuntimeError(f"{v} Prüfung fehlgeschlagen: {got}, erwartet {expect:.2f}s")
                entry["versions"][v] = {"file": os.path.basename(dst), "duration": got["duration"],
                                        "size": os.path.getsize(dst)}
            if src.endswith("_src.mp4"):
                os.remove(src)
        except Exception as ex:  # ein kaputtes Reel stoppt die anderen nicht
            entry["errors"].append(str(ex)[:800])
        manifest["reels"].append(entry)
    json.dump(manifest, open(os.path.join(out_dir, "manifest.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    if all(e["errors"] for e in manifest["reels"]):
        sys.exit("Alle Reels fehlgeschlagen")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
