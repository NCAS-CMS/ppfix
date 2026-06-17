from pyfive import File

def check_fragmentation(ncfile):
    """
    Test whether or not the metadata is fragmented, by looping over
    variables, and checking whether or not the first bytes of 
    any variable occur before the last element of the b-tree range.
    """
    f = File(ncfile, 'r')
    fragmented = False
    last_btree = 0
    first_data = 1024 * 1024 * 1024 * 1024  # 1GB, a large number to start with
    first_variable = None
    for v in f:
        vid = f[v].id
        try:
            first_chunk = vid.first_chunk
        except TypeError as e:
            print(f'Skipping variable {v}, probably not chunked (error {e})')
            continue
        range = vid.btree_range
        if first_chunk < first_data:
            first_data = first_chunk
            first_variable = v
        if range[1] > last_btree:
            last_btree = range[1]
    if first_data < last_btree:
        fragmented = True
        print(f'First data: {first_data} ({first_variable}), Last btree: {last_btree}, Fragmented: {fragmented}')
    return fragmented
