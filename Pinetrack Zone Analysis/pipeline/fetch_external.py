"""Download the public datasets the pipeline uses (both hosted on GitHub).
  1. LA Metro rail GTFS (track geometry, stations, schedule)
  2. Beijing Subway car-body vibration dataset (CC-BY) - a split zip; standard unzip tools fail on it,
     so the entries are inflated directly."""
import os, subprocess, struct, zlib, mmap, pandas as pd
ROOT = os.path.join(os.path.dirname(__file__), '..'); EXT = os.path.join(ROOT, 'ext'); os.makedirs(EXT, exist_ok=True)

def clone(repo):
    dst = os.path.join(EXT, repo.split('/')[1])
    if not os.path.exists(dst): subprocess.run(['git', 'clone', '--depth', '1', f'https://github.com/{repo}', dst], check=True)
    return dst

def extract_split_zip(folder, stem, out_dir):
    parts = sorted(f for f in os.listdir(folder) if f.startswith(stem + '.z0')) + [stem + '.zip']
    cat = os.path.join(folder, '_cat.zip')
    with open(cat, 'wb') as o:
        for p in parts: o.write(open(os.path.join(folder, p), 'rb').read())
    os.makedirs(out_dir, exist_ok=True)
    with open(cat, 'rb') as f:
        m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ); p = 0
        while True:
            p = m.find(b'PK\x03\x04', p)
            if p < 0: break
            _, _, _, meth, _, _, _, cs, us, fnl, exl = struct.unpack('<IHHHHHIIIHH', m[p:p + 30])
            name = m[p + 30:p + 30 + fnl]
            if name.endswith(b'.txt') and fnl < 40:
                start = p + 30 + fnl + exl; dec = zlib.decompressobj(-15)
                with open(os.path.join(out_dir, name.decode()), 'wb') as o:
                    i = start
                    while not dec.eof and i < len(m):
                        chunk = m[i:i + (1 << 22)]; i += len(chunk); o.write(dec.decompress(chunk))
            p += 4
    os.remove(cat)

if __name__ == '__main__':
    clone('LACMTA/gtfs_rail')
    bj = clone('Elscip/scidata_jrrt_1')
    unz = os.path.join(bj, 'unz'); extract_split_zip(bj, 'scidata_jrrt_1', unz)
    pd.read_csv(os.path.join(unz, 'trainningdataset.txt'), sep='\t').to_pickle(os.path.join(EXT, 'bj_train.pkl'))
    pd.read_csv(os.path.join(unz, 'testingdataset.txt'), sep='\t').to_pickle(os.path.join(EXT, 'bj_test.pkl'))
    print('external data ready in', EXT)
