# #
# Copyright 2009-2015 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/easybuild
#
# EasyBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EasyBuild.  If not, see <http://www.gnu.org/licenses/>.
# #
"""
Documentation-related functionality

@author: Stijn De Weirdt (Ghent University)
@author: Dries Verdegem (Ghent University)
@author: Kenneth Hoste (Ghent University)
@author: Pieter De Baets (Ghent University)
@author: Jens Timmerman (Ghent University)
@author: Toon Willems (Ghent University)
@author: Ward Poelmans (Ghent University)
"""
import copy
import inspect
import os

from easybuild.framework.easyconfig.default import DEFAULT_CONFIG, HIDDEN, sorted_categories
from easybuild.framework.easyconfig.easyconfig import get_easyblock_class
from easybuild.tools.ordereddict import OrderedDict
from easybuild.tools.utilities import quote_str, import_available_modules
from easybuild.tools.filetools import read_file

FORMAT_RST = 'rst'
FORMAT_TXT = 'txt'

def det_col_width(entries, title):
    """Determine column width based on column title and list of entries."""
    return max(map(len, entries + [title]))


def avail_easyconfig_params_rst(title, grouped_params):
    """
    Compose overview of available easyconfig parameters, in RST format.
    """
    # main title
    lines = [
        title,
        '=' * len(title),
        '',
    ]

    for grpname in grouped_params:
        # group section title
        lines.append("%s parameters" % grpname)
        lines.extend(['-' * len(lines[-1]), ''])

        name_title = "**Parameter name**"
        descr_title = "**Description**"
        dflt_title = "**Default value**"

        # figure out column widths
        nw = det_col_width(grouped_params[grpname].keys(), name_title) + 4  # +4 for raw format ("``foo``")
        dw = det_col_width([x[0] for x in grouped_params[grpname].values()], descr_title)
        dfw = det_col_width([str(quote_str(x[1])) for x in grouped_params[grpname].values()], dflt_title)

        # 3 columns (name, description, default value), left-aligned, {c} is fill char
        line_tmpl = "{0:{c}<%s}   {1:{c}<%s}   {2:{c}<%s}" % (nw, dw, dfw)
        table_line = line_tmpl.format('', '', '', c='=', nw=nw, dw=dw, dfw=dfw)

        # table header
        lines.append(table_line)
        lines.append(line_tmpl.format(name_title, descr_title, dflt_title, c=' '))
        lines.append(line_tmpl.format('', '', '', c='-'))

        # table rows by parameter
        for name, (descr, dflt) in sorted(grouped_params[grpname].items()):
            rawname = '``%s``' % name
            lines.append(line_tmpl.format(rawname, descr, str(quote_str(dflt)), c=' '))
        lines.append(table_line)
        lines.append('')

    return '\n'.join(lines)

def avail_easyconfig_params_txt(title, grouped_params):
    """
    Compose overview of available easyconfig parameters, in plain text format.
    """
    # main title
    lines = [
        '%s:' % title,
        '',
    ]

    for grpname in grouped_params:
        # group section title
        lines.append(grpname.upper())
        lines.append('-' * len(lines[-1]))

        # determine width of 'name' column, to left-align descriptions
        nw = max(map(len, grouped_params[grpname].keys()))

        # line by parameter
        for name, (descr, dflt) in sorted(grouped_params[grpname].items()):
            lines.append("{0:<{nw}}   {1:} [default: {2:}]".format(name, descr, str(quote_str(dflt)), nw=nw))
        lines.append('')

    return '\n'.join(lines)

def avail_easyconfig_params(easyblock, output_format):
    """
    Compose overview of available easyconfig parameters, in specified format.
    """
    params = copy.deepcopy(DEFAULT_CONFIG)

    # include list of extra parameters (if any)
    extra_params = {}
    app = get_easyblock_class(easyblock, default_fallback=False)
    if app is not None:
        extra_params = app.extra_options()
    params.update(extra_params)

    # compose title
    title = "Available easyconfig parameters"
    if extra_params:
        title += " (* indicates specific to the %s easyblock)" % app.__name__

    # group parameters by category
    grouped_params = OrderedDict()
    for category in sorted_categories():
        # exclude hidden parameters
        if category[1].upper() in [HIDDEN]:
            continue

        grpname = category[1]
        grouped_params[grpname] = {}
        for name, (dflt, descr, cat) in params.items():
            if cat == category:
                if name in extra_params:
                    # mark easyblock-specific parameters
                    name = '%s*' % name
                grouped_params[grpname].update({name: (descr, dflt)})

        if not grouped_params[grpname]:
            del grouped_params[grpname]

    # compose output, according to specified format (txt, rst, ...)
    avail_easyconfig_params_functions = {
        FORMAT_RST: avail_easyconfig_params_rst,
        FORMAT_TXT: avail_easyconfig_params_txt,
    }
    return avail_easyconfig_params_functions[output_format](title, grouped_params)

def generic_easyblocks():
    """
    Compose overview of all generic easyblocks
    """
    modules = import_available_modules('easybuild.easyblocks.generic')
    docs = []
    seen = []

    for m in modules:
        for name,obj in inspect.getmembers(m, inspect.isclass):
            eb_class = getattr(m, name)
            # skip imported classes that are not easyblocks
            if eb_class.__module__.startswith('easybuild.easyblocks.generic') and name not in seen:
                docs.append(doc_easyblock(eb_class))
                seen.append(name)

    return docs


def doc_easyblock(eb_class):
    """
    Compose overview of one easyblock given class object of the easyblock in rst format
    """
    classname = eb_class.__name__

    common_params = {
        'ConfigureMake' : ['configopts', 'buildopts', 'installopts'],
        # to be continued
    }

    lines = [
        '``' + classname + '``',
        '=' * (len(classname)+4),
        '',
    ]

    bases = ['``' + base.__name__ + '``' for base in eb_class.__bases__]
    derived = '(derives from ' + ', '.join(bases) + ')'


    lines.extend([derived, ''])

    # Description (docstring)
    lines.extend([eb_class.__doc__.strip(), ''])

    # Add extra options, if any
    if eb_class.extra_options():
        extra_parameters = 'Extra easyconfig parameters specific to ``' + classname + '`` easyblock'
        lines.extend([extra_parameters, '-' * len(extra_parameters), ''])
        ex_opt = eb_class.extra_options()

        ectitle = 'easyconfig parameter'
        desctitle = 'description'
        dftitle = 'default value'

        # figure out column widths
        nw = det_col_width([key for key in ex_opt], ectitle) + 4 # +4 for backticks
        dw = det_col_width([val[1] for val in ex_opt.values()], desctitle)
        dfw = det_col_width([str(val[0]) for val in ex_opt.values()], dftitle) + 4 # +4 for backticks

        # table aligning
        line_tmpl = "{0:{c}<%s}   {1:{c}<%s}   {2:{c}<%s}" % (nw, dw, dfw)
        table_line = line_tmpl.format('', '', '', c='=', nw=nw, dw=dw, dfw=dfw)

        lines.append(table_line)
        lines.append(line_tmpl.format(ectitle, desctitle, dftitle, c=' '))
        lines.append(table_line)

        for key in ex_opt:
           lines.append(line_tmpl.format('``'+key+'``', ex_opt[key][1], '``' + str(quote_str(ex_opt[key][0])) + '``', c=' '))
        lines.extend([table_line, ''])


    if classname in common_params:
        commonly_used = 'Commonly used easyconfig parameters with ``' + classname + '`` easyblock'
        lines.extend([commonly_used, '-' * len(commonly_used)])

        for opt in common_params[classname]:
            param = '* ``' + opt + '`` - ' + DEFAULT_CONFIG[opt][1]
            lines.append(param)


    if classname + '.eb' in os.listdir(os.path.join(os.path.dirname(__file__), 'doc_examples')):
        lines.extend(['', 'Example', '-' * 8, '', '::', ''])
        f = open(os.path.join(os.path.dirname(__file__), 'doc_examples', classname+'.eb'), "r")
        for line in f.readlines():
            lines.append('    ' + line.strip())
        lines.append('') # empty line after literal block

    return '\n'.join(lines)



