from math import log2, ceil
from time import asctime
from jinja2 import Environment, PackageLoader, select_autoescape, StrictUndefined

import dataclasses

env = Environment(
    loader=PackageLoader(__package__),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)

def binstring(value, bits):
    """Turn value into a str bits long, handling two's compliment."""
    if value < 0:
        value = (2**bits) + value
    return f"{value:0{bits}b}"
env.filters['binstring'] = binstring

@dataclasses.dataclass
class Builder:
    """Generator class for a CIC filter."""
    
    ratio       : int
    dtype       : str
    input_min   : int
    input_max   : int
    stages      : int = 1
    async_reset : bool = False
    osvvm       : bool = False
    work        : str = 'work'
    name        : str = 'cic_decimator'
    program     : str = __name__
    
    def _cook(self):
        """Calculate all values that need calculating."""
        
        # Calculate bit growth and final value size.
        growth = self.ratio**self.stages
        self.output_min = self.input_min * growth
        self.output_max = self.input_max * growth
        
        if self.dtype == 'unsigned':
            def bits(x, y):
                return y.bit_length()
        else:
            def bits(x, y):
                bx = x.bit_length() + (0 if x < 0 else 1)
                by = y.bit_length() + (0 if y < 0 else 1)
                return bx if bx > by else by
        
        self.input_bits = bits(self.input_min, self.input_max)
        self.output_bits = bits(self.output_min, self.output_max)
        
        self.input_dtype = f'{self.dtype}({self.input_bits-1} downto 0)'
        self.output_dtype = f'{self.dtype}({self.output_bits-1} downto 0)'
    
    def generate_filter(self, output=None) -> str:
        """Generate the synthesizable filter VHDL.
        
        Args:
            output: If present, should be an open writable file.
            
        Returns:
            The VHDL as a string.
        """
        
        self._cook()
        template = env.get_template('filter.vhd')
        text = template.render(vars(self), now=asctime())
        return text
        
    def generate_testbench(self) -> str:
        """Generate the VHDL testbench code.
        
        Args:
            output: If present, should be an open writable file.
            
        Returns:
            The VHDL as a string.
        """
        
        self._cook()
        template = env.get_template('testbench.vhd')
        text = template.render(vars(self), now=asctime())
        return text
        
    def copy(self, **kwargs):
        """Make a copy of this Builder, with any changes specified in kwargs."""
        
        d = dataclasses.asdict(self)
        d.update(kwargs)
        
        return self.__class__(**d)
    
