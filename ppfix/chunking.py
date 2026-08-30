import cf
def get_umchunking(field: cf.Field) -> tuple[int, ...]:
    """
    Determine the chunking for a cf.Field based on its shape and size.
    Returns None (allowing a default cf-python choice) if the field
    shape is not recognised.

    Parameters
    ----------
    field:
        A single cf.Field object.
    """

    # Get the shape of the field
    shape = field.shape

    if len(shape) < 2:
        return None

    ending = shape[-2:]

    umchunking = {
        #n1280
        (1920, 2560): (960, 1280),
        (1921, 2560): (961, 1280),
    }

    if ending not in umchunking:
        return None
    
    ending = umchunking[ending]

    chunking = tuple(1 for _ in shape[:-2]) + ending
    return chunking


def get_nemochunking(field: cf.Field) -> tuple[int, ...]:
    """
    Determine the chunking for a cf.Field based on its shape and size.
    Returns None (allowing a default cf-python choice) if the field
    shape is not recognised.

    Parameters
    ----------
    field:
        A single cf.Field object.
    """

    # Get the shape of the field
    shape = field.shape

    nemochunking = {
        #O12
        (1, 75, 3606, 4322): (1, 1, 601, 1441),
        (28, 3606, 4322): (1, 601, 1441),
        (29, 3606, 4322): (1, 601, 1441),
        (30, 3606, 4322): (1, 601, 1441),
        (31, 3606, 4322): (1, 601, 1441),
        (1, 3606, 4322): (1, 601, 1441),
        (1, 1, 3606, 4322): (1, 1, 601, 1441),
        (1, 5, 3606, 4322): (1, 1, 601, 1441),
        (28, 1, 3606, 4322): (1, 1, 601, 1441),
        (29, 1, 3606, 4322): (1, 1, 601, 1441),
        (30, 1, 3606, 4322): (1, 1, 601, 1441),
        (31, 1, 3606, 4322): (1, 1, 601, 1441),
        (1, 5, 3606, 1): (1, 5, 3606, 1),
        (1, 5, 75, 3606, 1): (1, 5, 1, 3606, 1),
        (1,): None,
        (28,): None
    
    }

    if shape in nemochunking:
        newchunk = nemochunking[shape]
        print(f"Using NEMO chunking {newchunk} for {field.identity()} with shape {shape}")
        return newchunk
    else:
        print(f"Field {field.identity()} with shape {shape} not recognised NEMO chunking")
        return None
