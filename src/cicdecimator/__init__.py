"""CIC Decimating Filter Generator"""

import argparse
import sys
import re
from math import log2, ceil
from time import asctime
from jinja2 import Environment, PackageLoader, select_autoescape, StrictUndefined

env = Environment(
    loader=PackageLoader(__package__),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)

def parse_arguments(args:list[str] = None):
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
        help='Filename for testbench. Default is <entity name>_tb.vhd'
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
        ns.tb_file = ns.name + '_tb.vhd'
    
    ns.program = parser.prog
    return ns
    
def generate_cic(ns):
    """Generate and write out the CIC filter and testbench.
    """
    
    # Determine the range of possible values at each step
    stage_growth = [ns.ratio**n for n in range(ns.stages+1)]
    stage_min    = [ns.input_min * g for g in stage_growth]
    stage_max    = [ns.input_max * g for g in stage_growth]
    
    # And the datatypes for each step
    if ns.dtype == 'unsigned':
        def bits(x, y):
            return y.bit_length()
    else:
        def bits(x, y):
            bx = x.bit_length() + (0 if x < 0 else 1)
            by = y.bit_length() + (0 if y < 0 else 1)
            return bx if bx > by else by

    stage_bits = [bits(*p) for p in zip(stage_min, stage_max)]
    stage_dtype = [f'{ns.dtype}({b-1} downto 0)' for b in stage_bits]
    
    for (x, y, t) in zip(stage_min, stage_max, stage_dtype):
        print(f'{t}:  {x}-{y}')
    
    tp_vars = vars(ns)
    tp_vars['stage_dtype'] = stage_dtype
    tp_vars['stage_min'] = stage_min
    tp_vars['stage_max'] = stage_max
    
    template = env.get_template('filter.vhd')
    print(template.render(vars(ns)))
    
        
def main(args=None):
    ns = parse_arguments(args)
    print(ns)
    
    env.globals['now'] = asctime()
    env.globals['program'] = ns.program
    
    gen = generate_cic(ns)
