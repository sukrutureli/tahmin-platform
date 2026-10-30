"""Authenticated encrypted artifact directories. No plaintext/legacy fallback."""
import argparse
import base64
import io
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import zipfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b'TAHMIN-PRIVATE-1\n'
LIMIT = 2 * 1024 * 1024 * 1024


def key():
    try:
        value = base64.b64decode(os.environ.get('PRIVATE_ARTIFACT_KEY', ''), validate=True)
    except ValueError:
        raise ValueError('PRIVATE_ARTIFACT_KEY must be a base64 encoded 32-byte key') from None
    if len(value) != 32:
        raise ValueError('PRIVATE_ARTIFACT_KEY must be a base64 encoded 32-byte key')
    return value


def pack(source, target):
    secret = key()  # Fail before creating output when no key is configured.
    root = Path(source).resolve()
    if not root.is_dir():
        raise ValueError('Artifact source directory is missing')
    buffer = io.BytesIO()
    expanded = 0
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError('Symlinks are not allowed in private artifacts')
            if path.is_file():
                expanded += path.stat().st_size
                if expanded > LIMIT:
                    raise ValueError('Expanded artifact too large')
                archive.write(path, path.relative_to(root).as_posix())
    if len(buffer.getvalue()) > LIMIT:
        raise ValueError('Artifact too large')
    nonce = secrets.token_bytes(12)
    encrypted = MAGIC + nonce + AESGCM(secret).encrypt(nonce, buffer.getvalue(), MAGIC)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encrypted)


def unpack(source, target):
    payload = Path(source).read_bytes()
    if not payload.startswith(MAGIC):
        raise ValueError('Unencrypted or unsupported artifact; explicit migration required')
    nonce = payload[len(MAGIC):len(MAGIC) + 12]
    plaintext = AESGCM(key()).decrypt(nonce, payload[len(MAGIC) + 12:], MAGIC)
    root = Path(target).resolve()
    with zipfile.ZipFile(io.BytesIO(plaintext)) as archive:
        members = archive.infolist()
        if sum(item.file_size for item in members) > LIMIT:
            raise ValueError('Expanded artifact too large')
        seen = set()
        for item in members:
            path = PurePosixPath(item.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in item.filename
                    or not path.parts or item.filename in seen
                    or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError('Unsafe archive member')
            destination = root.joinpath(*path.parts).resolve()
            if not destination.is_relative_to(root):
                raise ValueError('Unsafe extraction destination')
            seen.add(item.filename)
        # Validate every member before writing any file.
        root.mkdir(parents=True, exist_ok=True)
        for item in members:
            destination = root.joinpath(*PurePosixPath(item.filename).parts)
            if item.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(item))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['pack', 'unpack'])
    parser.add_argument('source')
    parser.add_argument('target')
    args = parser.parse_args()
    try:
        (pack if args.mode == 'pack' else unpack)(args.source, args.target)
    except Exception as error:
        # Only fixed infrastructure categories; never paths, contents or key values.
        known = {'Expanded artifact too large', 'Artifact too large', 'Symlinks are not allowed in private artifacts', 'Artifact source directory is missing'}
        category = str(error) if isinstance(error, ValueError) and str(error) in known else type(error).__name__
        raise SystemExit('Private artifact operation failed (' + category + '); no plaintext fallback') from None

