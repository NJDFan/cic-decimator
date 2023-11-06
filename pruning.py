"""
Investigate Hogenaur pruning.

This code will all get integrated later, but right now it's an attempt
to square up with Rick Lyon's code.

"""

import numpy as np
from scipy.special import binom

R=25
M=1
N=4
N = 3;  R = 16;  M = 1;  Bin = 16;  Bout = 16

B_out = Bout

bit_growth = np.ceil(np.log2((R*M)**N))
B_max = Bin + bit_growth - 1

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
internal_bits = B_max + 1
bits_truncated = internal_bits - B_out
truncation_noise_var = 2**(2*bits_truncated)/12
truncation_noise_std = np.sqrt(truncation_noise_var)

# Calculate bits truncated.  This fails on the final
# truncation, which we patch manually
B_j = np.floor(
    -np.log2(F_j) +
    np.log2(truncation_noise_std) +
    (np.log2(6/N) / 2)
)
B_j[-1] = bits_truncated
print(B_j)
