"""Export only browser reports. Authentication must be provided by Cloudflare Access."""
import argparse
from pathlib import Path
import shutil

INDEX = '''<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Tahminlerim</title><style>body{font:17px system-ui;background:#0d1523;color:#edf4ff;margin:0;padding:24px}main{max-width:650px;margin:auto}a{display:block;background:#192941;color:inherit;text-decoration:none;padding:24px;margin:18px 0;border-radius:18px}small{color:#afc0d8}</style><main><h1>Tahminlerim</h1><small>Raporu seç</small><a href="futbol/">⚽ Futbol</a><a href="basketbol/">🏀 Basketbol</a></main></html>'''


def build(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    if target.exists() and any(target.iterdir()):
        raise ValueError('Output directory must be empty')
    reports = {sport: source / sport / (sport + '.html') for sport in ('futbol', 'basketbol')}
    if any(not path.is_file() or path.is_symlink() for path in reports.values()):
        raise ValueError('Both published reports must exist as regular files')
    target.mkdir(parents=True, exist_ok=True)
    for sport, path in reports.items():
        folder = target / sport
        folder.mkdir()
        shutil.copyfile(path, folder / 'index.html')
    (target / 'index.html').write_text(INDEX)
    (target / '_headers').write_text('/*\n  Cache-Control: private, no-store\n  X-Robots-Tag: noindex, nofollow, noarchive\n  Referrer-Policy: no-referrer\n  X-Content-Type-Options: nosniff\n')
    # Headers are defense in depth, NOT authentication. Do not deploy before Access verification.


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    build(args.source, args.output)
