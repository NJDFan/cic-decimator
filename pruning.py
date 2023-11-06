"""=16
Investigate Hogenaur pruning.

This code will all get integrated later, but right now it's an attempt
to square up with Rick Lyon's code.

"""

import numpy as np
from scipy.special import binom

R=128
M=1
N=3

B_in=16
B_out=16

bit_growth = np.ceil(np.log2((R*M)**N))
B_max = B_in + bit_growth - 1

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
# begin with.
# 
B_j[0] = 0
B_j[B_j < 0] = 0
print('Bits saved per stage:', B_j, 'Total:', np.sum(B_j))

# Leading to a final number of accumulator bits
print('Bits left per stage:', internal_bits - B_j[:-1], B_out)

