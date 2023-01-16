# -*- coding: utf-8 -*-
{
    'name': "BIKO: Import comments to opportunities",
    'version': '14.0.1.3.1',
    'author': 'Borovlev AS and Hotkey',
    'company': 'BIKO,HOTKEY',
    "depends": ['crm'],
    "data": [
        'wizard/biko_import_recs_views.xml',
        'security/ir.model.access.csv',
        'views/assets.xml',
        'views/res_config_settings_views.xml'

    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
    "sequence": -1,
}
