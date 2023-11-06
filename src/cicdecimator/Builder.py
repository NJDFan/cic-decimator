from math import log2, ceil
from time import asctime
from jinja2 import Environment, PackageLoader, select_autoescape, StrictUndefined
import numpy as np
from scipy.special import binom

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
    output_width : int = None
    
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
        self.internal_bits = internal_bits = bits(self.output_min, self.output_max)
        
        output_width = self.output_width
        if output_width is None:
            # With no constraint we make the output full width
            output_width = internal_bits
        
        # Configure 2*N + 1 stage widths.
        # stage_width[0] is the input to (and width of) the
        #   first integrator
        # stage_width[N] is the truncated output of the last
        #   integrator and input to (and width of) the first comb
        # stage_width[2*N] is the truncated output of the last comb
        #
        self.output_bits = output_width
        if output_width >= internal_bits:
            self.calculate_untrimmed_stages()
        else:
            self.calculate_trimmed_stages()
        
        self._cooked = True
    
    def calculate_untrimmed_stages(self):
        """Calculate self.stage_widths with no bit trimming, and
        potential expansion into the last stage."""
        
        self.stage_widths = np.ones(self.stages * 2 + 1) * self.internal_bits
        self.stage_widths[-1] = self.output_bits
    
    def calculate_trimmed_stages(self):
        """Calculate self.stage_widths with bit trimming per stage
        as described in Hogenauer."""
        
        # This logic is nearly a transcription of Richard Lyons Feb., 2012
        # https://www.dsprelated.com/showarticle/160.php
        #
        # I'm glad Rick understood the math from the original paper enough
        # to implement this, because I did not.
        #
        
        R=self.ratio
        M=1
        N=self.stages

        # Preallocate the F_j array
        F_j = np.zeros(2*N+1)

        # Calculate F_j for all but the last integrator stages
        for j in range(N-1, 0, -1):
            h_j = np.zeros((R*M-1)*N + j)
            for k in range(len(h_j)):
                L = np.arange(np.floor(k/(R*M))+1)
                points = binom(N, L)*binom(N-j+k-(R*M*L), k-(R*M*L))
                points[1::2] *= -1
                h_j[k] = np.sum(points)
            F_j[j-1] = np.sqrt(np.sum(h_j ** 2))

        # Pre-calculated F_j for up to 7 comb stages
        canned_F = np.sqrt([1, 2, 6, 20, 70, 252, 924, 3424])

        # Assign F_k for the comb stages
        F_j[N:] = np.flip(canned_F[0:N+1])

        # And go back for the last integrator stage.
        F_j[N-1] = F_j[N+1] * np.sqrt(R*M)
    
        # Now cook down the stages
        bits_truncated = self.internal_bits - self.output_bits
        truncation_noise_var = 2**(2*bits_truncated)/12
        truncation_noise_std = np.sqrt(truncation_noise_var)

        # Calculate bits truncated.  This fails on the final
        # truncation, which we patch manually.
        #
        # This number is the total number of pruned bits from
        # internal_bits at any given stage, not the incremental
        # number of bits pruned.
        #
        B_j = np.floor(
            -np.log2(F_j) +
            np.log2(truncation_noise_std) +
            (np.log2(6/N) / 2)
        ).astype(int)
        B_j[-1] = bits_truncated

        # Pruning the input stage (B_j[0]) just feels gross.
        # And other stages can come up with negative stage
        # growth if the filter is relying on the growth to
        # begin with.  Make all applicable stages 0 truncation
        # 
        B_j[0] = 0
        B_j[B_j < 0] = 0
        
        # Take those lost bits off the stage widths as needed.
        self.stage_widths = int(self.internal_bits) - B_j

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
    
