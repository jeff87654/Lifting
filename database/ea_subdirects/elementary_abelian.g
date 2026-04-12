###############################################################################
# elementary_abelian.g - Precomputed elementary abelian subdirects
#
# Contains subdirects of C_p^n x C_p^n for various (p, n) combinations.
# Each entry EA_SUBDIRECTS_DATA.("p_n") is a list of basis matrices.
# The matrices are stored as lists of integer lists (coefficients in Z/pZ).
#
# For C_p x C_p (n=1), subdirects are:
#   - Full space GF(p)^2 (basis [[1,0],[0,1]])
#   - p-1 diagonal subspaces {(t, kt) : t in GF(p)} for k = 1,...,p-1
#     Each given by basis [[1,k]]
###############################################################################

EA_SUBDIRECTS_DATA := rec(
  ("2_1") := [
    # C_2 x C_2 subdirects (2 total)
    # Full space
    [ [1, 0], [0, 1] ],
    # Diagonal: k=1
    [ [1, 1] ]
  ],
  ("3_1") := [
    # C_3 x C_3 subdirects (3 total: full + 2 diagonals)
    [ [1, 0], [0, 1] ],
    [ [1, 1] ],
    [ [1, 2] ]
  ],
  ("5_1") := [
    # C_5 x C_5 subdirects (5 total: full + 4 diagonals)
    [ [1, 0], [0, 1] ],
    [ [1, 1] ],
    [ [1, 2] ],
    [ [1, 3] ],
    [ [1, 4] ]
  ],
  ("7_1") := [
    # C_7 x C_7 subdirects (7 total: full + 6 diagonals)
    [ [1, 0], [0, 1] ],
    [ [1, 1] ],
    [ [1, 2] ],
    [ [1, 3] ],
    [ [1, 4] ],
    [ [1, 5] ],
    [ [1, 6] ]
  ],
  ("11_1") := [
    # C_11 x C_11 subdirects (11 total)
    [ [1, 0], [0, 1] ],
    [ [1, 1] ],
    [ [1, 2] ],
    [ [1, 3] ],
    [ [1, 4] ],
    [ [1, 5] ],
    [ [1, 6] ],
    [ [1, 7] ],
    [ [1, 8] ],
    [ [1, 9] ],
    [ [1, 10] ]
  ],
  ("13_1") := [
    # C_13 x C_13 subdirects (13 total)
    [ [1, 0], [0, 1] ],
    [ [1, 1] ],
    [ [1, 2] ],
    [ [1, 3] ],
    [ [1, 4] ],
    [ [1, 5] ],
    [ [1, 6] ],
    [ [1, 7] ],
    [ [1, 8] ],
    [ [1, 9] ],
    [ [1, 10] ],
    [ [1, 11] ],
    [ [1, 12] ]
  ],
  ("2_2") := [
    # C_2^2 x C_2^2 = GF(2)^4 subdirects
    # A subspace W <= GF(2)^4 is subdirect if it projects onto both factors
    # i.e., for each of [1..2] and [3..4], some basis vector has nonzero entry

    # Dimension 4: full space (always subdirect)
    [ [1,0,0,0], [0,1,0,0], [0,0,1,0], [0,0,0,1] ],

    # Dimension 3: 15 such subspaces exist, here are representatives
    [ [1,0,0,0], [0,1,0,0], [0,0,1,1] ],
    [ [1,0,0,0], [0,1,0,1], [0,0,1,0] ],
    [ [1,0,0,0], [0,1,1,0], [0,0,0,1] ],
    [ [1,0,0,1], [0,1,0,0], [0,0,1,0] ],
    [ [1,0,1,0], [0,1,0,0], [0,0,0,1] ],
    [ [1,1,0,0], [0,0,1,0], [0,0,0,1] ],
    [ [1,0,0,0], [0,1,1,1], [0,0,0,1] ],
    [ [1,0,0,1], [0,1,0,1], [0,0,1,0] ],
    [ [1,0,0,1], [0,1,1,0], [0,0,0,1] ],
    [ [1,0,1,0], [0,1,0,1], [0,0,0,1] ],
    [ [1,0,1,0], [0,1,1,0], [0,0,0,1] ],
    [ [1,0,1,1], [0,1,0,0], [0,0,0,1] ],
    [ [1,1,0,0], [0,0,1,1], [0,0,0,1] ],
    [ [1,1,0,1], [0,0,1,0], [0,0,0,1] ],
    [ [1,1,1,0], [0,0,0,1], [0,0,1,0] ],

    # Dimension 2: subdirect if both factors have nonzero projection
    [ [1,0,1,0], [0,1,0,1] ],
    [ [1,0,1,1], [0,1,0,1] ],
    [ [1,0,1,0], [0,1,1,1] ],
    [ [1,0,1,1], [0,1,1,0] ],
    [ [1,1,1,0], [0,1,0,1] ],
    [ [1,1,0,1], [0,1,1,0] ],
    [ [1,1,1,1], [0,1,0,1] ],
    [ [1,1,0,1], [0,1,1,1] ],
    [ [1,1,1,0], [0,1,1,1] ],
    [ [1,1,1,1], [0,1,1,0] ]
  ]
);

Print("Loaded elementary abelian subdirects database.\n");
