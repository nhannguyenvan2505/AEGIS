"""Prepare local multipart fixtures without changing any dataset source."""
import argparse
import shutil
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--image', type=Path, default=Path(r'D:\AEGIS-AI\datasets\processed\aegis_rice_v4\images\val\blast__blast_100.jpg'))
args = parser.parse_args()
if not args.image.is_file():
    parser.error('Image not found. Pass --image with a valid JPEG path.')
root = Path(__file__).resolve().parents[1] / 'postman/fixtures'
root.mkdir(parents=True, exist_ok=True)
shutil.copyfile(args.image, root/'sample.jpg')
(root/'empty.bin').write_bytes(b'')
(root/'invalid.txt').write_text('This is not an image.\n', encoding='utf-8')
with (root/'too-large.bin').open('wb') as stream:
    stream.truncate(8*1024*1024+1)
print('Prepared sample.jpg, empty.bin, invalid.txt, too-large.bin in', root)
