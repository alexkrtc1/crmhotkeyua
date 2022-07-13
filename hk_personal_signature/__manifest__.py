{
    'name': 'Personal signature and stamp on documents',
    'version': '15.0.1.0.0',

    'author': 'HOTKEY COMPANY',
    'website': 'https://hotkey.ua',
    'license': 'OPL-1',
    'category': 'Localization',

    'depends': [
        'kw_invoice_rahf', 'kw_invoice_vydn', 'kw_so_vydn', 'kw_so_rahf'
    ],
    'data': [
        'report/invoice_inherit.xml',
        'views/users_company.xml',
    ],
    'installable': True,
    'demo': [

    ],

    'images': [
        'static/description/cover.png',
        'static/description/icon.png',
    ],

}
