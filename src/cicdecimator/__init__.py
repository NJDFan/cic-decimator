import argparse
import sys
import re
from math import log2, ceil
from io import TextIOBase


def parse_arguments(args):
    parser = argparse.ArgumentParser(
        prog = 'cic-decimator',
        description = 'VHDL CIC decimator generator'
    )
    
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument(
        '--input-bits', type=int, help="Input data width, in bits"
    )
    grp.add_argument(
        '--input-range', help="Input data range, as ####-#### without spaces"
    )
    
    parser.add_argument(
        '--ratio', required=True,
        type=int, help="Decimation ratio"
    )
    parser.add_argument('--dtype',
        choices=['unsigned', 'signed'], default='unsigned', help="Data type"
    )
    parser.add_argument('--stages',
        type=int, default=1, help="Number of cascaded stages"
    )
    ns = parser.parse_args(args)
    
    if ns.input_bits:
        if ns.dtype == 'unsigned':
            ns.input_min = 0
            ns.input_max = (2**ns.input_bits) - 1
        else:
            ns.input_min = -(2**(ns.input_bits-1))
            ns.input_max = (2**(ns.input_bits-1)) - 1
    else:
        mo = re.match(r'([-+]?\d+)\s*-\s*([-+]?\d+)', ns.input_range)
        if mo:
            ns.input_min = int(mo.group(1))
            ns.input_max = int(mo.group(2))
            if ns.input_min > ns.input_max:
                ns.input_max, ns.input_min = ns.input_min, ns.input_max
        else:
            parser.error("Unrecognized input range " + ns.input_range)
    
    if ns.dtype == 'unsigned' and ((ns.input_min < 0) or (ns.input_max < 0)):
        parser.error("Signed input data range with unsigned data type")
    
    return ns
    
class CIC_Generator:
    def __init__(self,
        input_min   : int,
        input_max   : int,
        ratio       : int,
        stages      : int,
        dtype       : str,
        output      : TextIOBase = sys.stdout
    ):
              
        """
        CIC decimator generator.
        
        Attributes:
            output_width:   Number of bits in the output data.
            input_dtype:    Input data type
            output_dtype:   Output data type
        """
        
        self.input_min   = input_min 
        self.input_max   = input_max 
        self.ratio       = ratio     
        self.stages      = stages    
        self.dtype       = dtype     
        self.output      = output    
        
        # Determine the range of possible values at each step
        stage_growth = [self.ratio**n for n in range(self.stages+1)]
        stage_min    = [self.input_min * g for g in stage_growth]
        stage_max    = [self.input_max * g for g in stage_growth]
        
        # And the datatypes for each step
        if self.dtype == 'unsigned':
            def bits(x, y):
                return y.bit_length()
        else:
            def bits(x, y):
                bx = x.bit_length() + (0 if x < 0 else 1)
                by = y.bit_length() + (0 if y < 0 else 1)
                return bx if bx > by else by

        stage_dtypes = [
            '{}({} downto 0)'.format(self.dtype, bits(x, y))
            for (x, y) in zip(stage_min, stage_max)
        ]
        self.stage_dtypes = stage_dtypes
        
def main(args=None):
    ns = parse_arguments(args)
    print(ns)
    
    gen = CIC_Generator(
        ns.input_min, ns.input_max, ns.ratio, ns.stages,
        ns.dtype
    )
    for dt in gen.stage_dtypes:
        print(dt)
