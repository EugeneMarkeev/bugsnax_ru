#!/usr/bin/perl
# Repair only the authenticated legacy PCM16 pack; caller verifies both SHA-256s.
use strict;
use warnings;
use Digest::MD5 qw(md5);
my ($source,$target)=@ARGV;
die "Usage: repair_bank.pl source target\n" unless defined $target;
open my $input,'<:raw',$source or die "Open source: $!";
local $/; my $raw=<$input>; close $input;
my $fsb_at=index($raw,'FSB5'); die "Missing FSB5" if $fsb_at<0;
my ($version,$count,$headers_size,$names_size,$data_size,$codec)=unpack('V6',substr($raw,$fsb_at+4,24));
die "Expected legacy PCM16 bank" unless $codec==2;
my $base=$version==0 ? 64 : 60;
my $pos=$fsb_at+$base;
my $data_at=$fsb_at+$base+$headers_size+$names_size;
my $headers='';my $data='';
for my $index (0..$count-1) {
    my $header=unpack('Q<',substr($raw,$pos,8));$pos+=8;
    my $more=$header&1;my $chunks='';
    while ($more) {
        my $meta=unpack('V',substr($raw,$pos,4));
        my $size=($meta>>1)&0xffffff;
        $chunks.=substr($raw,$pos,4+$size);$pos+=4+$size;
        $more=$meta&1;
    }
    my $channels=(($header>>5)&1)+1;
    my $frames=$header>>34;
    my $old_offset=(($header>>6)&0xfffffff)*16;
    my $length=$frames*$channels*2;
    die "Sample outside source data" if $old_offset+$length>$data_size;
    $data.="\0" x ((32-length($data)%32)%32);
    my $offset=length($data);
    my $new_header=($header&0x3f)|((int($offset/32))<<7)|($frames<<34);
    $headers.=pack('Q<',$new_header).$chunks;
    $data.=substr($raw,$data_at+$old_offset,$length);
}
die "Sample header size mismatch" unless $pos==$fsb_at+$base+$headers_size;
my $names=substr($raw,$fsb_at+$base+$headers_size,$names_size);
my $header=substr($raw,$fsb_at,$base);
substr($header,12,4)=pack('V',length($headers));
substr($header,20,4)=pack('V',length($data));
substr($header,36,16)=md5($data);
my $fsb=$header.$headers.$names.$data;
my $result=substr($raw,0,12);$pos=12;my $found=0;
while ($pos<length($raw)) {
    my $tag=substr($raw,$pos,4);
    my $size=unpack('V',substr($raw,$pos+4,4));
    my $content=substr($raw,$pos+8,$size);
    if ($tag eq 'SND ') {
        my $prefix=$fsb_at-($pos+8);
        die "Invalid SND chunk" if $found || $prefix<0;
        $content=substr($content,0,$prefix).$fsb;$found=1;
    }
    $result.=$tag.pack('V',length($content)).$content;
    $result.="\0" if length($content)%2;
    $pos+=8+$size+$size%2;
}
die "Missing SND chunk" unless $found;
substr($result,4,4)=pack('V',length($result)-8);
my $sndh=index($raw,'SNDH');die "Missing SNDH" if $sndh<0;
substr($result,$sndh+16,4)=pack('V',length($fsb));
open my $output,'>:raw',$target or die "Open target: $!";
print {$output} $result or die "Write: $!";
close $output or die "Close: $!";
