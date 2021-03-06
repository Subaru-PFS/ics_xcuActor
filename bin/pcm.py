#!/usr/bin/env python

from __future__ import print_function
from past.builtins import basestring
import argparse
import logging
import shlex
import sys

from xcuActor.Controllers import PCM

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if isinstance(argv, basestring):
        argv = shlex.split()

    parser = argparse.ArgumentParser('Run PCM commands')
    parser.add_argument('--on', type=str, action='append', choices=PCM.PCM.powerPorts, default=[],
                        help='turn on one of the PCM power ports')
    parser.add_argument('--off', type=str, action='append', choices=PCM.PCM.powerPorts, default=[],
                        help='turn off one of the PCM power ports')
    parser.add_argument('--host', type=str, action='store', default=None,
                        help='the IP address/name of the PCM board')
    parser.add_argument('--cam', type=str, action='store', default=None,
                        help='the name of the PCM board\'s camera')
    parser.add_argument('--raw', type=str, action='store', default=None,
                        help='a raw command to send')
    parser.add_argument('--debug', action='store_true')

    args = parser.parse_args(argv)
    print(argv)
    print(args)

    if args.cam is not None:
        host = 'pcm-%s.pfs' % (args.cam)
    elif args.host is not None:
        host = args.host
    else:
        raise RuntimeError('either --cam or --host must be specified')
    
    pcm = PCM.PCM(host=host, loglevel=logging.DEBUG if args.debug else logging.INFO)
    
    for p in args.off:
        print("turning %s %s off" % (host, p))
        pcm.powerOff(p)
    for p in args.on:
        print("turning %s %s on" % (host, p))
        pcm.powerOn(p)

    if args.raw is not None:
        print("sending %s raw command: %s" % (host, args.raw))
        print(" returned: %s" % (pcm.pcmCmd(args.raw)))
        
if __name__ == "__main__":
    main()
    
