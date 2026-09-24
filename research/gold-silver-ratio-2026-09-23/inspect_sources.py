from pathlib import Path
import urllib.request
import json
import hashlib
import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'sources'
RAW.mkdir(exist_ok=True)
URLS = {
    'worldbank_monthly.xlsx': 'https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx',
    'silver_institute_ratio_2026.pdf': 'https://silverinstitute.org/wp-content/uploads/2026/07/Is-the-Gold-Silver-Ratio-Relevant-Today.pdf',
}
metadata = {}
for name, url in URLS.items():
    path = RAW / name
    try:
        if not path.exists():
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
            path.write_bytes(data)
        data = path.read_bytes()
        metadata[name] = {'url': url, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'retrieved_date': '2026-09-23'}
        print(name, len(data))
        if name.endswith('.xlsx'):
            book = pd.ExcelFile(path)
            print('SHEETS', book.sheet_names)
            for s in book.sheet_names[:3]:
                frame = pd.read_excel(path, sheet_name=s, header=None)
                print(s, frame.shape)
                print(frame.head(8).to_string(index=False, header=False))
                print(frame.tail(2).to_string(index=False, header=False))
        else:
            reader = PdfReader(path)
            body = '\n\n'.join(f'PAGE {i+1}\n{page.extract_text()}' for i, page in enumerate(reader.pages))
            path.with_suffix('.txt').write_text(body, encoding='utf-8')
            print('PDF pages', len(reader.pages))
    except Exception as exc:
        metadata[name] = {'url': url, 'error': str(exc)}
        print(name, type(exc).__name__, str(exc))
(ROOT / 'source_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
