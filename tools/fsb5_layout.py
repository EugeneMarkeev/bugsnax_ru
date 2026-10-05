"""Validate PCM16 FSB5 layout independently of the voice bank builder.

Channel bits 5..6 encode 1/2/6/8 channels. Offset bits 7..33 count
32-byte blocks. Layout reference: vgmstream src/meta/fsb5.c.
"""
import struct

def validate_pcm_bank(raw):
    start=raw.index(b'FSB5')
    version,count,headers,names,data,codec=struct.unpack_from('<6I',raw,start+4)
    assert codec==2,'Expected PCM16 sound pack'
    base=64 if version==0 else 60
    pos=start+base
    entries=[]
    for _ in range(count):
        header,=struct.unpack_from('<Q',raw,pos);pos+=8
        channels=(1,2,6,8)[(header>>5)&3]
        offset=((header>>7)&0x7ffffff)*32
        frames=header>>34
        more=header&1
        while more:
            meta,=struct.unpack_from('<I',raw,pos);pos+=4
            more=meta&1;size=(meta>>1)&0xffffff;kind=meta>>25
            if kind==1:
                assert size==1
                channels=raw[pos]
            assert kind!=11,'PCM bank contains Vorbis codec metadata'
            pos+=size
        entries.append((offset,frames*channels*2,channels))
    assert pos==start+base+headers,'Sample header size mismatch'
    assert start+base+headers+names+data<=len(raw),'Truncated sample data'
    for i,(offset,length,channels) in enumerate(entries):
        end=entries[i+1][0] if i+1<len(entries) else data
        assert channels>0 and length>0
        assert 0<=end-offset-length<32, f'Sample {i}: invalid channels, offset or PCM length'
    return count
