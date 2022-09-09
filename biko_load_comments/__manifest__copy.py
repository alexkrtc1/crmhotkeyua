# -*- coding: utf-8 -*-
{
    'name': "BIKO: Import comments to opportunities",
    'version': '15.0.1.1.1',
    'author': 'Borovlev AS',
    'company': 'BIKO',
    "depends": ['crm'],
    "data": [
        'wizard/biko_import_recs_views.xml',
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_qweb': [

        ],
        'web.assets_backend': [

        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
    "sequence": -1,
}
