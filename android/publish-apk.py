#!/usr/bin/env python3
"""Publish a signed APK on the website download page.

Usage (from the repository root, after `bash android/build-apk.sh`):
    python3 android/publish-apk.py android/build/faraz-pharmacy-1.8.0.apk 1.8.0

It copies the APK into downloads/, writes its SHA-256 file, and updates android-app.html
(download link, version line, size and checksum). Review the diff, then commit and push.
Nothing is changed unless the APK file exists and the version looks like 1.2.3.
"""
import hashlib, pathlib, re, shutil, sys

def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    apk, version = pathlib.Path(sys.argv[1]), sys.argv[2]
    if not apk.is_file():
        sys.exit(f"APK not found: {apk}")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit("Version must look like 1.8.0")
    root = pathlib.Path(__file__).resolve().parent.parent
    data = apk.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    size_kb = max(1, round(len(data) / 1024))
    name = f"faraz-pharmacy-{version}.apk"
    (root / "downloads").mkdir(exist_ok=True)
    shutil.copyfile(apk, root / "downloads" / name)
    (root / "downloads" / f"faraz-pharmacy-{version}.sha256").write_text(f"{digest}  {name}\n")
    page = root / "android-app.html"
    html = page.read_text(encoding="utf-8")
    html, n1 = re.subn(r"downloads/faraz-pharmacy-\d+\.\d+\.\d+\.apk", f"downloads/{name}", html)
    html, n2 = re.subn(r"Version \d+\.\d+\.\d+ · Android 8\.0 or newer · \d+ KB", f"Version {version} · Android 8.0 or newer · {size_kb} KB", html)
    html, n3 = re.subn(r"<code>[0-9a-f]{64}</code>", f"<code>{digest}</code>", html)
    if (n1, n2, n3) != (1, 1, 1):
        sys.exit(f"android-app.html did not match the expected layout (matches: {n1},{n2},{n3}); nothing was written")
    page.write_text(html, encoding="utf-8")
    print(f"Published {name}: {size_kb} KB, sha256 {digest}")

main()
