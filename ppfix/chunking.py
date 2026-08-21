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
