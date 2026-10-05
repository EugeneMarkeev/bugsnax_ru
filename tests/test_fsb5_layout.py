import struct
import hashlib
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from fsb5_layout import validate_pcm_bank

def bank(legacy=False):
    # Two mono samples: 3 frames then 5 frames. The second needs padding.
    shift=6 if legacy else 7
    block=16 if legacy else 32
    offset=block
    headers=struct.pack('<QQ',(3<<34)|(9<<1),(5<<34)|(9<<1)|((offset//block)<<shift))
    data=b'\x00'*6+b'\x00'*max(0,offset-6)+b'\x00'*10
    return struct.pack('<4s6I',b'FSB5',1,2,len(headers),0,len(data),2)+b'\x00'*8+hashlib.md5(data).digest()+b'\x00'*8+headers+data

def riff_bank(legacy=False):
    fsb=bank(legacy)
    chunks=b'SNDH'+struct.pack('<4I',12,0,40,len(fsb))+b'SND '+struct.pack('<I',len(fsb))+fsb
    if len(fsb)%2:chunks+=b'\x00'
    return b'RIFF'+struct.pack('<I',len(chunks)+4)+b'FEV '+chunks

class FsbLayoutTests(unittest.TestCase):
    def test_two_mono_samples_with_32_byte_offsets(self):
        self.assertEqual(validate_pcm_bank(bank()),2)
    def test_old_16_byte_offset_writer_is_rejected(self):
        with self.assertRaises(AssertionError):validate_pcm_bank(bank(legacy=True))
    def test_truncated_pcm_is_rejected(self):
        with self.assertRaises(AssertionError):validate_pcm_bank(bank()[:-1])
