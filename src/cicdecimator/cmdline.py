"""CIC Decimator Builder class.

This is what actually does the work of generating the filters.  Actually the
Jinja engine is what actually actually does the work, but this wraps that.
"""

import argparse
import sys
import re

from .Builder import Builder

def parse_arguments(args = None):
    """Parse all command-line arguments, return namespace object.
    
    This also performs all the secondary checking, defaulting,
    and validation after the initial call.
    
    Args:
        args: A list of arguments, or None to use sys.argv.
    """
    
    parser = argparse.ArgumentParser(
        description = 'VHDL CIC decimator generator'
    )
    
    # Arguments for defining the size of the input data
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument(
        '--input-bits', type=int, help="Input data width, in bits"
    )
    grp.add_argument(
        '--input-range', help="Input data range, as ####-#### without spaces"
    )
    
    # Arguments for defining the filter itself.
    parser.add_argument(
        '--ratio', required=True,
        type=int, help="Decimation ratio R"
    )
    parser.add_argument('--dtype',
        choices=['unsigned', 'signed'], default='unsigned', help="Data type"
    )
    parser.add_argument('--stages',
        type=int, default=1, help="Number of cascaded stages N"
    )
    parser.add_argument('--async-reset',
        action='store_true', help="Use an asynchronous reset."
    )
    parser.add_argument('--osvvm',
        action='store_true', help="Use OSVVM assertion tools."
    )
    
    # Arguments about the environment.
    parser.add_argument('--work',
        default='work', help='VHDL library name for CIC filter. Default is work'
    )
    parser.add_argument('--name',
        default='cic_decimator', help='VHDL entity name for CIC filter. Default is cic_decimator'
    )
    parser.add_argument('--filter-file',
        help='Filename for CIC filter. Default is <entity name>.vhd'
    )
    parser.add_argument('--tb-file',
        help='Filename for testbench. Default is tb_<entity name>.vhd'
    )
    
    ns = parser.parse_args(args)
    
    # Turn the input information into input_min and input_max values.
    if ns.input_bits:
        if ns.dtype == 'unsigned':
            ns.input_min = 0
            ns.input_max = (2**ns.input_bits) - 1
        else:
            ns.input_min = -(2**(ns.input_bits-1))
            ns.input_max = (2**(ns.input_bits-1)) - 1
    else:
        mo = re.search(r'([-+]?\d+)\s*-\s*([-+]?\d+)', ns.input_range)
        if mo:
            ns.input_min = int(mo.group(1))
            ns.input_max = int(mo.group(2))
            if ns.input_min > ns.input_max:
                ns.input_max, ns.input_min = ns.input_min, ns.input_max
        else:
            parser.error("Unrecognized input range " + ns.input_range)
    
    if ns.dtype == 'unsigned' and ((ns.input_min < 0) or (ns.input_max < 0)):
        parser.error("Signed input data range with unsigned data type")
    
    # Sanity check the VHDL entity name, and fill in missing filenames
    if not re.match(r'[a-zA-Z]\w+', ns.name):
        parser.error("Illegal VHDL entity name: " + ns.name)
    if not ns.filter_file:
        ns.filter_file = ns.name + '.vhd'
    if not ns.tb_file:
        ns.tb_file = 'tb_' + ns.name + '.vhd'
    
    ns.program = parser.prog
    return ns
    
def main(args=None):
    """Entry point for the command-line program."""
    ns = parse_arguments(args)
    builder = Builder(
        ratio       = ns.ratio,
        dtype       = ns.dtype,
        input_min   = ns.input_min,
        input_max   = ns.input_max,
        stages      = ns.stages,
        async_reset = ns.async_reset,
        osvvm       = ns.osvvm,
        work        = ns.work,
        name        = ns.name,
        program     = ns.program
    )
    
    with open(ns.filter_file, 'w') as f:
        print(builder.generate_filter(), file=f)
    print(f"Wrote {ns.name} to {ns.filter_file}")
        
    with open(ns.tb_file, 'w') as f:
        print(builder.generate_testbench(), file=f)
    print(f"Wrote tb_{ns.name} to {ns.tb_file}")
