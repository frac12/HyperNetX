"""
Homology and Smith Normal Form
==============================
The purpose of computing the Homology groups for data generated
hypergraphs is to identify data sources that correspond to interesting
features in the topology of the hypergraph.

The elements of one of these Homology groups are generated by $k$
dimensional cycles of relationships in the original data that are not
bound together by higher order relationships. Ideally, we want the
briefest description of these cycles; we want a minimal set of
relationships exhibiting interesting cyclic behavior. This minimal set
will be a bases for the Homology group.

The cyclic relationships in the data are discovered using a **boundary
map** represented as a matrix. To discover the bases we compute the
**Smith Normal Form** of the boundary map.

Homology Mod2
-------------
This module computes the homology groups for data represented as an
abstract simplicial complex with chain groups $\{C_k\}$ and $Z_2$ additions.
The boundary matrices are represented as rectangular matrices over $Z_2$.
These matrices are diagonalized and represented in Smith
Normal Form. The kernel and image bases are computed and the Betti
numbers and homology bases are returned.

Methods for obtaining SNF for Z/2Z are based on Ferrario's work:
http://www.dlfer.xyz/post/2016-10-27-smith-normal-form/
"""

import numpy as np
import hypernetx as hnx
import warnings
import copy
from hypernetx import HyperNetXError
from collections import defaultdict
import itertools as it
import pickle


def kchainbasis(h, k):
    """
    Compute the set of k dimensional cells in the abstract simplicial
    complex associated with the hypergraph.

    Parameters
    ----------
    h : hnx.Hypergraph
    k : int
        dimension of cell

    Returns
    -------
     : list
        an ordered list of kchains represented as tuples of length k+1

    See also
    --------
    hnx.hypergraph.toplexes

    Notes
    -----
    - Method works best if h is simple [Berge], i.e. no edge contains another and there are no duplicate edges (toplexes).
    - Hypergraph node uids must be sortable.

    """

    import itertools as it
    kchains = set()
    for e in h.edges():
        if len(e) == k + 1:
            kchains.add(tuple(sorted(e.uidset)))
        elif len(e) > k + 1:
            kchains.update(set(it.combinations(sorted(e.uidset), k + 1)))
    return sorted(list(kchains))


def interpret(Ck, arr):
    """
    Returns the data as represented in Ck associated with the arr

    Parameters
    ----------
    Ck : list
        a list of k-cells being referenced by arr
    arr : np.array
        array of 0-1 vectors

    Returns
    ----
    : list
        list of k-cells referenced by data in Ck

    """

    output = list()
    for vec in arr:
        if len(Ck) != len(vec):
            raise HyperNetXError('elements of arr must have the same length as Ck')
        output.append([Ck[idx] for idx in range(len(vec)) if vec[idx] == 1])
    return output


def bkMatrix(km1basis, kbasis):
    """
    Compute the boundary map from $C_{k-1}$-basis to $C_k$ basis with
    respect to $Z_2$

    Parameters
    ----------
    km1basis : indexable iterable
        Ordered list of $k-1$ dimensional cell
    kbasis : indexable iterable
        Ordered list of $k$ dimensional cells

    Returns
    -------
    bk : np.array
        boundary matrix in $Z_2$ stored as boolean

    """
    bk = np.zeros((len(km1basis), len(kbasis)), dtype=int)
    for cell in kbasis:
        for idx in range(len(cell)):
            face = cell[:idx] + cell[idx + 1:]
            row = km1basis.index(face)
            col = kbasis.index(cell)
            bk[row, col] = 1
    return bk


def _rswap(i, j, S):
    """
    Swaps ith and jth row of copy of S

    Parameters
    ----------
    i : int
    j : int
    S : np.array

    Returns
    -------
    N : np.array
    """
    N = copy.deepcopy(S)
    row = copy.deepcopy(N[i])
    N[i] = copy.deepcopy(N[j])
    N[j] = row
    return N


def _cswap(i, j, S):
    """
    Swaps ith and jth column of copy of S

    Parameters
    ----------
    i : int
    j : int
    S : np.array
        matrix

    Returns
    -------
    N : np.array
    """
    N = _rswap(i, j, S.transpose()).transpose()
    return N


def swap_rows(i, j, *args):
    """
    Swaps ith and jth row of each matrix in args
    Returns a list of new matrices

    Parameters
    ----------
    i : int
    j : int
    args : np.arrays

    Returns
    -------
    list
        list of copies of args with ith and jth row swapped
    """
    output = list()
    for M in args:
        output.append(_rswap(i, j, M))
    return output


def swap_columns(i, j, *args):
    """
    Swaps ith and jth column of each matrix in args
    Returns a list of new matrices

    Parameters
    ----------
    i : int
    j : int
    args : np.arrays

    Returns
    -------
    list
        list of copies of args with ith and jth row swapped
    """
    output = list()
    for M in args:
        output.append(_cswap(i, j, M))
    return output


def add_to_row(M, i, j):
    """
    Replaces row i with logical xor between row i and j

    Parameters
    ----------
    M : np.array
    i : int
        index of row being altered
    j : int
        index of row being added to altered

    Returns
    -------
    N : np.array
    """
    N = copy.deepcopy(M)
    N[i] = 1 * np.logical_xor(N[i], N[j])
    return N


def add_to_column(M, i, j):
    """
    Replaces column i (of M) with logical xor between column i and j

    Parameters
    ----------
    M : np.array
        matrix
    i : int
        index of column being altered
    j : int
        index of column being added to altered

    Returns
    -------
    N : np.array
    """
    N = M.transpose()
    return add_to_row(N, i, j).transpose()


def logical_dot(ar1, ar2):
    """
    Returns the boolean equivalent of the dot product mod 2 on two 1-d arrays of
    the same length.

    Parameters
    ----------
    ar1 : numpy.ndarray
        1-d array
    ar2 : numpy.ndarray
        1-d array

    Returns
    -------
    : bool
        boolean value associated with dot product mod 2

    Raises
    ------
    HyperNetXError
        If arrays are not of the same length an error will be raised.
    """
    if len(ar1) != len(ar2):
        raise HyperNetXError('logical_dot requires two 1-d arrays of the same length')
    else:
        return 1 * np.logical_xor.reduce(np.logical_and(ar1, ar2))


def logical_matmul(mat1, mat2):
    """
    Returns the boolean equivalent of matrix multiplication mod 2 on two
    binary arrays stored as type boolean

    Parameters
    ----------
    mat1 : np.ndarray
        2-d array of boolean values
    mat2 : np.ndarray
        2-d array of boolean values

    Returns
    -------
    mat : np.ndarray
        boolean matrix equivalent to the mod 2 matrix multiplication of the
        matrices as matrices over Z/2Z

    Raises
    ------
    HyperNetXError
        If inner dimensions are not equal an error will be raised.

    """
    L1, R1 = mat1.shape
    L2, R2 = mat2.shape
    if R1 != L2:
        raise HyperNetXError("logical_matmul called for matrices with inner dimensions mismatched")

    mat = np.zeros((L1, R2), dtype=int)
    mat2T = mat2.transpose()
    for i in range(L1):
        if np.any(mat1[i]):
            for j in range(R2):
                mat[i, j] = logical_dot(mat1[i], mat2T[j])
        else:
            mat[i] = np.zeros((1, R2), dtype=int)
    return mat


def matmulreduce(arr, reverse=False):
    """
    Recursively applies a 'logical multiplication' to a list of boolean arrays.

    For arr = [arr[0],arr[1],arr[2]...arr[n]] returns product arr[0]arr[1]...arr[n]
    If reverse = True, returns product arr[n]arr[n-1]...arr[0]

    Parameters
    ----------
    arr : list of np.array
        list of nxm matrices represented as np.array
    reverse : bool, optional
        order to multiply the matrices

    Returns
    -------
    P : np.array
        Product of matrices in the list
    """
    if reverse:
        items = range(len(arr) - 1, -1, -1)
    else:
        items = range(len(arr))
    P = arr[items[0]]
    for i in items[1:]:
        P = logical_matmul(P, arr[i]) * 1
    return P


def logical_matadd(mat1, mat2):
    """
    Returns the boolean equivalent of matrix additon mod 2 on two
    binary arrays stored as type boolean

    Parameters
    ----------
    mat1 : np.ndarray
        2-d array of boolean values
    mat2 : np.ndarray
        2-d array of boolean values

    Returns
    -------
    mat : np.ndarray
        boolean matrix equivalent to the mod 2 matrix addition of the
        matrices as matrices over Z/2Z

    Raises
    ------
    HyperNetXError
        If dimensions are not equal an error will be raised.

    """
    S1 = mat1.shape
    S2 = mat2.shape
    mat = np.zeros(S1, dtype=int)
    if S1 != S2:
        raise HyperNetXError("logical_matadd called for matrices with different dimensions")
    if len(S1) == 1:
        for idx in range(S1[0]):
            mat[idx] = 1 * np.logical_xor(mat1[idx], mat2[idx])
    else:
        for idx in range(S1[0]):
            for jdx in range(S1[1]):
                mat[idx, jdx] = 1 * np.logical_xor(mat1[idx, jdx], mat2[idx, jdx])
    return mat


# Convenience methods for computing Smith Normal Form
# All of these operations have themselves as inverses

def _sr(i, j, M, L):
    return swap_rows(i, j, M, L)


def _sc(i, j, M, R):
    return swap_columns(i, j, M, R)


def _ar(i, j, M, L):
    return add_to_row(M, i, j), add_to_row(L, i, j)


def _ac(i, j, M, R):
    return add_to_column(M, i, j), add_to_column(R, i, j)


def _get_next_pivot(M, s1, s2=None):
    """
    Determines the first r,c indices in the submatrix of M starting
    with row s1 and column s2 index (row,col) that is nonzero,
    if it exists.

    Search starts with the s2th column and looks for the first nonzero
    s1 row. If none is found, search continues to the next column and so
    on.

    Parameters
    ----------
    M : np.array
        matrix represented as np.array
    s1 : int
        index of row position to start submatrix of M
    s2 : int, optional, default = s1
        index of column position to start submatrix of M

    Returns
    -------
    (r,c) : tuple of int or None

    """
    # find the next nonzero pivot to put in s,s spot for Smith Normal Form
    m, n = M.shape
    if not s2:
        s2 = s1
    for c in range(s2, n):
        for r in range(s1, m):
            if M[r, c]:
                return (r, c)
    return None


def smith_normal_form_mod2(M):
    """
    Computes the invertible transformation matrices needed to compute the
    Smith Normal Form of M modulo 2

    Parameters
    ----------
    M : np.array
        a rectangular matrix with data type bool
    track : bool
        if track=True will print out the transformation as Z/2Z matrix as it
        discovers L[i] and R[j]

    Returns
    -------
    L, R, S, Linv : np.arrays
        LMR = S is the Smith Normal Form of the matrix M.

    Note
    ----
    Given a mxn matrix $M$ with
    entries in $Z_2$ we start with the equation: $L M R = S$, where
    $L = I_m$, and $R=I_n$ are identity matrices and $S = M$. We
    repeatedly apply actions to the left and right side of the equation
    to transform S into a diagonal matrix.
    For each action applied to the left side we apply its inverse
    action to the right side of I_m to generate $L^{-1}$.
    Finally we verify:
    $L M R = S$ and  $LLinv = I_m$.
    """

    S = copy.copy(M)
    dimL, dimR = M.shape

    # initialize left and right transformations with identity matrices
    L = np.eye(dimL, dtype=int)
    R = np.eye(dimR, dtype=int)
    Linv = np.eye(dimL, dtype=int)
    for s in range(min(dimL, dimR)):
        # Find index pair (rdx,cdx) with value 1 in submatrix M[s:,s:]
        pivot = _get_next_pivot(S, s)
        if not pivot:
            break
        else:
            rdx, cdx = pivot
        # Swap rows and columns as needed so that 1 is in the s,s position
        if rdx > s:
            S, L = _sr(s, rdx, S, L)
            Linv = swap_columns(rdx, s, Linv)[0]
        if cdx > s:
            S, R = _sc(s, cdx, S, R)
        # add sth row to every row with 1 in sth column & sth column to every column with 1 in sth row
        row_indices = [idx for idx in range(s + 1, dimL) if S[idx, s] == 1]
        for rdx in row_indices:
            S, L = _ar(rdx, s, S, L)
            Linv = add_to_column(Linv, s, rdx)
        column_indices = [jdx for jdx in range(s + 1, dimR) if S[s, jdx] == 1]
        for cdx in column_indices:
            S, R = _ac(cdx, s, S, R)
    return L, R, S, Linv


def reduced_row_echelon_form_mod2(M):
    """
    Computes the invertible transformation matrices needed to compute
    the reduced row echelon form of M modulo 2

    Parameters
    ----------
    M : np.array
        a rectangular matrix with elements in $Z_2$

    Returns
    -------
    L, S, Linv : np.arrays
        LM = S where S is the reduced echelon form of M
        and M = LinvS
    """
    S = copy.deepcopy(M)
    dimL, dimR = M.shape

    # method with numpy
    Linv = np.eye(dimL, dtype=int)
    L = np.eye(dimL, dtype=int)

    s2 = 0
    s1 = 0
    while s2 <= dimR and s1 <= dimL:
        # Find index pair (rdx,cdx) with value 1 in submatrix M[s1:,s2:]
        # look for the first 1 in the s2 column
        pivot = _get_next_pivot(S, s1, s2)

        if not pivot:
            return L, S, Linv
        else:
            rdx, cdx = pivot
            if rdx > s1:
                # Swap rows as needed so that 1 leads the row
                S, L = _sr(s1, rdx, S, L)
                Linv = swap_columns(rdx, s1, Linv)[0]
            # add s1th row to every nonzero row
            row_indices = [idx for idx in range(0, dimL) if idx != s1 and S[idx, cdx] == 1]
            for idx in row_indices:
                S, L = _ar(idx, s1, S, L)
                Linv = add_to_column(Linv, s1, idx)
            s1, s2 = s1 + 1, cdx + 1

    return L, S, Linv


def coset(im2, bs=[], shortest=False):  # This breaks because line 529 has logical_xor on ndarray.
    # It only works on a simple array. will need to break it up on each dimension.
    # Do it by creating a method logical_matadd(*arr) and doing logical_xor.reduce on each element of the transpose.
    # Then transpose back. Will arkouda do this????
    """
    Generate the coset represented by bs, if bs=None
    returns the boundary group

    Parameters
    ----------
    im2 : np.array
        columns form a basis for the boundary group
    bs : np.array
        boolean vector from projection of kernel on cokernel

    Returns
    -------
     : list
        list of elements of the coset of interest
    """
    msg = """
    coset() is an very inefficient method for all but small examples.
    """
    warnings.warn(msg)
    if np.sum(im2) == 0:
        return None
    image_basis = np.array(im2.transpose())
    dim = image_basis.shape[0]
    coset = list()
    sh_len = np.sum(bs)
    for alpha in it.product([0, 1], repeat=dim):
        temp = np.logical_xor.reduce([a * image_basis[idx] for idx, a in enumerate(alpha)] + [bs], dtype=int)
        if shortest:
            if np.sum(temp) == sh_len:
                coset.append(temp)
            elif np.sum(temp) < sh_len:
                coset = [temp]
                sh_len = np.sum(temp)
        else:
            coset.append(temp)
    return coset


def homology_basis(bd, k, C=None, shortest=False, log=None):
    """
    Compute a basis for the kth-homology group with boundary
    matrices given by bd

    Parameters
    ----------
    bd : dict
        dict of k-boundary matrices keyed on k,k+1

    k : int
        k must be an integer greater than 0
        bd must have keys for k, and k+1
    C : list, optional
        list of k-cells used to interpret the generators
        bd[k] is boundary matrix with rows and columns indexed by
        k-1 and k cells. C is a list of k chains ordered
        to match the column index of bd[k]
    shortest : bool, optional
        option to look for shortest basis using boundaries
        *Warning*: This is only good for very small examples
    log : str, optional
        path to logfile where intermediate data should be
        pickled and stored

    Returns
    -------
    : list or dict
        list of generators as 0-1 tuples, if C then generators will be
        k-chains
        if shortest then returns a dictionary of shortest cycles for each coset.
    """
    L1, R1, S1, L1inv = smith_normal_form_mod2(bd[k])
    L2, R2, S2, L2inv = smith_normal_form_mod2(bd[k + 1])

    rank1 = np.sum(S1)
    rank2 = np.sum(S2)
    nullity1 = S1.shape[1] - rank1
    betti1 = S1.shape[1] - rank1 - rank2
    cokernel2_dim = S1.shape[1] - rank2

    print(f'Summary: \nrank{k} = {rank1}\nrank{k+1} = {rank2}\nnullity{k} = {nullity1}')

    ker1 = R1[:, rank1:]
    im2 = L2inv[:, :rank2]
    cokernel2 = L2inv[:, rank2:]
    cokproj2 = L2[rank2:, :]

    proj = matmulreduce([cokernel2, cokproj2, ker1]).transpose()
    ######
    print(proj)
    _, proj, _ = reduced_row_echelon_form_mod2(proj)
    proj = np.array(proj)
    proj = np.array([row for row in proj if np.any(row)])
    # print(f'hom basis reps: {proj*1}\n')
    basis = []
    if shortest:
        shortest_basis = list()
        for idx, bs in enumerate(proj):
            shortest_basis.append(coset(im2, bs=bs, shortest=True))
        if C:
            basis = [interpret(C, sb) for sb in shortest_basis]

        proj = shortest_basis
    else:
        if C:
            basis = interpret(C, proj)
        else:
            basis = proj
    if log:
        try:
            logdict = pickle.load(open(log, 'rb'))
        except:
            logdict = dict()
        logdict.update({'k': k,
                        f'betti{k}': betti1,
                        'ker': ker1,
                        'im': im2,
                        'proj': proj,
                        'basis': basis})
        pickle.dump(logdict, open(log, 'wb'))

    return basis


def hypergraph_homology_basis(h, k, shortest=False, log=None):
    """
    Computes the kth-homology group mod 2 for the ASC
    associated with the hypergraph h.

    Parameters
    ----------
    h : hnx.Hypergraph
    k : int
        k must be an integer greater than 0
    shortest : bool, optional
        option to look for shortest basis using boundaries
        only good for very small examples
    log : str, optional
        path to logfile where intermediate data should be
        pickled and stored

    Returns
    -------
    : list
        list of generators as k-chains
    """
    max_dim = np.max([len(e) for e in h.edges()]) - 1

    if k > max_dim or k < 1:
        return 'wrong dim'
    C = dict()
    for i in range(k - 1, k + 2):
        C[i] = kchainbasis(h, i)
    bd = dict()
    for i in range(k, k + 2):
        bd[i] = bkMatrix(C[i - 1], C[i])
    if log:
        try:
            logdict = pickle.load(open(log, 'rb'))
        except:
            logdict = dict()
        logdict.update({'maxdim': max_dim,
                        'kchains': C,
                        'bd': bd, })
        pickle.dump(logdict, open(log, 'wb'))
    return homology_basis(bd, k, C=C[k], shortest=shortest, log=log)
