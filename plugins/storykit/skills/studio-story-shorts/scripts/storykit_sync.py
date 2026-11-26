"""Blocky StoryKit sync: download the method bundle the Pass server hands out, check it, unpack it into the project.

Holds no method content: it only downloads, verifies and unzips. Standard library only.

    python storykit_sync.py status --project <dir>
        prints the cached state as JSON: content_version, valid_until, synced_at, intact (files unchanged), method path
    python storykit_sync.py fetch --project <dir> --url <url> --sha256 <hex> --bytes <n> --version <content_version> --valid-until <YYYY-MM-DD|"">
        downloads the bundle from get_bundle's url, checks size + sha256, unpacks it to <dir>/.storykit/method/ (the old copy is
        replaced only after the new one unpacked cleanly) and writes <dir>/.storykit/state.json
    python storykit_sync.py touch --project <dir> --valid-until <YYYY-MM-DD|"">
        records the newest valid_until from pass_status (so the cache knows when the Pass ends)
    python storykit_sync.py install-id
        prints this computer's install id (64 hex chars) for the per-computer Pass limit
    python storykit_sync.py install-header
        prints {"X-StoryKit-Install": "<id>"} for .mcp.json's headersHelper; never fails (prints {} if it can't)

The install id is sha256("blocky-storykit|" + the OS machine id): Windows MachineGuid, macOS IOPlatformUUID,
Linux /etc/machine-id, else a random id saved once in ~/.storykit/install-id. Only the hash leaves the computer.

Only https://thegentleminh.com and https://*.supabase.co URLs are accepted (add --dev for http://localhost test servers).
"""
import argparse, datetime, hashlib, io, json, re, shutil, subprocess, sys, urllib.parse, urllib.request, uuid, zipfile
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024
INSTALL_SALT = "blocky-storykit|"


def machine_uuid():
    """The OS's own stable machine id (read only), or None."""
    try:
        if sys.platform == "win32":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                                winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                return str(winreg.QueryValueEx(k, "MachineGuid")[0]).strip() or None
        if sys.platform == "darwin":
            out = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], capture_output=True, text=True, timeout=5).stdout
            m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
            return m.group(1) if m else None
        p = Path("/etc/machine-id")
        return p.read_text().strip() or None if p.exists() else None
    except Exception:
        return None


def saved_random_id():
    p = Path.home() / ".storykit" / "install-id"
    if p.exists():
        v = p.read_text(encoding="utf-8").strip()
        if v:
            return v
    v = str(uuid.uuid4())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(v, encoding="utf-8")
    return v


def install_id():
    return hashlib.sha256((INSTALL_SALT + (machine_uuid() or saved_random_id())).encode("utf-8")).hexdigest()


def cmd_install_id(a):
    print(install_id())


def cmd_install_header(a):
    try:
        print(json.dumps({"X-StoryKit-Install": install_id()}))
    except Exception:
        print("{}")


def state_path(project):
    return Path(project) / ".storykit" / "state.json"


def load_state(project):
    p = state_path(project)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_state(project, st):
    p = state_path(project); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def host_ok(url, dev):
    u = urllib.parse.urlparse(url)
    h = (u.hostname or "").lower()
    if u.scheme == "https" and (h == "thegentleminh.com" or h.endswith(".thegentleminh.com") or h.endswith(".supabase.co")):
        return True
    return dev and u.scheme in ("http", "https") and h in ("localhost", "127.0.0.1")


def cmd_status(a):
    st = load_state(a.project)
    m = Path(a.project) / ".storykit" / "method"
    intact = None
    if st.get("files") and m.exists():
        intact = all((m / f["path"]).exists() and hashlib.sha256((m / f["path"]).read_bytes()).hexdigest() == f["sha256"] for f in st["files"])
    out = {k: st.get(k) for k in ("content_version", "valid_until", "synced_at")}
    out.update({"method": str(m / "METHOD.md") if (m / "METHOD.md").exists() else None, "intact": intact,
                "pass_still_valid_by_date": (st.get("valid_until") or "") >= datetime.date.today().isoformat() if st.get("valid_until") else None})
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_touch(a):
    st = load_state(a.project)
    st["valid_until"] = a.valid_until or None
    st["checked_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    save_state(a.project, st)
    print("ok")


def cmd_fetch(a):
    if not host_ok(a.url, a.dev):
        sys.exit("refused: the bundle URL must be https on thegentleminh.com (or its storage); got " + urllib.parse.urlparse(a.url).netloc)
    req = urllib.request.Request(a.url, headers={"User-Agent": "storykit-sync/1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        blob = r.read(MAX_BYTES + 1)
    if len(blob) > MAX_BYTES:
        sys.exit("refused: bundle larger than 20 MB")
    if a.bytes and len(blob) != a.bytes:
        sys.exit(f"download incomplete: {len(blob)} bytes, expected {a.bytes}. Run the sync again.")
    digest = hashlib.sha256(blob).hexdigest()
    if digest != a.sha256.lower():
        sys.exit("checksum mismatch: the download is not the bundle the server announced. Nothing was changed. Run the sync again.")
    base = Path(a.project) / ".storykit"; base.mkdir(parents=True, exist_ok=True)
    new, cur, old = base / "method.new", base / "method", base / "method.old"
    shutil.rmtree(new, ignore_errors=True)
    files = []
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for info in z.infolist():
            name = info.filename
            parts = Path(name).parts
            if info.is_dir():
                continue
            if name.startswith(("/", "\\")) or ".." in parts or ":" in name:
                shutil.rmtree(new, ignore_errors=True)
                sys.exit("refused: unsafe path in bundle: " + name)
            data = z.read(info)
            dst = new / name; dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(data)
            files.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    if not (new / "METHOD.md").exists():
        shutil.rmtree(new, ignore_errors=True)
        sys.exit("refused: bundle has no METHOD.md")
    shutil.rmtree(old, ignore_errors=True)
    if cur.exists():
        cur.rename(old)
    new.rename(cur)
    shutil.rmtree(old, ignore_errors=True)
    st = load_state(a.project)
    st.update({"content_version": a.version, "sha256": digest, "synced_at": datetime.datetime.now().isoformat(timespec="seconds"),
               "valid_until": a.valid_until or None, "files": files})
    save_state(a.project, st)
    print(f"synced Blocky StoryKit method {a.version}: {len(files)} files -> {cur}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("status"); s.add_argument("--project", default=".")
    t = sp.add_parser("touch"); t.add_argument("--project", default="."); t.add_argument("--valid-until", default="")
    f = sp.add_parser("fetch"); f.add_argument("--project", default="."); f.add_argument("--url", required=True)
    f.add_argument("--sha256", required=True); f.add_argument("--bytes", type=int, default=0); f.add_argument("--version", required=True)
    f.add_argument("--valid-until", default=""); f.add_argument("--dev", action="store_true", help="allow http://localhost test servers")
    sp.add_parser("install-id"); sp.add_parser("install-header")
    a = ap.parse_args()
    {"status": cmd_status, "touch": cmd_touch, "fetch": cmd_fetch,
     "install-id": cmd_install_id, "install-header": cmd_install_header}[a.cmd](a)


if __name__ == "__main__":
    main()
