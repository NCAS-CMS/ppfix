from pathlib import Path
import json
import re

STASH_RE = re.compile(r'm01s\d{2}i\d{3}')

HADGEM3_SIMPLE_TABLE = Path(__file__).parent / 'stash_cmip6_simple.json'
HADGEM3_FULL_TABLE = Path(__file__).parent / 'stash_cmip6_all.json'

class CMIPIdentifiers:
    """ 
    Instantiate to provide a mapping from fields to CMIP table and variable identifiers. 
    """
    def __init__(self, era='CMIP6', source='HadGEM3'):
        self.era = era
        self.source = source

        if era == 'CMIP6':
            if source == 'HadGEM3':
                self.initialise()
            else:
                raise ValueError(f'Unsupported source {source} for era {era}')
        else:
            raise ValueError(f'Unsupported era {era}')


    def initialise(self):
        """ 
        Read and instantiate mapping 
        """
        if self.source == 'HadGEM3':
            TABLE = HADGEM3_FULL_TABLE
            self.varid_name = 'cmip6_short_name'
        else:
            raise NotImplementedError(f'CMIP identifiers for source {self.source} not implemented.')

        with open(TABLE, 'r') as f:
            mapping = json.load(f)
            self.mapping = {f"{m['stash']}{m['lbproc']}": m for m in mapping}



    def _find_cmip6(self, field):
        """
        Return a table and variable identifiers for a given field
        """
        table, variable = None, None
        stash = f"{field.get_property('um_stash_source', None)}{field.get_property('lbproc', None)}"
        if stash is not None:
            if stash in self.mapping:
                mapping = self.mapping[stash]
                if mapping['is_simple_mapping']:
                    table = mapping['mip_table']
                    variable = mapping['cmip6_short_name']
                else:
                    table = mapping['mip_table']
                    variable = 'expression'
            else:
                table = 'unknown'
                variable = 'unknown'
        return table, variable


    def find(self, field):
        """
        Return a dictionary of CMIP6 identifiers for the given field.
        This will only do as simple look up, if the identifier is only used in a complex expression it will return unknown.
        """
        if self.era == 'CMIP6':
            return self._find_cmip6(field)
        else:
            raise NotImplementedError(f'CMIP identifiers for era {self.era} not implemented.')

