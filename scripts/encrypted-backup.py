"""Authenticated encryption for a trusted portable backup using existing cryptography.

Run on Linux as the backup administrator. No dependency installation is performed.
Keep the independent 32-byte URL-safe base64 key outside Git/sync and copy it to
protected recovery storage before relying on an encrypted backup.
"""
import argparse
import io
import os
from pathlib import Path
import stat
import sys
import tarfile
from cryptography.fernet import Fernet
sys.path.insert(0, str(Path(__file__).resolve().parent))
import recovery


def exclusive(path, payload):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def seal(folder, key, output):
    recovery.validate_bundle(folder)
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w') as archive:
        for name in sorted(recovery.FILES | {'manifest.json'}):
            archive.add(folder/name,arcname=name,recursive=False)
    plaintext=buffer.getvalue()
    cipher=Fernet(key)
    encrypted=cipher.encrypt(plaintext)
    assert cipher.decrypt(encrypted)==plaintext
    exclusive(output,encrypted)


def unseal(source, key, output):
    # Authentication succeeds before any plaintext is written.
    plaintext=Fernet(key).decrypt(source.read_bytes())
    with tarfile.open(fileobj=io.BytesIO(plaintext)) as archive:
        members=archive.getmembers()
        if (len(members)!=len(recovery.FILES)+1 or
            {m.name for m in members} != recovery.FILES | {'manifest.json'} or
            any(not m.isfile() for m in members)):
            raise ValueError('Unexpected encrypted backup inventory')
        output.mkdir(mode=0o700)  # Refuse overwrite/merge.
        for member in members:
            exclusive(output/member.name,archive.extractfile(member).read())
    recovery.validate_bundle(output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['seal','unseal'])
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--key-file',type=Path,required=True)
    args=parser.parse_args()
    os.umask(0o077)
    info=args.key_file.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o600:
        raise ValueError('Key must be a regular owner-only file')
    key=args.key_file.read_bytes().strip()
    if args.action=='seal': seal(args.source,key,args.output)
    else: unseal(args.source,key,args.output)
    print('PASS: authenticated backup '+args.action+'; secret contents withheld')


if __name__=='__main__':
    try: main()
    except Exception as error:
        raise SystemExit('Encrypted backup failed ('+type(error).__name__+'); no credentials printed.')
