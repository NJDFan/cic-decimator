from math import log2, ceil
from time import asctime
from jinja2 import Environment, PackageLoader, select_autoescape, StrictUndefined
import numpy as np

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
    
    # Track whether this data has been cooked yet
    _cooked = False
    
    def __setattr__(self, attr, value):
        if attr != '_cooked':
            self._cooked = False
        self.__dict__[attr] = value
    
    def _cook(self):
        """Calculate all values that need calculating."""
        if self._cooked:
            return
        
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
        
        self._cooked = True
    
    def H(self, z):
        """Transfer function in the Z-domain (relative to input signal)."""
        za = np.asanyarray(z, dtype=np.cfloat)
        with np.errstate(divide='ignore', invalid='ignore'):
            H = ((1-za**-self.ratio)/(1-za**-1))
        return np.where(np.isnan(H), self.ratio, H) ** self.stages
    
    def ampl(self, f):
        """Amplitude in the digital frequency domain (1.0 = input sampling freq)."""
        
        w = np.asanyarray(f, dtype=float) * np.pi
        with np.errstate(divide='ignore', invalid='ignore'):
            H = np.sin(w * self.ratio) / np.sin(w)
        return np.where(np.isnan(H), self.ratio, np.abs(H)) ** self.stages
    
    def delay(self):
        """Returns the group-delay of the filter, in input samples."""
        return (self.ratio * self.stages) / 2
    
    def generate_filter(self) -> str:
        """Generate the synthesizable filter VHDL.
        
        Returns:
            The VHDL as a string.
        """
        
        self._cook()
        template = env.get_template('filter.vhd')
        text = template.render(vars(self), now=asctime())
        return text
        
    def generate_testbench(self) -> str:
        """Generate the VHDL testbench code.
        
        Returns:
            The VHDL as a string.
        """
        
        self._cook()
        template = env.get_template('testbench.vhd')
        text = template.render(vars(self), now=asctime())
        return text
        
    def copy(self, **kwargs):
        """Make a copy of this Builder, with any changes specified in kwargs."""
        
        self._cook()
        d = dataclasses.asdict(self)
        d.update(kwargs)
        
        return self.__class__(**d)
    
