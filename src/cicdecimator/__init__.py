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
    
    # Calculate bit growth and final value size.
    growth = ns.ratio**ns.stages
    output_min = ns.input_min * growth
    output_max = ns.input_max * growth
    
    if ns.dtype == 'unsigned':
        def bits(x, y):
            return y.bit_length()
    else:
        def bits(x, y):
            bx = x.bit_length() + (0 if x < 0 else 1)
            by = y.bit_length() + (0 if y < 0 else 1)
            return bx if bx > by else by
    
    input_bits = bits(ns.input_min, ns.input_max)
    output_bits = bits(output_min, output_max)
    
    input_dtype = f'{ns.dtype}({input_bits-1} downto 0)'
    output_dtype = f'{ns.dtype}({output_bits-1} downto 0)'
    
    tp_vars = vars(ns)
    tp_vars.update({
        'ns' : ns,
        'input_dtype'  : input_dtype,
        'output_dtype' : output_dtype,
        'output_min' : output_min,
        'output_max' : output_max
    })
    
    template = env.get_template('filter.vhd')
    with open(ns.filter_file, 'w') as f:
        print(template.render(tp_vars), file=f)
    print(f"Wrote {ns.name} to {ns.filter_file}")
        
def main(args=None):
    ns = parse_arguments(args)
    print(ns)
    
    env.globals['now'] = asctime()
    env.globals['program'] = ns.program
    
    gen = generate_cic(ns)
