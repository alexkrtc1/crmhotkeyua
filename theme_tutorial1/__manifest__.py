{
    # Theme information
    'name': "Tutorial1 theme 1",
    'description': """ A custom theme example
    """,
    'category': 'Theme/Creative',
    'version': '1.0',
    'depends': ['website', ],

    # templates
    'data': [
        'views/layout.xml',
        'views/pages.xml',
        'views/snippets.xml',
        'views/options.xml'
    ],
    'assets': {
        'website.assets_editor': [
            'theme_tutorial1/static/src/js/tutorial_editor.js'
        ],
        'web.assets_frontend': [
            "/theme_tutorial1/static/src/css/custom.css",
            "/theme_tutorial1/static/src/scss/custom.scss",
        ],
        'web._assets_primary_variables': [
            "/theme_tutorial1/static/src/scss/primary_variables.scss"
        ],
        'web._assets_frontend_helpers': [
            "/theme_tutorial1/static/src/scss/bootstrap_overriden.scss"
        ],

    },

    # demo pages
    'demo': [

    ],

    # Your information
    'author': "My Company",
    'website': "",
}
